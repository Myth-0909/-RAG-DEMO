---
name: multi-turn-conversation-memory
description: RAG 系统中多轮对话持久化和长期记忆检索的完整实现模式
source: auto-skill
extracted_at: '2026-06-01T05:51:36.355Z'
---

# 多轮对话与长期记忆实现

## 核心问题

RAG 系统默认每次问答独立，无法：
1. 理解对话上下文（"刚才提到的那个概念..."）
2. 跨会话保持历史（刷新页面丢失对话）
3. 利用历史知识增强新对话

## 解决方案架构

```
┌─────────────────────────────────────────────────────────┐
│  前端                                                    │
│  - 对话列表（左侧）                                      │
│  - 消息历史（右侧）                                      │
│  - conversation_id 传递                                  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Chat API                                                │
│  - 保存用户消息                                          │
│  - 加载对话历史                                          │
│  - 检索长期记忆                                          │
│  - 调用 RAG Chain                                        │
│  - 保存助手回复                                          │
│  - 更新对话摘要                                          │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  RAG Chain                                               │
│  - 接收 chat_history 参数                                │
│  - 接收 memory_context 参数                              │
│  - 构建完整上下文（知识库 + 历史 + 记忆）                │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  数据库                                                  │
│  - conversations（对话元数据）                           │
│  - chat_messages（消息历史）                             │
│  - conversation_summaries（向量化摘要）                  │
└─────────────────────────────────────────────────────────┘
```

## 数据库 Schema 设计

### 1. conversations 表

```python
class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    knowledge_base_ids = Column(JSON)  # [1, 2, 3]
    domain_id = Column(Integer, ForeignKey("domains.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    messages = relationship("ChatMessage", back_populates="conversation", 
                          cascade="all, delete-orphan")
```

**设计要点**：
- `knowledge_base_ids` 用 JSON 存储，支持多知识库
- `updated_at` 自动更新，用于排序
- 级联删除关联消息

### 2. chat_messages 表

```python
class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True)  # 引用的知识库来源
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversation = relationship("Conversation", back_populates="messages")
```

**设计要点**：
- `sources` 存储检索到的文档片段（用于溯源）
- 按 `created_at` 排序保证消息顺序

### 3. conversation_summaries 表（长期记忆）

```python
class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    summary = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=False)  # 向量化摘要
    created_at = Column(DateTime, default=datetime.utcnow)
```

**设计要点**：
- `embedding` 用 JSON 存储向量（SQLite 不支持原生向量类型）
- 每次对话更新时重新生成摘要

## Chat API 实现模式

### 消息保存函数

```python
def save_message(db: Session, conversation_id: int, role: str, content: str, sources: list = None):
    """保存消息到对话历史"""
    message = ChatMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sources=sources
    )
    db.add(message)
    
    # 更新对话的更新时间（用于排序）
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation:
        conversation.updated_at = datetime.utcnow()
    
    db.commit()
```

### 获取或创建对话

```python
def get_or_create_conversation(
    db: Session,
    user_id: int,
    conversation_id: int = None,
    knowledge_base_ids: list = None,
    domain_id: int = None,
    question: str = None
) -> Conversation:
    """获取现有对话或创建新对话"""
    if conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="对话不存在")
        return conversation
    
    # 创建新对话，使用问题前20个字符作为标题
    title = question[:20] + "..." if len(question) > 20 else question
    conversation = Conversation(
        user_id=user_id,
        title=title,
        knowledge_base_ids=knowledge_base_ids or [],
        domain_id=domain_id
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation
```

### Chat API 端点

```python
@router.post("/query")
async def chat_query(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. 获取或创建对话
    conversation = get_or_create_conversation(
        db=db,
        user_id=current_user.id,
        conversation_id=request.conversation_id,
        knowledge_base_ids=request.knowledge_base_ids,
        domain_id=request.domain_id,
        question=request.question
    )
    
    # 2. 保存用户消息
    save_message(db, conversation.id, "user", request.question)
    
    # 3. 加载对话历史
    chat_history = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation.id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    history_messages = [
        {"role": msg.role, "content": msg.content}
        for msg in chat_history[:-1]  # 不包含刚保存的用户消息
    ]
    
    # 4. 检索长期记忆
    memories = retrieve_relevant_memories(
        db=db,
        user_id=current_user.id,
        query=request.question,
        top_k=3
    )
    memory_context = build_memory_context(memories)
    
    # 5. 执行 RAG 查询
    result = await rag_query(
        question=request.question,
        knowledge_base_ids=request.knowledge_base_ids,
        domain_id=request.domain_id,
        top_k=request.top_k,
        db=db,
        chat_history=history_messages,
        memory_context=memory_context
    )
    
    # 6. 保存助手回复
    save_message(db, conversation.id, "assistant", result["answer"], result.get("sources"))
    
    # 7. 更新对话摘要
    update_conversation_summary_on_message(db, conversation.id, current_user.id)
    
    return {
        "conversation_id": conversation.id,
        "answer": result["answer"],
        "sources": result["sources"]
    }
```

## RAG Chain 集成对话历史

### 修改 rag_query 签名

```python
async def rag_query(
    question: str,
    knowledge_base_ids: List[int],
    domain_id: int = None,
    top_k: int = 5,
    db: Session = None,
    chat_history: List[Dict[str, str]] = None,  # 新增
    memory_context: str = "",                    # 新增
) -> Dict[str, Any]:
```

### 构建完整上下文

```python
def build_chat_history_text(chat_history: List[Dict[str, str]] = None, max_turns: int = 5) -> str:
    """构建对话历史文本"""
    if not chat_history:
        return ""
    
    # 只取最近的几轮对话（避免 token 过长）
    recent_history = chat_history[-max_turns * 2:]
    
    parts = []
    for msg in recent_history:
        role = "用户" if msg["role"] == "user" else "助手"
        parts.append(f"{role}: {msg['content']}")
    
    return "\n".join(parts)

# 在 rag_query 中
history_text = build_chat_history_text(chat_history)

user_message_parts = []
if memory_context:
    user_message_parts.append(memory_context)
if history_text:
    user_message_parts.append(f"对话历史：\n{history_text}")
user_message_parts.append(f"上下文信息：\n{context}")
user_message_parts.append(f"用户问题：{question}")

user_message = "\n\n".join(user_message_parts)
```

## 长期记忆服务实现

### 生成对话摘要

```python
def generate_conversation_summary(messages: List[Dict[str, str]]) -> str:
    """生成对话摘要（简单版本）"""
    if not messages:
        return ""
    
    user_questions = [m["content"] for m in messages if m["role"] == "user"]
    assistant_answers = [m["content"] for m in messages if m["role"] == "assistant"]
    
    summary_parts = []
    if user_questions:
        summary_parts.append("用户讨论的主题：" + "；".join(user_questions[:3]))
    if assistant_answers:
        key_points = [a[:100] for a in assistant_answers[:3]]
        summary_parts.append("关键信息：" + "；".join(key_points))
    
    return " | ".join(summary_parts)
```

### 保存摘要并生成向量

```python
def save_conversation_summary(
    db: Session,
    user_id: int,
    conversation_id: int,
    summary: str,
) -> Optional[ConversationSummary]:
    """保存对话摘要并生成向量"""
    if not summary.strip():
        return None
    
    try:
        # 生成摘要的向量
        embedding = embed_texts([summary])[0]
        
        # 检查是否已存在该对话的摘要
        existing = db.query(ConversationSummary).filter(
            ConversationSummary.conversation_id == conversation_id
        ).first()
        
        if existing:
            existing.summary = summary
            existing.embedding = embedding
            db.commit()
            db.refresh(existing)
            return existing
        
        # 创建新的摘要记录
        cs = ConversationSummary(
            user_id=user_id,
            conversation_id=conversation_id,
            summary=summary,
            embedding=embedding,
        )
        db.add(cs)
        db.commit()
        db.refresh(cs)
        return cs
    except Exception as e:
        logger.error(f"Failed to save conversation summary: {e}")
        db.rollback()
        return None
```

### 检索相关记忆

```python
def retrieve_relevant_memories(
    db: Session,
    user_id: int,
    query: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """检索与当前查询相关的历史对话摘要"""
    try:
        # 获取该用户的所有对话摘要
        summaries = db.query(ConversationSummary).filter(
            ConversationSummary.user_id == user_id
        ).all()
        
        if not summaries:
            return []
        
        # 对查询进行向量化
        query_embedding = embed_query(query)
        
        # 计算相似度并排序
        scored_memories = []
        for summary in summaries:
            if not summary.embedding:
                continue
            
            similarity = cosine_similarity(query_embedding, summary.embedding)
            scored_memories.append({
                "summary": summary.summary,
                "conversation_id": summary.conversation_id,
                "similarity": similarity,
                "created_at": summary.created_at,
            })
        
        scored_memories.sort(key=lambda x: x["similarity"], reverse=True)
        return scored_memories[:top_k]
    except Exception as e:
        logger.error(f"Failed to retrieve memories: {e}")
        return []

def build_memory_context(memories: List[Dict[str, Any]]) -> str:
    """构建记忆上下文文本"""
    if not memories:
        return ""
    
    parts = ["【相关历史对话】"]
    for i, mem in enumerate(memories, 1):
        parts.append(f"{i}. {mem['summary']} (相关度: {mem['similarity']:.2f})")
    
    return "\n".join(parts)
```

## 前端实现模式

### 对话列表组件

```typescript
interface Conversation {
  id: number;
  title: string;
  message_count: number;
  updated_at: string;
}

const [conversations, setConversations] = useState<Conversation[]>([]);
const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);

const loadConversations = async () => {
  const res = await getConversations();
  setConversations(res.data);
};

const loadConversationMessages = async (conversationId: number) => {
  const res = await getConversationMessages(conversationId);
  const msgs: Message[] = res.data.map((m: any) => ({
    role: m.role,
    content: m.content,
    sources: m.sources,
  }));
  setMessages(msgs);
  setCurrentConversationId(conversationId);
};
```

### 发送消息时传递 conversation_id

```typescript
const handleSend = async () => {
  const res = await chatQuery({
    question: input,
    knowledge_base_ids: selectedKbs,
    conversation_id: currentConversationId,  // 关键：传递对话 ID
    domain_id: selectedDomain,
    top_k: 5,
  });
  
  // 更新当前对话 ID（首次提问时）
  if (res.data.conversation_id && !currentConversationId) {
    setCurrentConversationId(res.data.conversation_id);
    loadConversations();  // 刷新对话列表
  }
  
  // 更新消息
  setMessages(prev => [...prev, assistantMsg]);
};
```

## 关键设计决策

### 1. 何时保存消息？

**用户消息**：调用 RAG 之前立即保存  
**助手回复**：RAG 返回完整回答后保存

**原因**：
- 用户消息必须先保存，才能在 `chat_history` 中体现
- 助手回复需要等待完整生成（尤其是流式输出）

### 2. 对话历史传递多少轮？

**建议**：最近 5 轮（10 条消息）

**原因**：
- 避免 token 过长导致成本增加
- 大多数对话只需要近期上下文
- 长期记忆通过摘要向量检索补充

### 3. 摘要何时更新？

**策略**：每次助手回复后更新

**原因**：
- 保持摘要与对话同步
- 避免遗漏重要信息
- 异步更新不影响响应速度

### 4. 记忆检索的相似度阈值？

**建议**：不设阈值，返回 top_k 并标注相似度

**原因**：
- 让 LLM 自行判断相关性
- 相似度数值供用户参考
- 避免硬性阈值导致信息丢失

## 常见问题与解决

### 问题：对话历史导致 token 超限

**解决**：限制历史轮数 + 压缩消息内容

```python
# 只取每条消息的前 500 字符
for msg in recent_history:
    content = msg['content'][:500] + "..." if len(msg['content']) > 500 else msg['content']
    parts.append(f"{role}: {content}")
```

### 问题：流式输出时无法保存完整回复

**解决**：在流式结束后保存

```python
full_answer = []

async def event_generator():
    yield {"event": "conversation_id", "data": json.dumps({"conversation_id": conversation.id})}
    
    async for event in rag_query_stream(...):
        if event["type"] == "token":
            full_answer.append(event["data"]["content"])
        yield event
    
    # 流式结束后保存
    save_message(db, conversation.id, "assistant", "".join(full_answer))
```

### 问题：对话摘要质量差

**改进方案**：
1. 使用 LLM 生成摘要（成本高但质量好）
2. 提取关键实体和关系
3. 结合用户反馈优化

```python
def generate_summary_with_llm(messages: List[Dict]) -> str:
    prompt = "请总结以下对话的关键信息和结论：\n\n"
    for msg in messages:
        prompt += f"{msg['role']}: {msg['content']}\n"
    
    response = llm_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200
    )
    return response.choices[0].message.content
```

## 性能优化建议

1. **索引优化**：
   - `conversations.user_id` 添加索引
   - `chat_messages.conversation_id` 添加索引
   - `conversation_summaries.user_id` 添加索引

2. **批量操作**：
   - 批量加载对话列表（分页）
   - 批量删除消息（级联删除）

3. **缓存策略**：
   - 缓存对话摘要向量（避免重复计算）
   - 缓存最近对话的消息（Redis）

4. **异步处理**：
   - 摘要生成异步执行
   - 记忆检索并行于知识库检索

## 适用场景

- ✅ 需要跨会话保持对话历史
- ✅ 用户经常在同一对话中追问细节
- ✅ 需要利用历史知识增强新对话
- ✅ 多用户系统（每个用户独立对话）

## 不适用场景

- ❌ 一次性问答（无需历史）
- ❌ 对隐私要求极高（不能存储对话）
- ❌ 实时性要求极高（摘要生成有延迟）
