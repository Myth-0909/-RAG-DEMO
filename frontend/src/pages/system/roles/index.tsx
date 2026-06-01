import React, { useEffect, useState } from 'react';
import { Card, Table, Button, Modal, Form, Input, Tree, Space, Tag, message, Popconfirm } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
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
      title: `${p.name} (${p.type === 'menu' ? '菜单' : p.type === 'button' ? '按钮' : '接口'})`,
      key: p.id,
      children: p.children?.map(toTreeNode) || [],
    };
  });

  const handleSubmit = async (values: any) => {
    try {
      const data = { ...values, permission_ids: checkedKeys };
      if (editingId) {
        await updateRole(editingId, data);
        message.success('更新成功');
      } else {
        await createRole(data);
        message.success('创建成功');
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
      message.success('删除成功');
      fetchData();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '删除失败');
    }
  };

  const columns = [
    { title: '角色名', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description' },
    {
      title: '类型', dataIndex: 'is_system', key: 'is_system',
      render: (v: boolean) => v ? <Tag color="gold">系统</Tag> : <Tag>自定义</Tag>,
    },
    {
      title: '权限数', key: 'perm_count',
      render: (_: any, record: any) => record.permissions?.length || 0,
    },
    {
      title: '操作', key: 'action',
      render: (_: any, record: any) => (
        <Space>
          {!record.is_system && (
            <>
              <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
              <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
                <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
              </Popconfirm>
            </>
          )}
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title="角色管理"
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingId(null); form.resetFields(); setCheckedKeys([]); setModalOpen(true); }}>新建角色</Button>}
      >
        <Table columns={columns} dataSource={roles} rowKey="id" loading={loading} />
      </Card>

      <Modal
        title={editingId ? '编辑角色' : '新建角色'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingId(null); }}
        onOk={() => form.submit()}
        destroyOnClose
        width={500}
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical">
          <Form.Item name="name" label="角色名" rules={[{ required: true }]}>
            <Input placeholder="角色名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="角色描述" />
          </Form.Item>
          <Form.Item label="权限分配">
            <Tree
              checkable
              treeData={treeData}
              checkedKeys={checkedKeys}
              onCheck={(keys: any) => setCheckedKeys(keys as number[])}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default RolePage;
