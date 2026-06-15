import React, { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Tree, Space, Tag, message, Popconfirm } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, TeamOutlined } from '@ant-design/icons';
import { getRoles, createRole, updateRole, deleteRole, getPermissionTree } from '@/services/api';

const RolePage: React.FC = () => {
  const [roles, setRoles] = useState<any[]>([]);
  const [permTree, setPermTree] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [checkedKeys, setCheckedKeys] = useState<number[]>([]);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const [roleRes, permRes] = await Promise.all([getRoles(), getPermissionTree()]);
      setRoles(roleRes.data);
      setPermTree(permRes.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const treeData = permTree.map(function toTreeNode(p: any): any {
    return {
      title: (
        <span style={{ fontSize: 13 }}>
          {p.name}
          <span style={{ color: '#96a2ae', fontSize: 11, marginLeft: 6 }}>
            {p.type === 'menu' ? '菜单' : p.type === 'button' ? '按钮' : '接口'}
          </span>
        </span>
      ),
      key: p.id,
      children: p.children?.map(toTreeNode) || [],
    };
  });

  const handleSubmit = async (values: any) => {
    try {
      const data = { ...values, permission_ids: checkedKeys };
      if (editingId) {
        await updateRole(editingId, data);
        message.success('已更新');
      } else {
        await createRole(data);
        message.success('已创建');
      }
      setModalOpen(false);
      form.resetFields();
      setEditingId(null);
      setCheckedKeys([]);
      fetchData();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '操作失败');
    }
  };

  const handleEdit = (record: any) => {
    setEditingId(record.id);
    form.setFieldsValue(record);
    setCheckedKeys(record.permissions?.map((p: any) => p.id) || []);
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteRole(id);
      message.success('已删除');
      fetchData();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '删除失败');
    }
  };

  const columns = [
    {
      title: '角色',
      key: 'role',
      render: (_: any, record: any) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 500 }}>{record.name}</span>
          {record.is_system && (
            <Tag style={{
              background: '#eaf1f5', color: '#3f6f8f', border: 'none',
              fontSize: 10, padding: '0 6px', borderRadius: 3,
            }}>系统</Tag>
          )}
        </div>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      render: (v: string) => <span style={{ color: '#7d8a96' }}>{v || '—'}</span>,
    },
    {
      title: '权限',
      key: 'perm_count',
      width: 80,
      render: (_: any, record: any) => (
        <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>
          {record.permissions?.length || 0}
        </span>
      ),
    },
    {
      title: '',
      key: 'action',
      width: 100,
      render: (_: any, record: any) => (
        <Space size={4}>
          {!record.is_system && (
            <>
              <Button type="text" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} className="action-icon-button" />
              <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)} okText="删除" cancelText="取消" okButtonProps={{ danger: true }}>
                <Button type="text" size="small" icon={<DeleteOutlined />} className="danger-icon-button" />
              </Popconfirm>
            </>
          )}
        </Space>
      ),
    },
  ];

  return (
    <>
      <div className="page-header">
        <div>
          <h2>角色管理</h2>
          <div className="page-desc">配置角色与权限分配</div>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => { setEditingId(null); form.resetFields(); setCheckedKeys([]); setModalOpen(true); }}
          style={{ borderRadius: 8, fontWeight: 500 }}
        >
          新建角色
        </Button>
      </div>

      <div className="content-panel">
        <Table
          columns={columns}
          dataSource={roles}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{
            emptyText: (
              <div className="empty-state">
                <TeamOutlined className="empty-icon" />
                <div className="empty-title">暂无角色</div>
              </div>
            ),
          }}
        />
      </div>

      <Modal
        title={<span style={{ fontWeight: 600 }}>{editingId ? '编辑角色' : '新建角色'}</span>}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingId(null); }}
        onOk={() => form.submit()}
        okText={editingId ? '保存' : '创建'}
        cancelText="取消"
        destroyOnClose
        width={480}
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical" style={{ marginTop: 20 }}>
          <Form.Item name="name" label="角色名" rules={[{ required: true, message: '请输入角色名' }]}>
            <Input placeholder="例如：编辑员" style={{ borderRadius: 8 }} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="角色描述" style={{ borderRadius: 8 }} />
          </Form.Item>
          <Form.Item label={<span style={{ fontWeight: 500, fontSize: 13, color: '#667482' }}>权限分配</span>}>
            <div style={{
              background: '#f8fafc',
              border: '1px solid #d9e1e8',
              borderRadius: 8,
              padding: '12px 16px',
              maxHeight: 280,
              overflow: 'auto',
            }}>
              <Tree
                checkable
                treeData={treeData}
                checkedKeys={checkedKeys}
                onCheck={(keys: any) => setCheckedKeys(keys as number[])}
              />
            </div>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default RolePage;
