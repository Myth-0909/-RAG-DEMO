---
name: intelligent-document-chunking
description: LLM 驱动的文档智能分块——用模型分析内容、判断是否清洗、输出分块 JSON 方案，上传后自动后台分析并通过轮询展示进度和思考过程
source: auto-skill
extracted_at: '2026-06-04T02:43:59.899Z'
updated_at: '2026-06-04T05:10:22.271Z'
---

# LLM 驱动的文档智能分块

## 核心问题

传统 RAG 文档处理依赖规则引擎（正则 + 统计评分）分析内容和选择分块策略，但：
1. 规则无法理解文档语义和上下文意图
2. 四维评分（structure/narrative/density/hierarchy）的阈值是硬编码的，无法覆盖所有文档类型
3. 用户无法看到"模型为什么这样分析"的思考过程
4. 分块参数（chunk_size, chunk_overlap）是固定的，无法根据文档特征动态调整

## 解决方案：LLM 全流程分析 + 后台自动处理 + 轮询展示

### 处理流程

```
上传文档
  ↓
POST /documents → 保存文件，创建 ProcessingTask，自动触发后台处理
  ↓
后台 async task（无需 SSE 连接）：
┌─ Step 1: extract   → 文本提取（PDF/DOCX/TXT/MD，含表格+图片OCR）
├─ Step 2: clean     → LLM 流式评估是否需要清洗（思考过程写入 DB）
├─ Step 3: apply     → 如需清洗则执行规则清洗
├─ Step 4: analyze   → LLM 流式分析内容，输出分块方案 JSON（思考过程写入 DB）
├─ Step 5: chunk     → 按 LLM 的 JSON 方案执行分块
├─ Step 6: embed     → 向量化并存入 Milvus
└─ Step 7: complete  → 更新文档状态，保存分析结果摘要
  ↓
前端通过 REST API 轮询查看进度：
GET /processing-tasks/ → 任务列表
GET /processing-tasks/{id} → 任务详情（含完整事件历史）
POST /processing-tasks/{id}/retry → 重试失败的任务
```

**关键变化**：上传后立即自动触发后台处理，所有事件实时持久化到 `processing_tasks` 表。前端通过轮询 REST API 查看进度，无需维持 SSE 连接。

### 0. 富内容提取（关键层）

**问题**：`pypdf.PdfReader` 的 `extract_text()` 只提取文字，`python-docx` 的 `doc.paragraphs` 遍历也不包含表格。PDF/DOCX 中的表格和图片被完全忽略。

**解决方案**：三步提取 —— 文本 → 表格 → 图片

#### PDF 表格提取
- `pypdf` 无法可靠提取表格结构，改用 `pdfplumber`
- `pdfplumber` 能检测表格边框并返回结构化数据 `[[header1, header2], [row1col1, row1col2], ...]`
- 转为 Markdown 管道格式 `| col1 | col2 |` 确保下游 `TABLE_PATTERN` 正则能匹配

```python
import pdfplumber

def extract_pdf_tables(file_path):
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                headers = table[0]
                rows = table[1:]
                # 转为 Markdown 表格格式
                md = table_to_markdown(headers, rows)
```

#### DOCX 表格提取
- `python-docx` 的 `doc.tables` 提供结构化表格数据
- `doc.paragraphs` **不包含表格内容**，必须单独遍历 `doc.tables`

```python
from docx import Document

def extract_docx_tables(file_path):
    doc = Document(file_path)
    for table in doc.tables:
        rows_data = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        headers = rows_data[0]
        rows = rows_data[1:]
```

#### 图片提取 + OCR
- PDF: `pypdf` 的 `page.images` 可提取嵌入图片的原始字节
- DOCX: 遍历 `doc.part.rels`，筛选 `"image" in rel.reltype`，从 `rel.target_part.blob` 获取图片数据
- OCR: `pytesseract.image_to_string(img, lang="chi_sim+eng")` 支持中英文
- 依赖: `pytesseract` (Python) + `tesseract` (系统级, `brew install tesseract tesseract-lang`)

#### 表格/图片标记
- 提取的内容使用标记前缀：`[表格 第X页 表Y]`、`[图片 第X页 图Y]`
- 内容分析器通过正则 `EXTRACTED_TABLE_PATTERN = re.compile(r'\[表格[^\]]*\]')` 识别这些标记
- 确保表格计数反映实际提取的表格数，而非仅 Markdown 管道行匹配

#### 优雅降级
- 所有提取函数用 `try/except ImportError` 保护：依赖未安装时静默跳过而非崩溃
- OCR 失败时 `logger.warning` + 返回空字符串，不阻断文档处理流程
- `extract_text()` 将文本/表格/图片三部分拼接，任一部分为空不影响其他

#### 依赖
```
pdfplumber==0.11.4   # PDF 表格提取
pytesseract==0.3.13  # OCR Python 绑定
Pillow==11.1.0       # 图片处理
# 系统级: brew install tesseract tesseract-lang
```

### 1. LLM 清洗评估（替代规则引擎）

**文件**: `backend/app/services/llm_analyzer.py`

LLM 通过流式 API 分析提取的文本，判断是否需要清洗，并输出结构化 JSON 评估。

```python
# LLM 被要求的输出格式
{
  "needs_cleaning": true/false,
  "issues_found": ["发现的问题1", "发现的问题2"],
  "cleaning_actions": ["需要执行的清洗操作1"],
  "severity": "none/low/medium/high",
  "reasoning": "详细的分析推理过程"
}
```

**如果 LLM 判断需要清洗**，仍然调用现有的 `content_analyzer.clean_content()` 规则清洗器执行实际清洗。LLM 只负责"是否需要"的决策，不负责执行。

**如果 LLM 判断不需要清洗**，直接跳过清洗步骤（`cleaning_report["skipped"] = True`）。

**如果 LLM 调用失败（502/超时）**，自动降级到 `_fallback_cleaning_assessment()` 规则分析，基于正则检测编码异常、多余空行、PDF 页码等。

### 2. LLM 分块策略分析（替代规则评分模型）

**文件**: `backend/app/services/llm_analyzer.py`

LLM 分析文档内容特征，直接输出分块方案 JSON。不再依赖硬编码的四维评分阈值。

```python
# LLM 被要求的输出格式
{
  "strategy": "recursive/fixed/parent_child/semantic/hybrid",
  "chunk_size": 300-800,      # LLM 根据文档特征动态决定
  "chunk_overlap": 50-200,
  "analysis": {
    "document_type": "文档类型",
    "structure_features": "结构特征描述",
    "content_characteristics": "内容特征描述",
    "heading_hierarchy": "标题层级描述",
    "special_elements": ["表格", "列表", "代码块"],
    "recommended_reasoning": "为什么选择这个分块策略的详细推理过程"
  },
  "quality_score": 0.0-1.0
}
```

**JSON 解析容错**：`_parse_json_response()` 处理 LLM 输出格式不稳定的问题：
1. 先去除 ````json` 代码块包裹
2. 尝试直接 `json.loads()`
3. 失败则在文本中查找 `{...}` 子串
4. 再失败则移除尾随逗号后重试
5. 最终回退到 `_fallback_chunking_plan()` 启发式方案

**参数归一化**：`_normalize_chunking_plan()` 确保 LLM 返回的参数在合理范围：
- `chunk_size`: 限制在 200-1500
- `chunk_overlap`: 限制在 0 到 chunk_size/2
- `strategy`: 必须是五种之一

**文本截断**：`_truncate_text(text, max_chars)` 防止超出 LLM 上下文窗口：
- 清洗评估截断到 12000 字符
- 分块分析截断到 15000 字符
- 截断时保留首尾各一半，中间插入 `[中间内容省略]` 标记

### 4. 混合分块策略（Hybrid）+ 表格保护

对于混合内容，按段落自动切换策略。**必须先提取表格再分块**，否则表格会被切分成碎片。

```python
def chunk_hybrid(text, metadata, chunk_size, chunk_overlap):
    # 1. 先提取表格为完整单元
    # 2. 对剩余文字按标题/双空行分割成段落
    # 3. 根据段落类型选择策略

    def hybrid_chunk_text(text_part):
        """对无表格的文字做混合分块"""
        sections = split_by_sections(text_part)  # 包含数字标题
        chunks = []
        for section in sections:
            # 检测段落类型（必须包含数字标题检测）
            has_heading = bool(re.search(
                r'^#{1,6}\s|^[一二三四五六七八九十]+[、.]|^\d+(?:\.\d+){0,2}\s+\S',
                section, re.MULTILINE
            ))
            has_list = bool(re.search(r'^[\s]*[-*•]\s+.+', section, re.MULTILINE))
            is_structured = has_heading or has_list

            if is_structured and len(section) > chunk_size:
                chunks.extend(chunk_parent_child(section, ...))
            elif len(section) > chunk_size * 2:
                chunks.extend(chunk_semantic(section, ...))
            else:
                chunks.extend(chunk_recursive(section, ...))
        return chunks

    return extract_tables_and_chunk_text(text, metadata, hybrid_chunk_text)
```

### 4.1 表格保护机制（关键）

**⚠️ 教训**：`hybrid` 和 `parent_child` 直接用 `RecursiveCharacterTextSplitter` 切分，会在表格行中间砍断，导致检索时找不到完整的表格数据。

**解决方案**：`_extract_tables_and_chunk_text()` —— 先用正则把 Markdown 表格整体抽出来作为独立 chunk，剩余文字再交给分块函数。

```python
# 匹配完整 Markdown 表格（表头行 + 分隔行 + 数据行）
_TABLE_BLOCK_RE = re.compile(
    r'(\|[^\n]+\|\n\|[\s\-:|]+\|\n(?:\|[^\n]+\|\n?)+)', re.MULTILINE
)

def extract_tables_and_chunk_text(text, metadata, text_chunk_fn, start_index=0):
    """
    1. 用 _TABLE_BLOCK_RE.split(text) 将文字和表格交替分开
    2. 表格部分 → 直接作为完整 chunk（超大表格按行拆分但保留表头）
    3. 文字部分 → 调用 text_chunk_fn 处理
    """
    parts = _TABLE_BLOCK_RE.split(text)
    chunks = []
    idx = start_index

    for part in parts:
        if _TABLE_BLOCK_RE.fullmatch(part):
            # 完整表格 → 作为独立 chunk
            if len(part) > 2000:
                # 超大表格：按行拆分，但每个子块保留表头
                # ...
            else:
                chunks.append(ChunkResult(text=part, ...))
        else:
            # 普通文字 → 委托给分块函数
            text_chunks = text_chunk_fn(part)
            chunks.extend(text_chunks)

    return chunks
```

**超大表格处理**：当表格 >2000 字符时，按行拆分但每个子块都复制表头行（header + separator），保证每个子块都是可解析的完整表格。

**所有策略都启用表格保护**：
- `_chunk_parent_child` → 通过 `extract_tables_and_chunk_text` 包装
- `_chunk_hybrid` → 通过 `extract_tables_and_chunk_text` 包装
- `_chunk_recursive` / `_chunk_fixed` / `_chunk_semantic` → 未包装（这些策略通常用于无表格的纯文本）

### 5. 元数据存储

将 LLM 分析结果存入文档元数据，供前端展示：

```python
doc.metadata_json = {
    "cleaning": {
        **cleaning_report,          # 规则清洗统计（chars_removed, encoding_fixed 等）
        "llm_assessment": {        # LLM 的清洗评估
            "needs_cleaning": true,
            "issues_found": [...],
            "severity": "medium",
            "reasoning": "...",
        },
    },
    "llm_analysis": {              # LLM 的完整分块分析 JSON
        "strategy": "parent_child",
        "chunk_size": 600,
        "chunk_overlap": 120,
        "analysis": {...},
        "quality_score": 0.85,
    },
    "content_analysis": {
        "total_chars": 12345,
    },
    "strategy": {                  # 兼容旧版 AnalysisDialog 的格式
        "selected": "parent_child",
        "label": "父子分块",
        "reasoning": "LLM 分析推荐的理由...",
    },
}
```

### 6. 后台自动处理架构（ProcessingTask）

**核心改进**：上传文件后自动触发后台处理，所有事件持久化到数据库，前端通过轮询查看进度。

#### 数据模型

**文件**: `backend/app/models/processing_task.py`

```python
class ProcessingTask(Base):
    __tablename__ = "processing_tasks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"))
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"))
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    current_step = Column(String(50), nullable=True)
    events = Column(JSON, default=list)  # 完整的事件历史
    error_message = Column(Text, nullable=True)
    result_summary = Column(JSON, nullable=True)  # 处理完成后的摘要
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

#### 后台处理器

**文件**: `backend/app/services/background_processor.py`

```python
async def run_background_processing(task_id, doc_id, file_path, metadata):
    """消费 process_document_stream async generator，将事件写入 DB"""
    db = _SessionLocal()
    task = db.query(ProcessingTask).filter(ProcessingTask.id == task_id).first()
    task.status = "processing"
    task.current_step = "extract"
    db.commit()

    collected_events = []
    async for event in process_document_stream(doc_id, file_path, metadata):
        # 添加步骤标签和时间戳
        enriched_event = {
            **event,
            "step_label": STEP_LABELS.get(event["step"], event["step"]),
            "timestamp": datetime.now().isoformat(),
        }
        
        # 只保存关键事件（非 token 级的 thinking）
        if status in ("thinking",) and "token" not in data:
            collected_events.append(enriched_event)
        elif status in ("done", "error"):
            collected_events.append(enriched_event)
        
        task.current_step = event["step"]
        task.events = list(collected_events)
        db.commit()
    
    # 处理完成
    task.status = "completed"
    task.result_summary = last_event.get("data", {})
    db.commit()

def start_background_processing(task_id, doc_id, file_path, metadata):
    """在事件循环中启动后台任务"""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.ensure_future(
            run_background_processing(task_id, doc_id, file_path, metadata)
        )
```

#### 上传自动触发

**文件**: `backend/app/api/v1/knowledge.py`

```python
@router.post("/{kb_id}/documents", response_model=DocumentResponse)
async def upload_document(...):
    # ... 保存文件 ...
    
    doc = Document(...)
    db.add(doc)
    db.commit()
    
    # 创建 ProcessingTask 并自动触发后台处理
    task = ProcessingTask(
        document_id=doc.id,
        knowledge_base_id=kb_id,
        status="pending",
    )
    db.add(task)
    db.commit()
    
    start_background_processing(
        task_id=task.id,
        doc_id=doc.id,
        file_path=file_path,
        metadata=metadata or {},
    )
    
    return doc
```

#### REST API 端点

**文件**: `backend/app/api/v1/processing_tasks.py`

```python
@router.get("/")
def list_processing_tasks(status: Optional[str] = None, ...):
    """获取任务列表，支持按状态过滤"""
    query = db.query(ProcessingTask)
    if status:
        query = query.filter(ProcessingTask.status == status)
    tasks = query.order_by(ProcessingTask.created_at.desc()).all()
    # 关联查询文档名和知识库名
    ...

@router.get("/{task_id}")
def get_processing_task(task_id: int):
    """获取任务详情，包含完整的事件历史"""
    task = db.query(ProcessingTask).filter(ProcessingTask.id == task_id).first()
    return ProcessingTaskResponse(
        ...
        events=task.events or [],  # 完整事件历史
        result_summary=task.result_summary,
    )

@router.post("/{task_id}/retry")
def retry_processing_task(task_id: int):
    """重试失败的任务"""
    task = db.query(ProcessingTask).filter(ProcessingTask.id == task_id).first()
    if task.status != "failed":
        raise HTTPException(status_code=400, detail="只能重试失败的任务")
    
    # 重置状态
    task.status = "pending"
    task.events = []
    task.error_message = None
    db.commit()
    
    # 重新启动后台处理
    start_background_processing(...)
    return {"detail": "已重新启动处理"}
```

#### 前端轮询展示

**文件**: `frontend/src/pages/processing-tasks/index.tsx`

```typescript
const ProcessingTasksPage: React.FC = () => {
  const [tasks, setTasks] = useState<any[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchTasks = useCallback(async () => {
    const res = await getProcessingTasks();
    setTasks(res.data);
  }, []);

  // 有活跃任务时每 3 秒自动轮询
  const hasActive = tasks.some(t => t.status === 'pending' || t.status === 'processing');
  useEffect(() => {
    if (hasActive) {
      pollRef.current = setInterval(fetchTasks, 3000);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [hasActive, fetchTasks]);

  // 点击查看详情时打开 Drawer，轮询任务详情
  const openDetail = async (task: any) => {
    setDrawerOpen(true);
    const res = await getProcessingTask(task.id);
    setTaskDetail(res.data);
  };

  // Drawer 内展示完整的事件历史，复用 ProcessAnalysisDialog 的 UI 组件
  const stepStates = buildStepStates(taskDetail.events);
  ...
};
```

**关键设计**：
1. **事件持久化**：所有步骤事件实时写入 `processing_tasks.events` JSON 字段
2. **轮询而非 SSE**：前端每 3 秒请求一次 REST API，无需维持长连接
3. **独立页面**：新增"处理任务"页面（侧边栏入口），集中展示所有任务
4. **复用 UI**：Drawer 内复用 `RenderEventDetail` 组件展示步骤详情
5. **自动刷新**：有活跃任务时自动轮询，完成后停止

**与旧版 SSE 的关系**：
- 旧的 SSE 端点 `GET /documents/{id}/process-stream` 仍然保留，可用于实时调试
- 新的后台处理模式是**默认流程**，上传后自动触发
- 前端不再需要手动建立 SSE 连接，简化了上传逻辑

## 关键实现细节

### 内容分析器正则模式

```python
# 标题检测
HEADING_PATTERNS = [
    re.compile(r'^#{1,6}\s+.+', re.MULTILINE),           # Markdown
    re.compile(r'^[一二三四五六七八九十]+[、.]\s*.+', re.MULTILINE),  # 中文编号
    re.compile(r'^第[一二三四五六七八九十\d]+[章节部分]', re.MULTILINE),
]

# 列表检测
LIST_PATTERNS = [
    re.compile(r'^[\s]*[-*•]\s+.+', re.MULTILINE),
    re.compile(r'^[\s]*\d+[.)]\s+.+', re.MULTILINE),
]
```

### 评分计算示例

```python
def calculate_structure_score(total_chars, heading_count, section_count, ...):
    score = 0.0
    
    # 标题密度（每1000字符的标题数）
    heading_density = heading_count / (total_chars / 1000)
    score += min(heading_density * 0.15, 0.3)
    
    # 章节数
    section_density = section_count / (total_chars / 1000)
    score += min(section_density * 0.12, 0.25)
    
    # 列表、表格、代码块...
    
    return min(score, 1.0)
```

## 用户体验改进

**之前**：
- 新建知识库时必须选择分块策略
- 用户困惑于"递归"vs"语义"vs"父子"的区别
- 选错策略导致检索效果差
- 分块策略对用户完全不透明
- 上传后必须保持页面打开以维持 SSE 连接

**现在**：
- 上传文档后全自动处理，**无需保持页面打开**
- 上传提示"系统正在后台自动分析"
- 侧边栏新增**"处理任务"**入口，集中查看所有任务进度
- 点击任务可查看完整的 LLM 分析过程和思考结果
- 失败的任务支持一键重试
- **文档处理完成后**可在知识库中点击 ⚡ 按钮查看分析结果（AnalysisDialog）
- 每个文档可以有不同策略（同一知识库内）

### AnalysisDialog UX 设计原则

1. **自动弹出但可关闭** — 新文档处理完成自动展示，用户可点"知道了"关闭
2. **不重复弹出** — 使用 `processedDocIdsRef` 跟踪已展示的文档 ID
3. **对话式展示** — 模拟"系统→分析师→系统"的对话流，逐步展开分析过程
4. **渐进动画** — 气泡依次淡入（0.08s 间隔），避免信息过载
5. **手动可访问** — 文档列表操作列提供 ⚡ 按钮随时查看

## 适用场景

- ✅ 用户上传多种类型文档（PDF/Word/Markdown/TXT）
- ✅ 文档类型差异大（技术文档、报告、散文混合）
- ✅ 用户不了解分块策略的技术细节
- ✅ 需要每个文档独立优化分块

## 不适用场景

- ❌ 所有文档都是同一类型且已知最优策略
- ❌ 需要完全控制分块参数的高级用户
- ❌ 对分块策略有严格合规要求（需固定策略）

## 常见坑和教训

### 坑1：数字层级标题不被识别

**问题**：`5 xxx` / `5.1 xxxx` / `5.1.1 xxx` 这种数字层级标题不被 `HEADING_PATTERNS` 识别，导致 `heading_levels=0`、`hierarchy_score` 极低。

**后果**：
- 策略选择错误（应该选 `parent_child` 却选了 `hybrid`）
- 表格被切分成碎片，检索时找不到完整数据
- 用户抱怨"分块后找不到对应内容"

**修复**：
```python
# 添加数字标题检测
NUMERIC_HEADING_ALL_RE = re.compile(r'^(\d+(?:\.\d+){0,2})\s+\S.{1,}', re.MULTILINE)

# 在 section_splits 和 hybrid 的 has_heading 检测中都加入
has_heading = bool(re.search(
    r'^#{1,6}\s|^[一二三四五六七八九十]+[、.]|^\d+(?:\.\d+){0,2}\s+\S',
    section, re.MULTILINE
))
```

### 坑2：表格被切碎

**问题**：`hybrid` 和 `parent_child` 直接用 `RecursiveCharacterTextSplitter` 切分，会在表格行中间砍断。

**后果**：
- 表格数据丢失（如 `| 1 | 基础工程 | A级 | 100 | 50万 |` 被切成多个碎片）
- 检索时只能匹配到部分行，无法获取完整表格信息
- 用户抱怨"分块后找不到对应内容"

**修复**：
```python
# 先提取表格为完整单元，再分块
_TABLE_BLOCK_RE = re.compile(
    r'(\|[^\n]+\|\n\|[\s\-:|]+\|\n(?:\|[^\n]+\|\n?)+)', re.MULTILINE
)

def extract_tables_and_chunk_text(text, metadata, text_chunk_fn, start_index=0):
    """
    1. 用 _TABLE_BLOCK_RE 把 Markdown 表格整体抽出来
    2. 剩余文字再交给交给分块函数
    """
    parts = _TABLE_BLOCK_RE.split(text)
    tables = [p for p in parts if _TABLE_BLOCK_RE.fullmatch(p)]
    text_only = [p for p in parts if not _TABLE_BLOCK_RE.fullmatch(p)]
    
    # 对 text_only 做分块
    chunks = []
    for text_part in text_only:
        chunks.extend(text_chunk_fn(text_part, metadata))
    
    # 对 tables 直接作为完整 chunk
    for table in tables:
        chunks.append(ChunkResult(text=table, metadata=metadata))
    
    return chunks
```

### 坑3：hybrid 的 section_pattern 检测不够

**问题**：`hybrid` 的 `section_pattern` 只检测 `^#{1,6}\s` 和 `^第[一二三四五六七八九十\d]+[章节部分]`，漏掉了数字层级标题。

**修复**：在 `section_pattern` 检测中加入数字标题模式：
```python
has_heading = bool(re.search(
    r'^#{1,6}\s|^[一二三四五六七八九十]+[、.]|^\d+(?:\.\d+){0,2}\s+\S',
    section, re.MULTILINE
))
```

### 坑4：LLM 502 超时导致处理中断

**问题**：发送 12000-15000 字符给 gemma-4-31B-it 做清洗评估后，再发送 15000 字符做分块分析，第二次调用经常返回 502。OpenAI client 无 timeout 设置，无 retry 机制，异常直接导致 SSE 流中断。

**根因**：
1. 发送给 LLM 的文本太长，模型处理时间超过网关超时
2. 连续两次大文本 LLM 请求导致模型服务过载
3. OpenAI client 没有设置 timeout
4. `document.py` 中 LLM 调用异常没有被 catch，导致 async generator 崩溃

**修复**：

1. **缩减文本大小**：清洗评估和分块分析都截断到 6000 字符（原来 12000/15000）
```python
MAX_CLEANING_CHARS = 6000
MAX_CHUNKING_CHARS = 6000
```

2. **httpx.Timeout 配置**：connect=10s, read=180s（流式读取需要更长时间）
```python
_LLM_TIMEOUT = httpx.Timeout(connect=10.0, read=180.0, write=10.0, pool=10.0)

client = OpenAI(
    base_url=cfg.base_url,
    api_key=cfg.api_key,
    timeout=_LLM_TIMEOUT,
    max_retries=0,  # 自己管理重试
)
```

3. **集中式重试**：`_call_llm_stream()` 最多重试 2 次，每次间隔递增（3s, 6s）
```python
for attempt in range(_MAX_RETRIES + 1):
    if attempt > 0:
        time.sleep(_RETRY_DELAY * attempt)
    try:
        # ... stream and collect response
        return full_response
    except Exception as e:
        last_error = e
        continue
raise last_error
```

4. **每次调用创建新 client**：不再缓存全局 `_client`，确保配置变更后立即生效
```python
def get_llm_client():
    cfg = get_current_llm_config()
    return OpenAI(base_url=cfg.base_url, api_key=cfg.api_key, timeout=_LLM_TIMEOUT)
```

5. **document.py 中的双重保护**：
```python
def _run_assess():
    try:
        return assess_cleaning_stream(raw_text, doc.file_type, _clean_thinking)
    except Exception as e:
        # LLM 完全失败时返回安全默认值，不中断 SSE 流
        return {"needs_cleaning": False, "issues_found": [f"LLM 异常: {e}"], ...}
    finally:
        loop.call_soon_threadsafe(clean_queue.put_nowait, None)  # sentinel
```

6. **llm_analyzer 中的 fallback**：每个 LLM 函数内部 catch 异常，降级到规则分析
```python
def assess_cleaning_stream(text, file_type, on_thinking):
    fallback = _fallback_cleaning_assessment(text, file_type)
    try:
        response = _call_llm_stream(...)
        return _parse_json_response(response, fallback=fallback)
    except Exception as e:
        on_thinking(f"\n\n⚠ LLM 调用失败（{e}），切换到规则分析模式...")
        return fallback
```
