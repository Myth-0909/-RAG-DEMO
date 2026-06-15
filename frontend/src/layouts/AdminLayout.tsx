import React, { useEffect, useState, useMemo } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Avatar, Dropdown, Space, Typography } from 'antd';
import {
  ApiOutlined,
  AppstoreOutlined,
  AuditOutlined,
  BarChartOutlined,
  BellOutlined,
  CloudOutlined,
  ClusterOutlined,
  ControlOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  DeploymentUnitOutlined,
  FileTextOutlined,
  FolderOutlined,
  MessageOutlined,
  SettingOutlined,
  UserOutlined,
  TeamOutlined,
  GlobalOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MenuOutlined,
  RobotOutlined,
  ThunderboltOutlined,
  HomeOutlined,
  KeyOutlined,
  PartitionOutlined,
  ProfileOutlined,
  SafetyCertificateOutlined,
  ScheduleOutlined,
  SearchOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import { getMe, getVisibleMenuTree } from '@/services/api';
import { removeToken, setUserInfo, getUserInfo } from '@/utils/auth';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const iconMap: Record<string, React.ReactNode> = {
  ApiOutlined: <ApiOutlined />,
  AppstoreOutlined: <AppstoreOutlined />,
  AuditOutlined: <AuditOutlined />,
  BarChartOutlined: <BarChartOutlined />,
  BellOutlined: <BellOutlined />,
  CloudOutlined: <CloudOutlined />,
  ClusterOutlined: <ClusterOutlined />,
  ControlOutlined: <ControlOutlined />,
  DashboardOutlined: <DashboardOutlined />,
  DatabaseOutlined: <DatabaseOutlined />,
  DeploymentUnitOutlined: <DeploymentUnitOutlined />,
  FileTextOutlined: <FileTextOutlined />,
  FolderOutlined: <FolderOutlined />,
  GlobalOutlined: <GlobalOutlined />,
  HomeOutlined: <HomeOutlined />,
  KeyOutlined: <KeyOutlined />,
  MenuOutlined: <MenuOutlined />,
  MessageOutlined: <MessageOutlined />,
  PartitionOutlined: <PartitionOutlined />,
  ProfileOutlined: <ProfileOutlined />,
  RobotOutlined: <RobotOutlined />,
  SafetyCertificateOutlined: <SafetyCertificateOutlined />,
  ScheduleOutlined: <ScheduleOutlined />,
  SearchOutlined: <SearchOutlined />,
  SettingOutlined: <SettingOutlined />,
  TeamOutlined: <TeamOutlined />,
  ThunderboltOutlined: <ThunderboltOutlined />,
  ToolOutlined: <ToolOutlined />,
  UserOutlined: <UserOutlined />,
};

const staticMenuItems = [
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
    key: '/model-config',
    icon: <RobotOutlined />,
    label: '模型配置',
    permission: 'model_config',
  },
  {
    key: '/processing-tasks',
    icon: <ThunderboltOutlined />,
    label: '处理任务',
    permission: 'processing_tasks',
  },
  {
    key: '/system',
    icon: <SettingOutlined />,
    label: '系统',
    permission: 'system',
    children: [
      { key: '/system/users', icon: <UserOutlined />, label: '用户管理', permission: 'system:user' },
      { key: '/system/roles', icon: <TeamOutlined />, label: '角色管理', permission: 'system:role' },
      { key: '/system/menus', icon: <MenuOutlined />, label: '菜单管理', permission: 'system:menu' },
    ],
  },
];

const routeIconFallback: Record<string, React.ReactNode> = {
  '/knowledge': <DatabaseOutlined />,
  '/chat': <MessageOutlined />,
  '/domain': <GlobalOutlined />,
  '/model-config': <RobotOutlined />,
  '/processing-tasks': <ThunderboltOutlined />,
  '/system': <SettingOutlined />,
  '/system/users': <UserOutlined />,
  '/system/roles': <TeamOutlined />,
  '/system/menus': <MenuOutlined />,
};

const toMenuItems = (items: any[]): any[] =>
  items
    .filter((item) => item.path)
    .map((item) => ({
      key: item.path,
      icon: iconMap[item.icon] || routeIconFallback[item.path] || <MenuOutlined />,
      label: item.name,
      children: item.children?.length ? toMenuItems(item.children) : undefined,
    }));

const collectMenuKeys = (items: any[]): Set<string> => {
  const keys = new Set<string>();
  const walk = (menuItems: any[]) => {
    menuItems.forEach((item) => {
      keys.add(item.key);
      if (item.children?.length) walk(item.children);
    });
  };
  walk(items);
  return keys;
};

const mergeMissingMenuItems = (
  serverItems: any[],
  fallbackItems: any[],
  existingKeys = collectMenuKeys(serverItems),
): any[] => {
  const fallbackByKey = new Map(fallbackItems.map((item: any) => [item.key, item]));

  const merged = serverItems.map((item: any) => {
    const fallback = fallbackByKey.get(item.key);
    if (!fallback?.children) return item;
    return {
      ...item,
      children: mergeMissingMenuItems(item.children || [], fallback.children, existingKeys),
    };
  });

  const mergedKeys = new Set(merged.map((item: any) => item.key));
  fallbackItems.forEach((item: any) => {
    if (!mergedKeys.has(item.key) && !existingKeys.has(item.key)) {
      merged.push(item);
      existingKeys.add(item.key);
    }
  });

  return merged;
};

const findAncestorKeys = (items: any[], targetKey: string, parents: string[] = []): string[] => {
  for (const item of items) {
    if (item.key === targetKey) return parents;
    if (item.children?.length) {
      const result = findAncestorKeys(item.children, targetKey, [...parents, item.key]);
      if (result.length > 0) return result;
    }
  }
  return [];
};

const AdminLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [userName, setUserName] = useState('管理员');
  const [isSuperuser, setIsSuperuser] = useState(false);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [serverMenuItems, setServerMenuItems] = useState<any[]>([]);
  const [openKeys, setOpenKeys] = useState<string[]>([]);

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
    getVisibleMenuTree()
      .then((res) => setServerMenuItems(toMenuItems(res.data)))
      .catch(() => setServerMenuItems([]));
  }, []);

  // 根据权限过滤菜单
  const filteredMenuItems = useMemo(() => {
    const hasPermission = (perm: string) => isSuperuser || permissions.includes(perm);

    const fallbackItems = staticMenuItems
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

    if (serverMenuItems.length === 0) {
      return fallbackItems;
    }

    return mergeMissingMenuItems(serverMenuItems, fallbackItems);
  }, [isSuperuser, permissions, serverMenuItems]);

  useEffect(() => {
    if (collapsed) {
      setOpenKeys([]);
      return;
    }
    const ancestors = findAncestorKeys(filteredMenuItems, location.pathname);
    setOpenKeys((current) => Array.from(new Set([...current, ...ancestors])));
  }, [collapsed, filteredMenuItems, location.pathname]);

  const handleLogout = () => {
    removeToken();
    navigate('/login');
  };

  const userMenuItems = [
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', onClick: handleLogout },
  ];

  return (
    <Layout className="admin-shell">
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
          openKeys={openKeys}
          onOpenChange={(keys) => setOpenKeys(keys as string[])}
          items={filteredMenuItems}
          onClick={({ key }) => navigate(key)}
          style={{
            marginTop: 8,
            borderRight: 'none',
            fontSize: 13,
          }}
        />
      </Sider>

      <Layout className="admin-layout" style={{ marginLeft: collapsed ? 64 : 220 }}>
        <Header className="admin-header">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="icon-button-plain"
          >
            {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </button>

          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Space className="user-trigger">
              <Avatar
                size={30}
                style={{
                  background: '#3f6f8f',
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                {userName?.[0]?.toUpperCase()}
              </Avatar>
              <Text style={{
                fontSize: 13,
                fontWeight: 600,
                color: '#202a34',
              }}>{userName}</Text>
            </Space>
          </Dropdown>
        </Header>

        <Content className="admin-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AdminLayout;
