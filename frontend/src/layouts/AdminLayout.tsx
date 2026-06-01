import React, { useEffect, useState, useMemo } from 'react';
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

// 所有菜单项及其所需权限
const allMenuItems = [
  {
    key: '/knowledge',
    icon: <DatabaseOutlined />,
    label: '知识库',
    permission: 'knowledge',
  },
  {
    key: '/chat',
    icon: <MessageOutlined />,
    label: '智能问答',
    permission: 'chat',
  },
  {
    key: '/domain',
    icon: <GlobalOutlined />,
    label: '专业领域',
    permission: 'domain',
  },
  {
    key: '/system',
    icon: <SettingOutlined />,
    label: '系统',
    permission: 'system',
    children: [
      { key: '/system/users', icon: <UserOutlined />, label: '用户管理', permission: 'system:user' },
      { key: '/system/roles', icon: <TeamOutlined />, label: '角色管理', permission: 'system:role' },
    ],
  },
];

const AdminLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [userName, setUserName] = useState('管理员');
  const [isSuperuser, setIsSuperuser] = useState(false);
  const [permissions, setPermissions] = useState<string[]>([]);

  useEffect(() => {
    const info = getUserInfo();
    if (info) {
      setUserName(info.full_name || info.username);
      setIsSuperuser(info.is_superuser || false);
      setPermissions(info.permissions || []);
    }
    getMe().then((res) => {
      setUserName(res.data.full_name || res.data.username);
      setIsSuperuser(res.data.is_superuser || false);
      setPermissions(res.data.permissions || []);
      setUserInfo(res.data);
    }).catch(() => {});
  }, []);

  // 根据权限过滤菜单
  const filteredMenuItems = useMemo(() => {
    const hasPermission = (perm: string) => isSuperuser || permissions.includes(perm);

    return allMenuItems
      .filter(item => hasPermission(item.permission))
      .map(item => {
        if (item.children) {
          const filteredChildren = item.children.filter(child => hasPermission(child.permission));
          if (filteredChildren.length === 0) return null;
          return { ...item, children: filteredChildren };
        }
        return item;
      })
      .filter(Boolean);
  }, [isSuperuser, permissions]);

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
          items={filteredMenuItems}
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
