import React, { useEffect, useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Avatar, Dropdown, Space, Typography } from 'antd';
import {
  DatabaseOutlined,
  MessageOutlined,
  SettingOutlined,
  UserOutlined,
  TeamOutlined,
  GlobalOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { getMe } from '@/services/api';
import { removeToken, setUserInfo, getUserInfo } from '@/utils/auth';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const menuItems = [
  {
    key: '/knowledge',
    icon: <DatabaseOutlined />,
    label: '知识库',
  },
  {
    key: '/chat',
    icon: <MessageOutlined />,
    label: '智能问答',
  },
  {
    key: '/domain',
    icon: <GlobalOutlined />,
    label: '专业领域',
  },
  {
    key: '/system',
    icon: <SettingOutlined />,
    label: '系统',
    children: [
      { key: '/system/users', icon: <UserOutlined />, label: '用户管理' },
      { key: '/system/roles', icon: <TeamOutlined />, label: '角色管理' },
    ],
  },
];

const AdminLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [userName, setUserName] = useState('管理员');

  useEffect(() => {
    const info = getUserInfo();
    if (info) {
      setUserName(info.full_name || info.username);
    }
    getMe().then((res) => {
      setUserName(res.data.full_name || res.data.username);
      setUserInfo(res.data);
    }).catch(() => {});
  }, []);

  const handleLogout = () => {
    removeToken();
    navigate('/login');
  };

  const userMenuItems = [
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', onClick: handleLogout },
  ];

  return (
    <Layout style={{ minHeight: '100dvh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={220}
        collapsedWidth={64}
        className="admin-sider"
        style={{
          borderRight: 'none',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
        }}
      >
        <div className="sider-logo">
          <div className="logo-mark">R</div>
          {!collapsed && <span className="logo-text">RAG System</span>}
        </div>

        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={collapsed ? [] : ['/system']}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{
            marginTop: 8,
            borderRight: 'none',
            fontSize: 13,
          }}
        />
      </Sider>

      <Layout style={{ marginLeft: collapsed ? 64 : 220, transition: 'margin-left 0.2s ease' }}>
        <Header style={{
          height: 56,
          lineHeight: '56px',
          padding: '0 28px',
          background: '#fff',
          borderBottom: '1px solid #eae8e4',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          zIndex: 50,
        }}>
          <button
            onClick={() => setCollapsed(!collapsed)}
            style={{
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              fontSize: 16,
              color: '#6b6560',
              padding: '6px 8px',
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = '#f4f3f1')}
            onMouseLeave={e => (e.currentTarget.style.background = 'none')}
          >
            {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </button>

          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Space
              style={{
                cursor: 'pointer',
                padding: '4px 12px 4px 4px',
                borderRadius: 20,
                transition: 'background 0.2s',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f4f3f1')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              <Avatar
                size={30}
                style={{
                  background: '#e8653a',
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                {userName?.[0]?.toUpperCase()}
              </Avatar>
              <Text style={{
                fontSize: 13,
                fontWeight: 500,
                color: '#1a1a1a',
              }}>{userName}</Text>
            </Space>
          </Dropdown>
        </Header>

        <Content style={{
          padding: '28px 28px 40px',
          minHeight: 'calc(100dvh - 56px)',
          background: '#f4f3f1',
        }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AdminLayout;
