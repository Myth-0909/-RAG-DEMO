# Project Memory

## 固定规则

- **编码前必须先使用 /karpathy-guidelines skill**：遵循 Think Before Coding、Simplicity First、Surgical Changes、Goal-Driven Execution 原则

## 技术栈

- 后端：FastAPI + SQLAlchemy + LangChain
- 前端：React + Vite + Ant Design
- 向量库：Milvus（172.16.0.44:19530）
- 数据库：SQLite（本地开发）

## 项目结构

- 后端入口：`backend/app/main.py`
- 前端入口：`frontend/src/main.tsx`
- 模型配置：`backend/.env`（EMBEDDING + LLM）
- 知识库管理：`backend/app/api/v1/knowledge.py`
- 智能问答：`backend/app/api/v1/chat.py`
- 对话管理：`backend/app/api/v1/conversations.py`

## 开发环境

- Python 3.11 + venv
- Node.js 18 + npm
- 后端端口：8000
- 前端端口：3000

## 已实现功能

### 智能内容分析与分块策略选择（2026-06-01）

**核心重构：内容驱动的策略选择**
- 新增 `hierarchy_score`：衡量标题层级深度，而非仅计算标题数量
  - `#` > `##` > `###` = 真正的层级结构
  - 全部 `##` = 扁平列表，不适合父子分块
- 新增 `avg_section_chars`：确保章节有足够内容支撑父子分块
- 降低标题/章节密度系数，防止评分膨胀
- `parent_child` 现在需要：
  - `heading_levels >= 2` AND
  - `hierarchy_score >= 0.3` AND
  - `avg_section_chars > 150`
- 扁平文档（单层标题）正确降级为 `recursive`
- DOCX 编号段落不再被误识别为章节标题

**实际文档测试结果：**
- RAG_01.md (H1+H2, 27标题): `parent_child` ✅
- RAG_02.md (H1+H2, avg 69字符/节): `recursive` ✅
- 公司规章制度表.docx (无MD标题): `recursive` ✅
- 三层层级文档 (H1>H2>H3): `parent_child` ✅
- 纯叙事文档: `semantic` ✅

### 多轮对话与长期记忆（2026-06-01）

**后端实现：**
- 数据库表：Conversation、ChatMessage、ConversationSummary
- 对话管理 API：创建、列表、获取消息、删除
- Chat API 支持 conversation_id 参数
- RAG Chain 集成对话历史上下文
- 对话摘要向量化和长期记忆检索

**前端实现：**
- 左侧对话列表（创建/切换/删除）
- 加载历史消息
- 消息持久化到后端
- 对话 API 调用

**核心特性：**
- 多轮对话上下文感知
- 通过对话摘要实现长期记忆
- 记忆检索增强 RAG 回答
- 跨会话持久化对话历史
