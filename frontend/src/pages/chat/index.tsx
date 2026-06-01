import React, { useState, useRef, useEffect } from 'react';
import { Card, Input, Button, Select, Space, List, Typography, Tag, Divider, Spin, Empty } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons';
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
        content: '抱歉，查询出错：' + (err.response?.data?.detail || err.message),
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)' }}>
      <Card size="small" style={{ marginBottom: 12 }}>
        <Space wrap>
          <span>知识库：</span>
          <Select
            mode="multiple"
            style={{ minWidth: 300 }}
            placeholder="选择知识库"
            value={selectedKbs}
            onChange={setSelectedKbs}
            options={kbs.map(kb => ({ label: kb.name, value: kb.id }))}
          />
          <span>领域：</span>
          <Select
            style={{ width: 150 }}
            placeholder="选择领域"
            value={selectedDomain}
            onChange={setSelectedDomain}
            allowClear
            options={domains.map(d => ({ label: d.name, value: d.id }))}
          />
        </Space>
      </Card>

      <Card style={{ flex: 1, overflow: 'auto' }} bodyStyle={{ padding: '16px', overflow: 'auto' }}>
        {messages.length === 0 ? (
          <Empty description="选择知识库后开始提问" style={{ marginTop: 100 }} />
        ) : (
          <List
            dataSource={messages}
            renderItem={(msg) => (
              <List.Item style={{
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                borderBottom: 'none', padding: '8px 0',
              }}>
                <div style={{
                  maxWidth: '75%',
                  background: msg.role === 'user' ? '#1677ff' : '#f5f5f5',
                  color: msg.role === 'user' ? '#fff' : '#000',
                  padding: '12px 16px',
                  borderRadius: 12,
                }}>
                  <Space style={{ marginBottom: 4 }}>
                    {msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                    <Text strong style={{ color: msg.role === 'user' ? '#fff' : '#000' }}>
                      {msg.role === 'user' ? '我' : 'AI 助手'}
                    </Text>
                  </Space>
                  <Paragraph style={{ whiteSpace: 'pre-wrap', margin: 0, color: 'inherit' }}>
                    {msg.content}
                  </Paragraph>
                  {msg.sources && msg.sources.length > 0 && (
                    <>
                      <Divider style={{ margin: '8px 0', borderColor: '#ddd' }} />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        📚 参考来源 ({msg.sources.length})
                      </Text>
                      {msg.sources.map((s: any, i: number) => (
                        <div key={i} style={{ fontSize: 12, marginTop: 4, opacity: 0.8 }}>
                          [{i + 1}] {s.document_name} - 分块#{s.chunk_index} (相关度: {(s.score * 100).toFixed(1)}%)
                        </div>
                      ))}
                    </>
                  )}
                </div>
              </List.Item>
            )}
          />
        )}
        {loading && <Spin tip="思考中..." style={{ display: 'block', textAlign: 'center', padding: 20 }} />}
        <div ref={messagesEndRef} />
      </Card>

      <Card size="small" style={{ marginTop: 12 }}>
        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="输入问题..."
            autoSize={{ minRows: 1, maxRows: 4 }}
            onPressEnter={e => { if (!e.shiftKey) { e.preventDefault(); handleSend(); } }}
            disabled={loading}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={loading}
            disabled={!input.trim() || selectedKbs.length === 0}
            style={{ height: 'auto' }}
          >
            发送
          </Button>
        </Space.Compact>
      </Card>
    </div>
  );
};

export default ChatPage;
