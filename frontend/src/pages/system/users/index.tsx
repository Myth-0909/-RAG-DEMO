import React, { useEffect, useState } from 'react';
import { Card, Table, Button, Modal, Form, Input, Select, Space, Tag, Switch, message, Popconfirm } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
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
        message.success('更新成功');
      } else {
        await createUser(values);
        message.success('创建成功');
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
      message.success('删除成功');
      fetchData();
    } catch (err: any) {
      message.error('删除失败');
    }
  };

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '姓名', dataIndex: 'full_name', key: 'full_name' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    {
      title: '角色', key: 'roles',
      render: (_: any, record: any) => (
        <Space>
          {record.roles?.map((r: any) => <Tag key={r.id} color="blue">{r.name}</Tag>)}
        </Space>
      ),
    },
    {
      title: '状态', dataIndex: 'is_active', key: 'is_active',
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '管理员', dataIndex: 'is_superuser', key: 'is_superuser',
      render: (v: boolean) => v ? <Tag color="gold">超级管理员</Tag> : null,
    },
    {
      title: '操作', key: 'action',
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          {!record.is_superuser && (
            <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
              <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title="用户管理"
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingId(null); form.resetFields(); setModalOpen(true); }}>新建用户</Button>}
      >
        <Table columns={columns} dataSource={users} rowKey="id" loading={loading} />
      </Card>

      <Modal
        title={editingId ? '编辑用户' : '新建用户'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingId(null); }}
        onOk={() => form.submit()}
        destroyOnClose
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: !editingId }]}>
            <Input placeholder="用户名" disabled={!!editingId} />
          </Form.Item>
          {!editingId && (
            <Form.Item name="password" label="密码" rules={[{ required: true, min: 6 }]}>
              <Input.Password placeholder="密码（至少6位）" />
            </Form.Item>
          )}
          <Form.Item name="full_name" label="姓名">
            <Input placeholder="姓名" />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input placeholder="邮箱" />
          </Form.Item>
          <Form.Item name="role_ids" label="角色">
            <Select mode="multiple" placeholder="选择角色" options={roles.map(r => ({ label: r.name, value: r.id }))} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default UserPage;
