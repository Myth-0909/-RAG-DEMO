import React, { useEffect, useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Avatar, Dropdown, theme, Space, Typography } from 'antd';
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
    label: '知识库管理',
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
    label: '系统管理',
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
  const { token: { colorBgContainer, borderRadiusLG } } = theme.useToken();

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
    <Layout style={{ minHeight: '100vh' }}>
      <Sider trigger={null} collapsible collapsed={collapsed} theme="dark">
        <div style={{
          height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontSize: collapsed ? 14 : 18, fontWeight: 'bold',
        }}>
          {collapsed ? 'RAG' : 'RAG 知识库'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={['/system']}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{
          padding: '0 24px', background: colorBgContainer,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <Space>
            {React.createElement(collapsed ? MenuUnfoldOutlined : MenuFoldOutlined, {
              onClick: () => setCollapsed(!collapsed),
              style: { fontSize: 18, cursor: 'pointer' },
            })}
          </Space>
          <Dropdown menu={{ items: userMenuItems }}>
            <Space style={{ cursor: 'pointer' }}>
              <Avatar icon={<UserOutlined />} />
              <Text>{userName}</Text>
            </Space>
          </Dropdown>
        </Header>
        <Content style={{ margin: 24, padding: 24, background: colorBgContainer, borderRadius: borderRadiusLG, overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AdminLayout;
