# RAG 知识库管理系统 — 设计文档

## 一、系统概述

基于 FastAPI + React + Milvus 的企业级 RAG（检索增强生成）知识库管理平台。核心能力：多策略文档分块、向量化存储与检索、LLM 驱动的文档智能分析、多轮对话问答与长期记忆。

**技术选型**：后端 Python FastAPI + SQLAlchemy + LangChain；前端 React 18 + Vite + Ant Design 5；向量库 Milvus (pymilvus)；嵌入模型 Qwen3-Embedding-8B（OpenAI 兼容 API）；默认 SQLite（可切换 PostgreSQL）。

---

## 二、设计思路

### 2.1 权限模型：RBAC + 超级管理员旁路

系统采用基于角色的访问控制（RBAC），包含四张核心表：

```
users ──< user_roles >── roles ──< role_permissions >── permissions
```

- **User**：用户主体，`is_superuser` 字段标记超级管理员，超级管理员绕过所有权限检查
- **Role**：角色，`is_system` 字段保护内置角色（管理员、普通用户）不被误删或修改
- **Permission**：权限，自引用树形结构（`parent_id`），支持无限层级，`type` 字段区分菜单/按钮/API 三种粒度
- **UserRole / RolePermission**：两张多对多关联表

**设计考量**：

- 权限树而非平铺列表 —— 权限天然有父子关系（如 `knowledge` 菜单下包含 `knowledge:upload` 按钮），树形结构方便前端渲染菜单和批量授权
- 系统角色不可变 —— `is_system=True` 的角色在 API 层被保护，确保种子数据中的基础角色结构不被破坏
- 超级管理员旁路 —— `require_permission` 依赖中对 `is_superuser` 直接放行，避免超级管理员因权限配置错误被锁死

### 2.2 动态模型配置：数据库优先 + 环境变量回退

传统做法将 LLM / Embedding 的连接信息写死在 `.env` 文件中，切换模型需要重启服务。系统引入 `ModelConfig` 表实现运行时可切换的模型配置：

```
ModelConfig (DB, is_current=True) ──优先──> 使用
     └── 不存在 is_current ──回退──> settings.LLM_* / EMBEDDING_* (.env)
```

- 每种类型（`llm` / `embedding`）最多一个 `is_current=True` 的配置
- 服务层每次请求动态创建 API 客户端，配置变更即时生效无需重启
- `ModelConfigHistory` 表记录所有创建/更新/删除/恢复操作，完整审计追溯
- `_normalize_base_url()` 自动兼容不同 API 厂商的 URL 格式（如阿里云 MaaS 的 `/apps/anthropic` → `/compatible-mode/v1`）

### 2.3 文档处理管线：本地规则 + LLM 智能分析双轨制

这是系统最核心的设计。传统 RAG 系统使用固定分块策略处理所有文档，但不同文档（长篇报告 vs 技术手册 vs 对话记录）的结构差异巨大，单一策略效果不稳定。

系统实现了一条 **7 步 SSE 处理管线**，其中 LLM 分析和本地规则分析两条轨道并行：

```
上传文档
  │
  ├─1. 提取 ── pypdf/pdfplumber/DOCX/OCR，提取文本+表格+图片
  ├─2. 清洗评估 ── LLM 评估是否需要清洗（流式输出思考过程）
  ├─3. 执行清洗 ── 规则引擎：Unicode 归一化、PDF 伪影移除、空白行合并
  ├─4. 分块分析 ── LLM 分析文档结构，推荐策略和参数
  ├─5. 执行分块 ── 根据分析结果选择策略执行
  ├─6. 向量存储 ── 批量 50 条 embedding，写入 Milvus + 数据库
  └─7. 完成 ── 保存分析报告
```

**设计考量**：

- **SSE 流式进度** —— 用户可实时看到 LLM 的思考过程和每步结果，而非对着进度条干等。前端 `ProcessAnalysisDialog` 用不同颜色和状态图标区分每步的 pending/thinking/done/error 状态
- **LLM 不可靠时的降级** —— `llm_analyzer.py` 实现了完整的容错链：最多重试 3 次（指数退避 3s/6s）→ JSON 解析失败时修复常见错误（去除 markdown 包裹、修复尾部逗号）→ 仍失败则回退到本地启发式规则
- **本地分析器独立运行** —— `content_analyzer.py` 的 `ContentProfile` 评分体系（层级/结构/叙述/密度四维评分）不依赖外部 LLM，纯本地计算，结果可供前端 `AnalysisDialog` 展示并与 LLM 推荐策略对比
- **后台异步处理** —— 文档上传后立即返回，处理任务提交到后台异步执行，状态持久化到 `ProcessingTask` 表，前端轮询展示进度

### 2.4 分块策略体系：5 种策略覆盖不同文档类型

| 策略 | 适用场景 | 核心机制 |
|------|----------|----------|
| **fixed** | 简单纯文本 | 固定窗口滑动，每步前进 chunk_size - chunk_overlap |
| **recursive** | 通用文本 | LangChain RecursiveCharacterTextSplitter，优先级逐级降级切分：段落→换行→句号→感叹号→问号→分号→空格→字符 |
| **parent_child** | 层级清晰的文档 | 两级切分，父块 4× 大小作为大上下文，子块精准匹配。严格保护 Markdown 表格完整性 |
| **semantic** | 叙述性长文 | 小块切分后向量聚类，余弦相似度 > 0.7 的相邻块合并，最大不超过 chunk_size |
| **hybrid** | 混合结构文档 | 按章节/标题切分后，每个章节独立判断：有子标题→parent_child，长段落→semantic，其他→recursive |

**表格保护机制**是分块体系的关键设计：正则匹配完整 Markdown 表格（表头+分隔线+数据行），超大表格按行拆分（每 1500 字符），处理完表格后重新编号 chunk_index，确保表格数据不会因切分被截断导致检索时信息丢失。

### 2.5 RAG 检索管线：多知识库联合检索 + 对话记忆融合

```
用户问题
  │
  ├── Vectorize ── embed_query(question)
  ├── 多 KB 检索 ── 对每个选中 KB 在 Milvus 中独立搜索 top_k 结果
  ├── 合并排序 ── 跨 KB 合并，按余弦相似度降序，取全局 top_k
  ├── 长期记忆 ── 检索用户历史对话摘要（embedding 余弦相似度），注入相关记忆
  ├── 对话历史 ── 最近 5 轮（10 条消息）格式化为上下文
  ├── 上下文组装 ── 记忆 → KB 检索 → 对话历史 → 当前问题
  └── LLM 生成 ── system prompt 约束仅基于上下文回答 + 引用来源编号
```

**设计考量**：

- **多知识库独立检索后合并** —— 每个 KB 有独立的 Milvus collection（`kb_{id}`），检索时独立查询后按分数合并。这样不同 KB 之间的向量分布互不干扰
- **父子块检索** —— 搜索匹配子块（精准），但展示时优先使用父块（完整上下文），兼顾检索精度和阅读体验
- **长期记忆通过 embedding 相似度检索** —— 而非简单的最近 N 条对话，这样即使用户切换话题后再回来，相关历史对话仍能被召回
- **对话摘要增量更新** —— 每次新消息后自动重新生成摘要并重新 embedding，保持记忆的时效性

### 2.6 流式问答的 SSE 协议设计

系统使用 Server-Sent Events 实现问答的逐 token 流式输出，自定义三阶段事件协议：

```
event: conversation_id    →  { conversation_id: 42 }
event: sources            →  [{ document_name, score, chunk_text }]
event: token              →  { content: "根据" }  (逐 token)
event: token              →  { content: "您" }
...
event: done               →  { status: "complete" }
```

前端 `sources` 事件先于 `token` 事件到达，可在回答开始渲染前展示引用来源卡片。流结束后在服务端收集完整答案保存到数据库，确保对话历史可追溯。

### 2.7 长期记忆系统

不同于简单的"带上最近 N 条对话"，系统实现了一个轻量级长期记忆机制：

1. **摘要生成**：每次对话有新消息后，取前 3 个用户问题（各 100 字符）和前 3 个助手回答（各 100 字符），拼接为结构化摘要
2. **向量化存储**：摘要经 embedding 后存入 `ConversationSummary` 表
3. **相似度召回**：下次有新问题时，计算问题向量与所有历史摘要的余弦相似度，取 top 3
4. **上下文注入**：召回的记忆格式化为 `【相关历史对话】` 块注入 system prompt

这种设计让系统在长对话或跨会话场景中仍能保持对用户历史话题的感知。

---

## 三、功能实现详解

### 3.1 权限管理模块

**数据流**：`POST /auth/login` → JWT token → `Authorization: Bearer <token>` 请求头 → `get_current_user` 解析 → `require_permission(code)` 检查 → 角色-权限并集匹配

**前端菜单过滤**：`AdminLayout` 加载时调用 `/auth/me` 获取用户权限列表，通过 `filteredMenuItems` 按 `permissions.includes(perm)` 递归过滤菜单树。超级管理员看到所有菜单项，不受权限列表限制。

**权限粒度**：
- `menu` 类型控制左侧菜单项的可见性
- `button` 类型控制页面内操作按钮（如上传、删除）
- `api` 类型控制后端接口访问（通过 `require_permission` 依赖注入）

### 3.2 知识库管理模块

**创建知识库**时自动在 Milvus 创建对应 collection（`kb_{id}`），包含 id、embedding（1024 维 FLOAT_VECTOR）、chunk_text、parent_text、metadata、document_id、chunk_index 七个字段。索引采用 IVF_FLAT + COSINE 度量，nlist=128。

**上传文档**流程：校验格式（仅 .pdf/.docx/.txt/.md）→ UUID 重命名保存 → 创建 Document 记录（pending）→ 创建 ProcessingTask 记录 → 启动后台异步处理 → 立即返回（不等处理完成）。

**删除文档**采用数据库优先策略：即使 Milvus 删除失败、文件删除失败，数据库记录仍然会被清理，只记录 warning 日志，不阻断删除流程。

**删除知识库**是三级级联：先删除关联的 ProcessingTask → drop Milvus collection → 删除 KnowledgeBase（SQLAlchemy cascade 自动删除所有 documents 和 chunks）。

### 3.3 文档处理管线

**步骤 1：文本提取** (`document.py:extract_text`)

- PDF：pypdf 提取文本 + pdfplumber 提取表格转 Markdown + pypdf 提取嵌入图片做 OCR（pytesseract, chi_sim+eng）
- DOCX：python-docx 提取段落 + 表格提取 + 内嵌图片 OCR
- TXT/MD：直接读取

**步骤 2-3：清洗评估与执行**

- LLM 取文本前 6000 字符，流式输出 JSON 评估结果
- 规则引擎执行：Unicode 特殊字符（零宽空格、BOM 等）、PDF 伪影（页码正则、断行连字符）、多余空白行合并
- 如果 LLM 调用失败，回退到基于规则的评估

**步骤 4-5：分块分析** (`content_analyzer.py` + `llm_analyzer.py`)

本地分析器 `ContentProfile` 计算四个维度评分：
- **层级分数**（hierarchy_score）：检测标题层级深度（Markdown `#`、中文标题模式 `第X章`、数字层级 `5.1`），层级越深分数越高
- **结构分数**（structure_score）：标题/表格/列表元素的密度
- **叙述分数**（narrative_score）：长句（>30 字）、长段（>300 字）、低标题比例 → 偏向叙述性
- **密度分数**（density_score）：内容类型的多样性

LLM 分析器独立运行，输出推荐的策略和参数。本地和 LLM 两条分析结果在 `AnalysisDialog` 中并排展示，供用户对比参考。

**策略选择决策树**：
1. 短文档（<1000 字）→ recursive
2. 多级标题 + 层级分 >0.3 + 章节平均长度达标 → parent_child
3. 叙述分 >0.45 + 层级分 <0.2（叙述性强但结构弱）→ semantic
4. 高密度 + 结构+叙述达标 + 足够长 → hybrid
5. 含表格但无层级 → hybrid
6. 其他 → recursive（最稳妥的默认策略）

**步骤 6：向量存储**：embedding 服务动态读取当前模型配置，批量 50 条调用 OpenAI 兼容 API，写入 Milvus collection 和 `DocumentChunk` 表，记录 milvus_id 便于追溯。

### 3.4 智能问答模块

**非流式问答** (`POST /chat/query`)：完整 RAG 管线，返回 `{conversation_id, answer, sources}`。

**流式问答** (`POST /chat/stream`)：SSE 协议，逐 token 推送。事件顺序：`conversation_id → sources → token... → done`。前端通过 `fetch` + `ReadableStream` 消费 SSE 流，AbortController 支持取消。

**对话自动管理**：无 `conversation_id` 时自动创建新对话，标题取自问题前 20 字符 + "..."。每次新消息后更新 `conversation.updated_at` 以便按最近活跃排序。

**上下文窗口构建顺序**：
1. `build_system_prompt()` — 6 条行为约束规则
2. `memory_context` — 长期记忆（相关历史对话摘要，top 3）
3. `kb_context` — 知识库检索结果（带编号 [1] [2]...）
4. `chat_history` — 最近 5 轮对话（10 条消息，格式 `角色: 内容`）
5. 当前用户问题

### 3.5 模型配置模块

**设为当前**（`POST /{id}/set-current`）是关键操作：将同类型（llm/embedding）其他配置的 `is_current` 设为 False，当前置为 True。一类型一当前，保证全局唯一。

**配置恢复**（`POST /restore/{history_id}`）：从 `ModelConfigHistory` 快照恢复，若原配置仍存在则更新字段，否则以 `{原名}(已恢复)` 新建。全量快照式审计而非增量变更日志，简化恢复逻辑。

**服务层集成**：`embedding.py` 和 `rag_chain.py` 每次请求创建新的 OpenAI 客户端（通过 `model_config_service.py` 获取当前配置），配置变更无需重启服务即可生效。

### 3.6 处理任务模块

后台任务状态机：`pending → processing → completed/failed`。

前端 `processing-tasks` 页面提供：
- 统计卡片（处理中/已完成/失败的数量）
- 任务列表（支持状态过滤、自动轮询活跃任务 3s 间隔）
- 详情抽屉（展示 7 步的逐步事件，包括 LLM 思考 token 和每步结果）
- 失败任务重试按钮

重试流程：仅 `failed` 状态可重试 → 重置文档和任务状态 → 重新提交后台处理。

### 3.7 对话管理模块

- 对话列表按 `updated_at` 降序（最近活跃在前），显示 `message_count`
- 点击历史对话加载消息时，**同时恢复该对话的知识库选择和领域选择**，保留用户之前的问答上下文
- 对话删除级联删除所有消息和摘要
- 用户隔离：所有对话操作校验 `user_id`，用户只能看到和操作自己的对话

### 3.8 前端设计系统

**设计语言**：暖色调为主的质感知风格。
- 主色 `#e8653a`（暖橙），布局背景 `#f4f3f1`（暖灰），非纯白无彩色系，视觉更柔和
- 全局噪点纹理叠加（SVG fractalNoise，opacity 0.018），增加纸质感
- 字体 DM Sans（英文）优先，中文回退到系统字体
- 组件交互：hover 抬起（translateY -2px）、active 缩放（scale 0.97）、暖色阴影

**自定义组件体系**：
- `.chat-bubble-user`：深底白字，右下角直角+其余大圆角
- `.chat-bubble-assistant`：白底黑字带边框，含 `source-ref` 引用区域（文档名 + 相关度百分比标签）
- `.stat-card`：28px 等宽数字 + 12px 大写标签
- `ProcessAnalysisDialog`：7 步骤左侧状态柱（thinking 橙色脉冲、done 绿色、error 红色），LLM 思考区域暗色背景模拟终端

---

## 附录

### 关键参数速查

| 参数 | 值 | 说明 |
|------|-----|------|
| JWT 过期 | 24h | HS256 签名 |
| Embedding 维度 | 1024 | Qwen3-Embedding-8B |
| Milvus 索引 | IVF_FLAT, COSINE, nlist=128 | 搜索 nprobe=16 |
| 支持格式 | .pdf/.docx/.txt/.md | 最大 100MB |
| 嵌入批处理 | 50 条/批 | — |
| chunk_size 范围 | 200-1500 | LLM 推荐值会被 clamp |
| LLM 重试 | 最多 3 次 | 指数退避 3s/6s |
| LLM 采样截断 | 6000 字符 | 取前一半+后一半 |
| LLM 温度 | 0.2(分析) / 0.3(问答) | — |
| 问答历史窗口 | 最近 5 轮(10 条) | — |
| 长期记忆召回 | top 3 | 余弦相似度 |
| 语义分块阈值 | 相似度 > 0.7 | — |
| API 超时 | 30s(默认) / 120s(chat) | — |
