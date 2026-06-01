import React from 'react';
import { Form, Input, Button, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import { login } from '@/services/api';
import { setToken } from '@/utils/auth';

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = React.useState(false);

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const res = await login(values);
      setToken(res.data.access_token);
      message.success('登录成功');
      navigate('/knowledge');
    } catch (err: any) {
      message.error(err.response?.data?.detail || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100dvh',
      display: 'grid',
      gridTemplateColumns: '1fr 420px',
      background: '#f4f3f1',
    }}>
      {/* Left panel — brand area */}
      <div style={{
        background: '#1c1b19',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '48px 56px',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Subtle radial glow */}
        <div style={{
          position: 'absolute',
          width: 500,
          height: 500,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(232,101,58,0.12) 0%, transparent 70%)',
          bottom: -120,
          right: -80,
          pointerEvents: 'none',
        }} />

        <div>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            marginBottom: 80,
          }}>
            <div style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: '#e8653a',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: 15,
              color: '#fff',
            }}>R</div>
            <span style={{
              fontSize: 16,
              fontWeight: 600,
              color: 'rgba(255,255,255,0.9)',
              letterSpacing: '-0.01em',
            }}>RAG System</span>
          </div>

          <h1 style={{
            fontSize: 36,
            fontWeight: 700,
            lineHeight: 1.2,
            letterSpacing: '-0.03em',
            color: '#fff',
            margin: 0,
          }}>
            知识库<br />管理平台
          </h1>
          <p style={{
            fontSize: 15,
            lineHeight: 1.7,
            color: 'rgba(255,255,255,0.45)',
            marginTop: 20,
            maxWidth: 340,
          }}>
            基于向量检索与 RAG 技术的企业级知识管理解决方案。支持多种文档格式、智能分块策略与多领域专业问答。
          </p>
        </div>

        <div style={{
          display: 'flex',
          gap: 32,
          position: 'relative',
          zIndex: 1,
        }}>
          {[
            { label: '向量引擎', value: 'Milvus' },
            { label: 'Embedding', value: 'Qwen3' },
            { label: '分块策略', value: '4种' },
          ].map((item) => (
            <div key={item.label}>
              <div style={{
                fontSize: 22,
                fontWeight: 700,
                color: '#fff',
                letterSpacing: '-0.02em',
                fontVariantNumeric: 'tabular-nums',
              }}>{item.value}</div>
              <div style={{
                fontSize: 11,
                fontWeight: 500,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                color: 'rgba(255,255,255,0.3)',
                marginTop: 4,
              }}>{item.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel — login form */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        padding: '48px 48px',
      }}>
        <div style={{ marginBottom: 40 }}>
          <h2 style={{
            fontSize: 24,
            fontWeight: 700,
            letterSpacing: '-0.02em',
            color: '#1a1a1a',
            margin: 0,
          }}>登录</h2>
          <p style={{
            fontSize: 14,
            color: '#8a8580',
            marginTop: 8,
          }}>输入你的账号以继续</p>
        </div>

        <Form
          onFinish={onFinish}
          layout="vertical"
          requiredMark={false}
          size="large"
        >
          <Form.Item
            name="username"
            label={<span style={{ fontWeight: 500, fontSize: 13, color: '#6b6560' }}>用户名</span>}
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input
              placeholder="admin"
              style={{ height: 44, borderRadius: 10 }}
            />
          </Form.Item>
          <Form.Item
            name="password"
            label={<span style={{ fontWeight: 500, fontSize: 13, color: '#6b6560' }}>密码</span>}
            rules={[{ required: true, message: '请输入密码' }]}
            style={{ marginBottom: 32 }}
          >
            <Input.Password
              placeholder="输入密码"
              style={{ height: 44, borderRadius: 10 }}
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{
                height: 46,
                borderRadius: 10,
                fontWeight: 600,
                fontSize: 15,
              }}
            >
              登录
            </Button>
          </Form.Item>
        </Form>

        <div style={{
          marginTop: 40,
          fontSize: 12,
          color: '#a09a94',
          textAlign: 'center',
        }}>
          默认账号 admin / admin123
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
