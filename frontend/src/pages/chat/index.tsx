import React, { useState, useRef, useEffect } from 'react';
import { Input, Button, Select, Space, Typography, Spin, Tag, List, Popconfirm } from 'antd';
import {
  SendOutlined, MessageOutlined, BookOutlined,
  PlusOutlined, DeleteOutlined,
} from '@ant-design/icons';
import {
  getKnowledgeBases, getDomains, chatQuery,
  getConversations, getConversationMessages, deleteConversation
} from '@/services/api';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: any[];
}

interface Conversation {
  id: number;
  title: string;
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
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<any>(null);

  useEffect(() => {
    getKnowledgeBases().then(res => setKbs(res.data.filter((kb: any) => kb.is_active)));
    getDomains().then(res => setDomains(res.data));
    loadConversations();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadConversations = async () => {
    try {
      const res = await getConversations();
      setConversations(res.data);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  };

  const loadConversationMessages = async (conversationId: number) => {
    try {
      const res = await getConversationMessages(conversationId);
      const msgs: Message[] = res.data.map((m: any) => ({
        role: m.role,
        content: m.content,
        sources: m.sources,
      }));
      setMessages(msgs);
      setCurrentConversationId(conversationId);
    } catch (err) {
      console.error('Failed to load messages:', err);
    }
  };

  const handleNewConversation = () => {
    setCurrentConversationId(null);
    setMessages([]);
  };

  const handleDeleteConversation = async (id: number) => {
    try {
      await deleteConversation(id);
      if (currentConversationId === id) {
        handleNewConversation();
      }
      loadConversations();
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || selectedKbs.length === 0) return;

    const userMsg: Message = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await chatQuery({
        question: input,
        knowledge_base_ids: selectedKbs,
        conversation_id: currentConversationId,
        domain_id: selectedDomain,
        top_k: 5,
      });

      // 更新当前对话 ID
      if (res.data.conversation_id && !currentConversationId) {
        setCurrentConversationId(res.data.conversation_id);
        loadConversations();
      }

      const assistantMsg: Message = {
        role: 'assistant',
        content: res.data.answer,
        sources: res.data.sources,
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err: any) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '查询出错：' + (err.response?.data?.detail || err.message),
      }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div style={{ display: 'flex', gap: 16, height: 'calc(100dvh - 120px)' }}>
      {/* 左侧对话列表 */}
      <div style={{
        width: 280,
        background: '#fff',
        borderRadius: 12,
        border: '1px solid #eae8e4',
        display: 'flex',
        flexDirection: 'column',
      }}>
        <div style={{ padding: '16px', borderBottom: '1px solid #eae8e4' }}>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleNewConversation}
            block
            style={{ borderRadius: 8 }}
          >
            新对话
          </Button>
        </div>
        <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
          <List
            dataSource={conversations}
            renderItem={(conv) => (
              <List.Item
                style={{
                  padding: '12px',
                  borderRadius: 8,
                  cursor: 'pointer',
                  background: currentConversationId === conv.id ? '#f5f5f5' : 'transparent',
                  border: 'none',
                }}
                onClick={() => loadConversationMessages(conv.id)}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 14,
                    fontWeight: 500,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                    {conv.title}
                  </div>
                  <div style={{ fontSize: 12, color: '#8a8580', marginTop: 4 }}>
                    {conv.message_count} 条消息
                  </div>
                </div>
                <Popconfirm
                  title="确定删除此对话？"
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
                    style={{ color: '#8a8580' }}
                  />
                </Popconfirm>
              </List.Item>
            )}
          />
        </div>
      </div>

      {/* 右侧聊天区域 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Config bar */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '12px 16px',
          background: '#fff',
          borderRadius: 12,
          border: '1px solid #eae8e4',
          marginBottom: 16,
          flexWrap: 'wrap',
        }}>
          <BookOutlined style={{ color: '#e8653a', fontSize: 15 }} />
          <Select
            mode="multiple"
            style={{ minWidth: 260, flex: 1 }}
            placeholder="选择知识库"
            value={selectedKbs}
            onChange={setSelectedKbs}
            options={kbs.map(kb => ({ label: kb.name, value: kb.id }))}
            maxTagCount="responsive"
          />
          <div style={{ width: 1, height: 24, background: '#eae8e4' }} />
          <span style={{ fontSize: 12, color: '#8a8580', fontWeight: 500 }}>领域</span>
          <Select
            style={{ width: 140 }}
            placeholder="通用"
            value={selectedDomain}
            onChange={setSelectedDomain}
            allowClear
            options={domains.map(d => ({ label: d.name, value: d.id }))}
          />
        </div>

        {/* Messages area */}
        <div style={{
          flex: 1,
          overflow: 'auto',
          background: '#fff',
          borderRadius: 12,
          border: '1px solid #eae8e4',
          padding: '24px 28px',
        }}>
          {messages.length === 0 ? (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: '#a09a94',
            }}>
              <div style={{
                width: 64,
                height: 64,
                borderRadius: 16,
                background: '#f4f3f1',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: 20,
              }}>
                <MessageOutlined style={{ fontSize: 24, color: '#c4c0ba' }} />
              </div>
              <div style={{
                fontSize: 16,
                fontWeight: 600,
                color: '#6b6560',
                marginBottom: 6,
              }}>
                开始对话
              </div>
              <div style={{
                fontSize: 13,
                color: '#a09a94',
                textAlign: 'center',
                maxWidth: 300,
                lineHeight: 1.6,
              }}>
                选择一个或多个知识库，输入问题开始基于向量检索的智能问答
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  }}
                >
                  <div className={msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'}>
                    {msg.role === 'assistant' && (
                      <div style={{
                        fontSize: 11,
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        color: '#e8653a',
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
                          color: '#6b6560',
                        }}>
                          参考来源
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                          {msg.sources.map((s: any, i: number) => (
                            <div key={i} style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 6,
                              fontSize: 12,
                            }}>
                              <span style={{
                                color: '#8a8580',
                                fontVariantNumeric: 'tabular-nums',
                              }}>[{i + 1}]</span>
                              <span style={{ color: '#1a1a1a', fontWeight: 500 }}>
                                {s.document_name}
                              </span>
                              <Tag style={{
                                fontSize: 10,
                                padding: '0 5px',
                                background: '#f4f3f1',
                                border: 'none',
                                color: '#8a8580',
                                borderRadius: 3,
                              }}>
                                {(s.score * 100).toFixed(1)}%
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
                  color: '#8a8580',
                  fontSize: 13,
                }}>
                  <Spin size="small" />
                  <span>检索中...</span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div style={{
          marginTop: 12,
          background: '#fff',
          borderRadius: 12,
          border: '1px solid #eae8e4',
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'flex-end',
          gap: 12,
        }}>
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
      </div>
    </div>
  );
};

export default ChatPage;
