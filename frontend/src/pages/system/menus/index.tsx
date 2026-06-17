import React, { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Spin,
  Tag,
  Tree,
  message,
} from 'antd';
import {
  ApartmentOutlined,
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
  DeleteOutlined,
  DeploymentUnitOutlined,
  EditOutlined,
  FileTextOutlined,
  FolderOutlined,
  GlobalOutlined,
  HolderOutlined,
  HomeOutlined,
  KeyOutlined,
  MenuOutlined,
  MessageOutlined,
  PartitionOutlined,
  PlusOutlined,
  ProfileOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  ScheduleOutlined,
  SearchOutlined,
  SettingOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  ToolOutlined,
  UserOutlined,
} from '@ant-design/icons';
import {
  createPermission,
  deletePermission,
  getPermissionTree,
  reorderPermissions,
  updatePermission,
} from '@/services/api';

interface MenuItem {
  id: number;
  code: string;
  name: string;
  type: string;
  parent_id: number | null;
  path?: string | null;
  icon?: string | null;
  sort_order: number;
  is_active: boolean;
  children?: MenuItem[];
}

const iconOptions = [
  { value: 'HomeOutlined', icon: <HomeOutlined /> },
  { value: 'AppstoreOutlined', icon: <AppstoreOutlined /> },
  { value: 'MenuOutlined', icon: <MenuOutlined /> },
  { value: 'DatabaseOutlined', icon: <DatabaseOutlined /> },
  { value: 'FolderOutlined', icon: <FolderOutlined /> },
  { value: 'FileTextOutlined', icon: <FileTextOutlined /> },
  { value: 'MessageOutlined', icon: <MessageOutlined /> },
  { value: 'GlobalOutlined', icon: <GlobalOutlined /> },
  { value: 'RobotOutlined', icon: <RobotOutlined /> },
  { value: 'ThunderboltOutlined', icon: <ThunderboltOutlined /> },
  { value: 'SettingOutlined', icon: <SettingOutlined /> },
  { value: 'UserOutlined', icon: <UserOutlined /> },
  { value: 'TeamOutlined', icon: <TeamOutlined /> },
  { value: 'SafetyCertificateOutlined', icon: <SafetyCertificateOutlined /> },
  { value: 'ToolOutlined', icon: <ToolOutlined /> },
  { value: 'ControlOutlined', icon: <ControlOutlined /> },
  { value: 'BarChartOutlined', icon: <BarChartOutlined /> },
  { value: 'DashboardOutlined', icon: <DashboardOutlined /> },
  { value: 'ProfileOutlined', icon: <ProfileOutlined /> },
  { value: 'PartitionOutlined', icon: <PartitionOutlined /> },
  { value: 'ClusterOutlined', icon: <ClusterOutlined /> },
  { value: 'DeploymentUnitOutlined', icon: <DeploymentUnitOutlined /> },
  { value: 'CloudOutlined', icon: <CloudOutlined /> },
  { value: 'ApiOutlined', icon: <ApiOutlined /> },
  { value: 'KeyOutlined', icon: <KeyOutlined /> },
  { value: 'AuditOutlined', icon: <AuditOutlined /> },
  { value: 'ScheduleOutlined', icon: <ScheduleOutlined /> },
  { value: 'BellOutlined', icon: <BellOutlined /> },
  { value: 'SearchOutlined', icon: <SearchOutlined /> },
];

const iconMap = iconOptions.reduce<Record<string, React.ReactNode>>((map, item) => {
  map[item.value] = item.icon;
  return map;
}, {});

const IconPicker: React.FC<{ value?: string; onChange?: (value: string) => void }> = ({ value, onChange }) => (
  <div className="menu-icon-picker">
    {iconOptions.map((item) => (
      <button
        key={item.value}
        type="button"
        className={`menu-icon-choice ${value === item.value ? 'menu-icon-choice-active' : ''}`}
        onClick={() => onChange?.(item.value)}
        title={item.value}
      >
        {item.icon}
      </button>
    ))}
  </div>
);

const filterMenus = (items: MenuItem[] = []): MenuItem[] =>
  items
    .filter((item) => item.type === 'menu')
    .map((item) => ({
      ...item,
      parent_id: item.parent_id ?? null,
      children: filterMenus(item.children || []),
    }))
    .sort((a, b) => a.sort_order - b.sort_order);

const flattenMenus = (items: MenuItem[], parentId: number | null = null) => {
  const result: Array<{ id: number; parent_id: number | null; sort_order: number }> = [];
  items.forEach((item, index) => {
    result.push({ id: item.id, parent_id: parentId, sort_order: index + 1 });
    result.push(...flattenMenus(item.children || [], item.id));
  });
  return result;
};

const getAllMenus = (items: MenuItem[]): MenuItem[] =>
  items.flatMap((item) => [item, ...getAllMenus(item.children || [])]);

const findNode = (items: MenuItem[], key: number): MenuItem | undefined => {
  for (const item of items) {
    if (item.id === key) return item;
    const child = findNode(item.children || [], key);
    if (child) return child;
  }
  return undefined;
};

const collectDescendantIds = (item: MenuItem): Set<number> =>
  new Set(getAllMenus(item.children || []).map((child) => child.id));

const removeNode = (items: MenuItem[], key: number): { next: MenuItem[]; node?: MenuItem } => {
  let removed: MenuItem | undefined;
  const next = items
    .map((item) => {
      if (item.id === key) {
        removed = item;
        return null;
      }
      const childResult = removeNode(item.children || [], key);
      if (childResult.node) {
        removed = childResult.node;
        return { ...item, children: childResult.next };
      }
      return item;
    })
    .filter(Boolean) as MenuItem[];

  return { next, node: removed };
};

const insertNode = (
  items: MenuItem[],
  dropKey: number,
  node: MenuItem,
  dropToGap: boolean,
  dropPosition: number,
): MenuItem[] => {
  if (!dropToGap) {
    return items.map((item) => {
      if (item.id === dropKey) {
        return { ...item, children: [node, ...(item.children || [])] };
      }
      return { ...item, children: insertNode(item.children || [], dropKey, node, dropToGap, dropPosition) };
    });
  }

  const dropIndex = items.findIndex((item) => item.id === dropKey);
  if (dropIndex >= 0) {
    const next = [...items];
    next.splice(dropPosition < 0 ? dropIndex : dropIndex + 1, 0, node);
    return next;
  }

  return items.map((item) => ({
    ...item,
    children: insertNode(item.children || [], dropKey, node, dropToGap, dropPosition),
  }));
};

const MenuManagementPage: React.FC = () => {
  const [menus, setMenus] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingOrder, setSavingOrder] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingMenu, setEditingMenu] = useState<MenuItem | null>(null);
  const [form] = Form.useForm();

  const flatMenus = useMemo(() => getAllMenus(menus), [menus]);

  const fetchMenus = async () => {
    setLoading(true);
    try {
      const res = await getPermissionTree();
      setMenus(filterMenus(res.data));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMenus();
  }, []);

  const openCreate = (parentId?: number) => {
    setEditingMenu(null);
    form.resetFields();
    form.setFieldsValue({
      type: 'menu',
      parent_id: parentId ?? null,
      icon: 'MenuOutlined',
      is_active: true,
    });
    setModalOpen(true);
  };

  const openEdit = (menu: MenuItem) => {
    setEditingMenu(menu);
    form.setFieldsValue({
      code: menu.code,
      name: menu.name,
      parent_id: menu.parent_id,
      path: menu.path,
      icon: menu.icon,
      is_active: menu.is_active,
    });
    setModalOpen(true);
  };

  const handleSubmit = async (values: any) => {
    const payload = {
      ...values,
      type: 'menu',
      parent_id: values.parent_id ?? null,
      sort_order: editingMenu?.sort_order ?? flatMenus.length + 1,
    };

    try {
      if (editingMenu) {
        await updatePermission(editingMenu.id, payload);
        message.success('菜单已更新');
      } else {
        await createPermission(payload);
        message.success('菜单已创建');
      }
      setModalOpen(false);
      fetchMenus();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '保存失败');
    }
  };

  const handleDelete = async (menu: MenuItem) => {
    if (menu.children?.length) {
      message.warning('请先删除或移动子菜单');
      return;
    }

    try {
      await deletePermission(menu.id);
      message.success('菜单已删除');
      fetchMenus();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '删除失败');
    }
  };

  const handleDrop = async (info: any) => {
    const dragKey = Number(info.dragNode.key);
    const dropKey = Number(info.node.key);
    const dropPosition = info.dropPosition - Number(info.node.pos.split('-').pop());
    const previousMenus = menus;
    const draggedNode = findNode(menus, dragKey);

    if (!draggedNode) return;
    if (collectDescendantIds(draggedNode).has(dropKey)) {
      message.warning('不能把菜单移动到自己的子菜单下');
      return;
    }

    const removed = removeNode(menus, dragKey);
    if (!removed.node) return;

    const nextMenus = insertNode(removed.next, dropKey, removed.node, info.dropToGap, dropPosition);
    setMenus(nextMenus);
    setSavingOrder(true);

    try {
      const res = await reorderPermissions(flattenMenus(nextMenus));
      setMenus(filterMenus(res.data));
      message.success('菜单位置已保存');
    } catch (err: any) {
      setMenus(previousMenus);
      message.error(err.response?.data?.detail || '菜单排序保存失败');
    } finally {
      setSavingOrder(false);
    }
  };

  const treeData = menus.map(function toTreeNode(menu): any {
    return {
      key: menu.id,
      title: (
        <div className="menu-tree-row">
          <div className="menu-tree-main">
            <HolderOutlined className="menu-tree-drag" />
            <span className="menu-tree-icon">{iconMap[menu.icon || ''] || <MenuOutlined />}</span>
            <div>
              <div className="menu-tree-title">
                {menu.name}
                {!menu.is_active && <Tag>停用</Tag>}
              </div>
              <div className="menu-tree-meta">
                <span>{menu.code}</span>
                {menu.path && <span>{menu.path}</span>}
              </div>
            </div>
          </div>
          <Space size={4} onClick={(event) => event.stopPropagation()}>
            <Button type="text" size="small" icon={<PlusOutlined />} onClick={() => openCreate(menu.id)} className="action-icon-button" />
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEdit(menu)} className="action-icon-button" />
            <Popconfirm
              title="确认删除此菜单？"
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => handleDelete(menu)}
            >
              <Button type="text" size="small" icon={<DeleteOutlined />} className="danger-icon-button" />
            </Popconfirm>
          </Space>
        </div>
      ),
      children: (menu.children || []).map(toTreeNode),
    };
  });

  const disabledParentIds = editingMenu
    ? new Set([editingMenu.id, ...collectDescendantIds(editingMenu)])
    : new Set<number>();

  const parentOptions = flatMenus
    .filter((menu) => !disabledParentIds.has(menu.id))
    .map((menu) => ({ label: menu.name, value: menu.id }));

  return (
    <>
      <div className="page-header">
        <div>
          <h2>菜单管理</h2>
          <div className="page-desc">通过拖拽调整菜单层级与展示顺序</div>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openCreate()} style={{ borderRadius: 8 }}>
          新增菜单
        </Button>
      </div>

      <div className="content-panel menu-management-panel">
        <div className="menu-management-toolbar">
          <div>
            <div className="menu-management-title">
              <ApartmentOutlined /> 菜单结构
            </div>
            <div className="menu-management-desc">拖动左侧手柄可改变菜单位置，保存会自动完成。</div>
          </div>
          {savingOrder && <Tag color="processing">保存排序中</Tag>}
        </div>

        {loading ? (
          <div className="menu-management-loading">
            <Spin />
          </div>
        ) : menus.length === 0 ? (
          <Empty description="暂无菜单" style={{ padding: '64px 0' }} />
        ) : (
          <Tree
            blockNode
            draggable
            defaultExpandAll
            treeData={treeData}
            onDrop={handleDrop}
            className="menu-tree"
          />
        )}
      </div>

      <Modal
        title={editingMenu ? '编辑菜单' : '新增菜单'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        okText={editingMenu ? '保存' : '创建'}
        cancelText="取消"
        destroyOnHidden
        width={560}
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical" style={{ marginTop: 20 }}>
          <Form.Item name="name" label="菜单名称" rules={[{ required: true, message: '请输入菜单名称' }]}>
            <Input placeholder="例如：菜单管理" />
          </Form.Item>
          <Form.Item name="code" label="权限编码" rules={[{ required: true, message: '请输入权限编码' }]}>
            <Input placeholder="例如：system:menu" disabled={!!editingMenu} />
          </Form.Item>
          <Form.Item name="path" label="路由路径" rules={[{ required: true, message: '请输入路由路径' }]}>
            <Input placeholder="例如：/system/menus" />
          </Form.Item>
          <Form.Item name="parent_id" label="上级菜单">
            <Select allowClear placeholder="顶级菜单" options={parentOptions} />
          </Form.Item>
          <Form.Item name="icon" label="图标">
            <IconPicker />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default MenuManagementPage;
