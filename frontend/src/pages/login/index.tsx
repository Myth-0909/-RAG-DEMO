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
    <div className="login-shell">
      <div className="login-brand-panel">
        <div className="login-brand-content">
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
              background: '#3f6f8f',
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
              letterSpacing: 0,
            }}>RAG System</span>
          </div>

          <h1 className="login-title">
            知识库<br />管理平台
          </h1>
          <p className="login-copy">
            管理文档、分块策略、模型连接和领域提示词，让团队用同一个知识底座回答复杂问题。
          </p>
        </div>

        <div className="login-metrics" style={{
          display: 'flex',
          gap: 32,
        }}>
          {[
            { label: '向量引擎', value: 'Milvus' },
            { label: 'Embedding', value: 'Qwen3' },
            { label: '分块策略', value: '5种' },
          ].map((item) => (
            <div key={item.label}>
              <div style={{
                fontSize: 22,
                fontWeight: 760,
                color: '#f8fbfd',
                letterSpacing: 0,
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

      <div className="login-form-panel">
        <div style={{ marginBottom: 40 }}>
          <h2 style={{
            fontSize: 28,
            fontWeight: 760,
            letterSpacing: 0,
            color: '#202a34',
            margin: 0,
          }}>登录</h2>
          <p style={{
            fontSize: 14,
            color: '#7d8a96',
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
            label={<span style={{ fontWeight: 600, fontSize: 13, color: '#667482' }}>用户名</span>}
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input
              placeholder="admin"
              style={{ height: 44, borderRadius: 10 }}
            />
          </Form.Item>
          <Form.Item
            name="password"
            label={<span style={{ fontWeight: 600, fontSize: 13, color: '#667482' }}>密码</span>}
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
          color: '#96a2ae',
          textAlign: 'center',
        }}>
          默认账号 admin / admin123
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
