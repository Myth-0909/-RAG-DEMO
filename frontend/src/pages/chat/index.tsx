import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Input, Button, Select, Spin, Tag, List, Popconfirm, message, Empty, Drawer } from 'antd';
import {
  SendOutlined, MessageOutlined, BookOutlined,
  PlusOutlined, DeleteOutlined, DatabaseOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import {
  getKnowledgeBases, getDomains, chatQuery,
  getConversations, getConversationMessages, deleteConversation
} from '@/services/api';

const { TextArea } = Input;

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: any[];
  isError?: boolean;
}

interface Conversation {
  id: number;
  title: string;
  knowledge_base_ids: number[];
  domain_id: number | null;
  message_count: number;
  updated_at: string;
}

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [kbs, setKbs] = useState<any[]>([]);
  const [domains, setDomains] = useState<any[]>([]);
  const [selectedKbs, setSelectedKbs] = useState<number[]>([]);
  const [selectedDomain, setSelectedDomain] = useState<number | undefined>();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
  const [sourceDetail, setSourceDetail] = useState<any>(null);
  const [sourceDrawerOpen, setSourceDrawerOpen] = useState(false);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [searchMode, setSearchMode] = useState<string>('hybrid');
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<any>(null);

  const currentConversation = useMemo(
    () => conversations.find((conv) => conv.id === currentConversationId),
    [conversations, currentConversationId],
  );

  useEffect(() => {
    getKnowledgeBases().then(res => setKbs(res.data.filter((kb: any) => kb.is_active)));
    getDomains().then(res => setDomains(res.data));
    loadConversations();
  }, []);

  const scrollMessagesToBottom = (behavior: ScrollBehavior = 'smooth') => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const container = messagesContainerRef.current;
        if (!container) return;
        container.scrollTo({
          top: container.scrollHeight,
          behavior,
        });
      });
    });
  };

  useEffect(() => {
    scrollMessagesToBottom('smooth');
  }, [messages]);

  const loadConversations = async () => {
    setConversationLoading(true);
    try {
      const res = await getConversations();
      setConversations(res.data);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setConversationLoading(false);
    }
  };

  const loadConversationMessages = async (conv: Conversation) => {
    if (loading) return;
    try {
      const res = await getConversationMessages(conv.id);
      const msgs: Message[] = res.data.map((m: any) => ({
        role: m.role,
        content: m.content,
        sources: m.sources,
      }));
      setMessages(msgs);
      setCurrentConversationId(conv.id);
      setSelectedKbs(conv.knowledge_base_ids || []);
      setSelectedDomain(conv.domain_id ?? undefined);
      scrollMessagesToBottom('auto');
    } catch (err) {
      console.error('Failed to load messages:', err);
      message.error('无法加载此对话');
    }
  };

  const handleNewConversation = (showTip = true) => {
    setCurrentConversationId(null);
    setMessages([]);
    setInput('');
    if (showTip) message.success('已切换到新对话');
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  const handleDeleteConversation = async (id: number) => {
    try {
      await deleteConversation(id);
      if (currentConversationId === id) {
        handleNewConversation(false);
      }
      message.success('已删除对话');
      loadConversations();
    } catch (err) {
      console.error('Failed to delete conversation:', err);
      message.error('删除对话失败');
    }
  };

  const handleSend = async () => {
    const question = input.trim();
    if (!question) return;
    if (selectedKbs.length === 0) {
      message.warning('请先选择知识库');
      return;
    }

    const userMsg: Message = { role: 'user', content: question };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await chatQuery({
        question,
        knowledge_base_ids: selectedKbs,
        conversation_id: currentConversationId,
        domain_id: selectedDomain,
        top_k: 5,
        search_mode: searchMode,
      });

      // 更新当前对话 ID
      if (res.data.conversation_id && !currentConversationId) {
        setCurrentConversationId(res.data.conversation_id);
      }

      const assistantMsg: Message = {
        role: 'assistant',
        content: res.data.answer,
        sources: res.data.sources,
      };
      setMessages(prev => [...prev, assistantMsg]);
      loadConversations();
    } catch (err: any) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '查询失败：' + (err.response?.data?.detail || err.message),
        isError: true,
      }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div className="chat-shell">
      <aside className="chat-sidebar">
        <div className="chat-sidebar-head">
          <div className="chat-sidebar-title">
            <span>对话</span>
            <span>{conversations.length}</span>
          </div>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => handleNewConversation()}
            block
            className="chat-new-button"
          >
            新对话
          </Button>
        </div>
        <div className="conversation-list">
          <List
            loading={conversationLoading}
            dataSource={conversations}
            locale={{
              emptyText: (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="暂无历史对话"
                />
              ),
            }}
            renderItem={(conv) => (
              <List.Item
                className={`conversation-item ${currentConversationId === conv.id ? 'conversation-item-active' : ''}`}
                style={{ borderBlockEnd: 'none' }}
                onClick={() => loadConversationMessages(conv)}
              >
                <div className="conversation-content">
                  <div className="conversation-title">{conv.title}</div>
                  <div className="conversation-meta">
                    <span>{conv.message_count} 条消息</span>
                  </div>
                </div>
                <Popconfirm
                  title="确定删除此对话？"
                  okText="删除"
                  cancelText="取消"
                  okButtonProps={{ danger: true }}
                  onConfirm={(e) => {
                    e?.stopPropagation();
                    handleDeleteConversation(conv.id);
                  }}
                  onCancel={(e) => e?.stopPropagation()}
                >
                  <Button
                    type="text"
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={(e) => e.stopPropagation()}
                    className="danger-icon-button conversation-delete"
                  />
                </Popconfirm>
              </List.Item>
            )}
          />
        </div>
      </aside>

      <main className="chat-main">
        <div className="chat-workspace-header">
          <div>
            <div className="chat-kicker">智能问答</div>
            <h2 className="chat-title">{currentConversation?.title || '新对话'}</h2>
          </div>
          <div className="chat-meta">
            <span><DatabaseOutlined /> {selectedKbs.length || 0} 个知识库</span>
            <span>{selectedDomain ? '已选择领域' : '通用领域'}</span>
          </div>
        </div>

        <div className="chat-config">
          <BookOutlined style={{ color: '#3f6f8f', fontSize: 15 }} />
          <Select
            mode="multiple"
            style={{ minWidth: 260, flex: 1 }}
            placeholder="选择知识库"
            value={selectedKbs}
            onChange={setSelectedKbs}
            options={kbs.map(kb => ({ label: kb.name, value: kb.id }))}
            maxTagCount="responsive"
          />
          <div style={{ width: 1, height: 24, background: '#d9e1e8' }} />
          <span style={{ fontSize: 12, color: '#667482', fontWeight: 700 }}>领域</span>
          <Select
            style={{ width: 140 }}
            placeholder="通用"
            value={selectedDomain}
            onChange={setSelectedDomain}
            allowClear
            options={domains.map(d => ({ label: d.name, value: d.id }))}
          />
          <div style={{ width: 1, height: 24, background: '#d9e1e8' }} />
          <span style={{ fontSize: 12, color: '#667482', fontWeight: 700 }}>检索</span>
          <Select
            style={{ width: 130 }}
            value={searchMode}
            onChange={setSearchMode}
            options={[
              { label: '混合检索', value: 'hybrid' },
              { label: '向量检索', value: 'vector' },
              { label: '关键词检索', value: 'keyword' },
            ]}
          />
        </div>

        <div className="chat-messages" ref={messagesContainerRef}>
          {messages.length === 0 ? (
            <div className="chat-empty">
              <div className="chat-empty-icon">
                <MessageOutlined style={{ fontSize: 24, color: '#3f6f8f' }} />
              </div>
              <div className="chat-empty-title">
                开始对话
              </div>
              <div className="chat-empty-desc">
                {selectedKbs.length > 0
                  ? '输入问题后，系统会检索知识库并附上来源。'
                  : '先选择一个或多个知识库，再开始提问。'}
              </div>
            </div>
          ) : (
            <div className="chat-thread">
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`chat-message-row ${msg.role === 'user' ? 'chat-message-row-user' : 'chat-message-row-assistant'}`}
                >
                  <div className={msg.role === 'user' ? 'chat-bubble-user' : `chat-bubble-assistant ${msg.isError ? 'chat-bubble-error' : ''}`}>
                    {msg.role === 'assistant' && (
                      <div style={{
                        fontSize: 11,
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        color: '#3f6f8f',
                        marginBottom: 8,
                      }}>
                        回答
                      </div>
                    )}
                    <div style={{
                      whiteSpace: 'pre-wrap',
                      lineHeight: 1.7,
                      fontSize: 14,
                    }}>
                      {msg.content}
                    </div>
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="source-ref">
                        <div style={{
                          fontSize: 11,
                          fontWeight: 600,
                          textTransform: 'uppercase',
                          letterSpacing: '0.06em',
                          marginBottom: 8,
                          color: '#667482',
                        }}>
                          参考来源
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                          {msg.sources.map((s: any, i: number) => (
                            <div
                              key={i}
                              onClick={() => { setSourceDetail(s); setSourceDrawerOpen(true); }}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6,
                                fontSize: 12,
                                cursor: 'pointer',
                                padding: '4px 6px',
                                borderRadius: 6,
                                transition: 'background 0.15s',
                              }}
                              onMouseEnter={(e) => {
                                (e.currentTarget as HTMLElement).style.background = '#f0f4f8';
                              }}
                              onMouseLeave={(e) => {
                                (e.currentTarget as HTMLElement).style.background = 'transparent';
                              }}
                            >
                              <span style={{
                                color: '#7d8a96',
                                fontVariantNumeric: 'tabular-nums',
                              }}>[{i + 1}]</span>
                              <span style={{ color: '#202a34', fontWeight: 500 }}>
                                {s.document_name}
                              </span>
                              <Tag style={{
                                fontSize: 10,
                                padding: '0 5px',
                                background: '#f1f5f8',
                                border: 'none',
                                color: '#7d8a96',
                                borderRadius: 3,
                              }}>
                                {typeof s.score === 'number' ? `${(s.score * 100).toFixed(1)}%` : '来源'}
                              </Tag>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {loading && (
            <div style={{
              display: 'flex',
              justifyContent: 'flex-start',
              marginTop: 20,
            }}>
              <div className="chat-bubble-assistant">
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  color: '#7d8a96',
                  fontSize: 13,
                }}>
                  <Spin size="small" />
                  <span>检索中...</span>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="chat-input-bar">
          <TextArea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={selectedKbs.length > 0 ? '输入你的问题...' : '请先选择知识库'}
            autoSize={{ minRows: 1, maxRows: 4 }}
            onPressEnter={e => {
              if (!e.shiftKey) { e.preventDefault(); handleSend(); }
            }}
            disabled={loading || selectedKbs.length === 0}
            style={{
              border: 'none',
              boxShadow: 'none',
              padding: '4px 0',
              fontSize: 14,
              resize: 'none',
            }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={loading}
            disabled={!input.trim() || selectedKbs.length === 0}
            style={{
              borderRadius: 10,
              height: 38,
              width: 38,
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          />
        </div>
      </main>

      {/* Source chunk detail drawer */}
      <Drawer
        open={sourceDrawerOpen}
        onClose={() => setSourceDrawerOpen(false)}
        width={560}
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileTextOutlined style={{ color: '#3f6f8f' }} />
            <span style={{ fontWeight: 600 }}>检索来源详情</span>
          </div>
        }
      >
        {sourceDetail && (
          <div>
            <div style={{
              background: '#f8fafc',
              border: '1px solid #d9e1e8',
              borderRadius: 10,
              padding: '14px 16px',
              marginBottom: 20,
            }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#667482' }}>文档</span>
                  <span style={{ fontWeight: 500, color: '#202a34' }}>{sourceDetail.document_name}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#667482' }}>分块序号</span>
                  <span style={{ fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>#{sourceDetail.chunk_index}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#667482' }}>相关性</span>
                  <Tag style={{
                    fontSize: 11, border: 'none',
                    color: '#3f6f8f', background: '#e9f0f5',
                  }}>
                    {typeof sourceDetail.score === 'number'
                      ? `${(sourceDetail.score * 100).toFixed(1)}%`
                      : '—'}
                  </Tag>
                </div>
                {sourceDetail.metadata && Object.keys(sourceDetail.metadata).length > 0 && (
                  <>
                    <div style={{ borderTop: '1px solid #e7edf2', margin: '4px 0' }} />
                    {Object.entries(sourceDetail.metadata).map(([k, v]) => (
                      <div key={k} style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: '#667482' }}>{k}</span>
                        <span style={{ fontWeight: 500, color: '#202a34', maxWidth: '60%', textAlign: 'right' }}>
                          {typeof v === 'boolean' ? (v ? '是' : '否') : String(v)}
                        </span>
                      </div>
                    ))}
                  </>
                )}
              </div>
            </div>

            <div style={{
              fontSize: 12,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: '#667482',
              marginBottom: 10,
            }}>
              完整分块内容
            </div>
            <pre style={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontFamily: '"SF Mono", "Fira Code", monospace',
              fontSize: 13,
              lineHeight: 1.7,
              color: '#2c2c2c',
              background: '#faf9f7',
              padding: 16,
              borderRadius: 8,
              border: '1px solid #eee',
              maxHeight: 'calc(100vh - 380px)',
              overflowY: 'auto',
              margin: 0,
            }}>
              {sourceDetail.text}
            </pre>
          </div>
        )}
      </Drawer>
    </div>
  );
};

export default ChatPage;
