import React, { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, Space, Tag, message, Popconfirm } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, UserOutlined } from '@ant-design/icons';
import { getUsers, createUser, updateUser, deleteUser, getRoles } from '@/services/api';

const UserPage: React.FC = () => {
  const [users, setUsers] = useState<any[]>([]);
  const [roles, setRoles] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const [userRes, roleRes] = await Promise.all([getUsers(), getRoles()]);
      setUsers(userRes.data);
      setRoles(roleRes.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleSubmit = async (values: any) => {
    try {
      if (editingId) {
        await updateUser(editingId, values);
        message.success('已更新');
      } else {
        await createUser(values);
        message.success('已创建');
      }
      setModalOpen(false);
      form.resetFields();
      setEditingId(null);
      fetchData();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '操作失败');
    }
  };

  const handleEdit = (record: any) => {
    setEditingId(record.id);
    form.setFieldsValue({
      ...record,
      role_ids: record.roles?.map((r: any) => r.id) || [],
    });
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteUser(id);
      message.success('已删除');
      fetchData();
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    {
      title: '用户',
      key: 'user',
      render: (_: any, record: any) => (
        <Space>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: record.is_superuser ? '#3f6f8f' : '#f1f5f8',
            color: record.is_superuser ? '#fff' : '#667482',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 600, fontSize: 13,
          }}>
            {(record.full_name || record.username)?.[0]?.toUpperCase()}
          </div>
          <div>
            <div style={{ fontWeight: 500, fontSize: 14 }}>{record.full_name || record.username}</div>
            <div style={{ fontSize: 12, color: '#7d8a96' }}>@{record.username}</div>
          </div>
        </Space>
      ),
    },
    {
      title: '角色',
      key: 'roles',
      render: (_: any, record: any) => (
        <Space size={4}>
          {record.roles?.map((r: any) => (
            <Tag key={r.id} style={{ background: '#f1f5f8', color: '#667482', border: 'none' }}>
              {r.name}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (v: boolean) => (
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: v ? '#547b63' : '#b3bec8',
          display: 'inline-block',
        }} />
      ),
    },
    {
      title: '',
      key: 'action',
      width: 100,
      render: (_: any, record: any) => (
        <Space size={4}>
          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} className="action-icon-button" />
          {!record.is_superuser && (
            <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)} okText="删除" cancelText="取消" okButtonProps={{ danger: true }}>
              <Button type="text" size="small" icon={<DeleteOutlined />} className="danger-icon-button" />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <>
      <div className="page-header">
        <div>
          <h2>用户管理</h2>
          <div className="page-desc">管理系统用户、分配角色与权限</div>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => { setEditingId(null); form.resetFields(); setModalOpen(true); }}
          style={{ borderRadius: 8, fontWeight: 500 }}
        >
          新建用户
        </Button>
      </div>

      <div className="content-panel">
        <Table
          columns={columns}
          dataSource={users}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{
            emptyText: (
              <div className="empty-state">
                <UserOutlined className="empty-icon" />
                <div className="empty-title">暂无用户</div>
              </div>
            ),
          }}
        />
      </div>

      <Modal
        title={<span style={{ fontWeight: 600 }}>{editingId ? '编辑用户' : '新建用户'}</span>}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingId(null); }}
        onOk={() => form.submit()}
        okText={editingId ? '保存' : '创建'}
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical" style={{ marginTop: 20 }}>
          <Form.Item name="username" label="用户名" rules={[{ required: !editingId }]}>
            <Input placeholder="用户名" disabled={!!editingId} style={{ borderRadius: 8 }} />
          </Form.Item>
          {!editingId && (
            <Form.Item name="password" label="密码" rules={[{ required: true, min: 6 }]}>
              <Input.Password placeholder="至少 6 位" style={{ borderRadius: 8 }} />
            </Form.Item>
          )}
          <Form.Item name="full_name" label="姓名">
            <Input placeholder="显示名称" style={{ borderRadius: 8 }} />
          </Form.Item>
          <Form.Item name="role_ids" label="角色">
            <Select
              mode="multiple"
              placeholder="选择角色"
              options={roles.map(r => ({ label: r.name, value: r.id }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default UserPage;
