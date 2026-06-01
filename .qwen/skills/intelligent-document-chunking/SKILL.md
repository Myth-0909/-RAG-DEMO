---
name: intelligent-document-chunking
description: 自动分析文档内容特征并智能选择最优分块策略，避免用户手动选择
source: auto-skill
extracted_at: '2026-06-01T02:15:00.000Z'
---

# 智能文档分块策略自动选择

## 核心问题

传统 RAG 系统要求用户手动选择分块策略（递归/固定/父子/语义），但：
1. 用户不了解不同策略的适用场景
2. 同一知识库内不同文档可能需要不同策略
3. 手动选择无法根据文档内容动态调整

## 解决方案：内容分析 + 自动策略推荐

### 处理流程

```
上传文档 → 提取文本 → 数据清洗 → 内容分析 → 自动选策略 → 分块 → 向量化 → 存储
```

### 1. 数据清洗（保留原始语义）

```python
def clean_content(text: str, file_type: str) -> Tuple[str, Dict]:
    """清洗内容，保留原始含义"""
    # 修复编码问题（零宽空格、BOM等）
    # 标准化空白（多个空格→单空格，多个空行→双空行）
    # 移除 PDF 伪影（页码、断行连字符）
    # 返回清洗后文本 + 清洗报告
```

**关键点**：清洗只移除格式问题，不改变语义内容。

### 2. 内容特征分析

计算三个维度的评分（0-1）：

- **结构评分 (structure_score)**：标题密度、章节数、列表、表格、代码块
  - 高结构：技术文档、手册、报告
  - 低结构：散文、小说、邮件

- **叙事评分 (narrative_score)**：平均句长、段落长度、标题稀疏度
  - 高叙事：连续文本、长段落、少标题
  - 低叙事：结构化内容、短段落

- **密度评分 (density_score)**：内容类型混合度、段落长度适中
  - 高密度：混合结构+叙述+列表
  - 低密度：单一类型内容

### 3. 策略选择规则

```python
def recommend_strategy(profile: ContentProfile) -> str:
    # 短文档 (<1000字符)
    if total_chars < 1000:
        return "recursive"
    
    # 高结构 + 多标题 → 父子分块
    if structure_score >= 0.5 and heading_count >= 3:
        return "parent_child"
    
    # 高叙事 + 低结构 → 语义分块
    if narrative_score >= 0.5 and structure_score < 0.3:
        return "semantic"
    
    # 混合内容 → 混合分块
    if density_score >= 0.4 and structure_score >= 0.2:
        return "hybrid"
    
    # 长文档 + 一定结构 → 父子分块
    if total_chars > 5000 and structure_score >= 0.25:
        return "parent_child"
    
    # 默认 → 递归分块
    return "recursive"
```

### 4. 混合分块策略（Hybrid）

对于混合内容，按段落自动切换策略：

```python
def chunk_hybrid(text, metadata, chunk_size, chunk_overlap):
    # 按标题或双空行分割成段落
    sections = split_by_sections(text)
    
    chunks = []
    for section in sections:
        # 检测段落类型
        is_structured = has_headings(section) or has_lists(section)
        
        if is_structured and len(section) > chunk_size:
            # 结构化部分用父子分块
            section_chunks = chunk_parent_child(section, ...)
        elif len(section) > chunk_size * 2:
            # 长叙述部分用语义分块
            section_chunks = chunk_semantic(section, ...)
        else:
            # 短段落用递归分块
            section_chunks = chunk_recursive(section, ...)
        
        chunks.extend(section_chunks)
    
    return chunks
```

### 5. 元数据存储

将分析结果存入文档元数据，供前端展示：

```python
doc.metadata_json = {
    "cleaning": cleaning_report,  # 清洗统计
    "content_analysis": {
        "total_chars": 12345,
        "headings": 15,
        "sections": 8,
        ...
    },
    "scores": {
        "structure": 0.72,
        "narrative": 0.23,
        "density": 0.45,
    },
    "strategy": {
        "selected": "parent_child",
        "label": "父子分块",
        "reasoning": "检测到 15 个标题和 8 个章节，文档结构清晰..."
    }
}
```

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

**现在**：
- 上传文档后全自动处理
- 前端展示自动检测的策略 + 推理原因
- 每个文档可以有不同策略（同一知识库内）

## 适用场景

- ✅ 用户上传多种类型文档（PDF/Word/Markdown/TXT）
- ✅ 文档类型差异大（技术文档、报告、散文混合）
- ✅ 用户不了解分块策略的技术细节
- ✅ 需要每个文档独立优化分块

## 不适用场景

- ❌ 所有文档都是同一类型且已知最优策略
- ❌ 需要完全控制分块参数的高级用户
- ❌ 对分块策略有严格合规要求（需固定策略）
