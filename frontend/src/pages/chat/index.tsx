import React, { useState, useRef, useEffect } from 'react';
import { Input, Button, Select, Space, Typography, Divider, Spin, Tag } from 'antd';
import {
  SendOutlined, MessageOutlined, BookOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons';
import { getKnowledgeBases, getDomains, chatQuery } from '@/services/api';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: any[];
}

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [kbs, setKbs] = useState<any[]>([]);
  const [domains, setDomains] = useState<any[]>([]);
  const [selectedKbs, setSelectedKbs] = useState<number[]>([]);
  const [selectedDomain, setSelectedDomain] = useState<number | undefined>();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<any>(null);

  useEffect(() => {
    getKnowledgeBases().then(res => setKbs(res.data.filter((kb: any) => kb.is_active)));
    getDomains().then(res => setDomains(res.data));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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
        domain_id: selectedDomain,
        top_k: 5,
      });

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
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100dvh - 120px)' }}>
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
          icon={<ArrowRightOutlined />}
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
  );
};

export default ChatPage;
