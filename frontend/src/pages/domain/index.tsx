import React, { useEffect, useState } from 'react';
import { Card, Table, Button, Modal, Form, Input, Space, Tag, message, Popconfirm } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { getDomains, createDomain, updateDomain, deleteDomain } from '@/services/api';

const { TextArea } = Input;

const DomainPage: React.FC = () => {
  const [domains, setDomains] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await getDomains();
      setDomains(res.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleSubmit = async (values: any) => {
    try {
      if (editingId) {
        await updateDomain(editingId, values);
        message.success('更新成功');
      } else {
        await createDomain(values);
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
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteDomain(id);
      message.success('删除成功');
      fetchData();
    } catch (err: any) {
      message.error('删除失败');
    }
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '系统提示词', dataIndex: 'system_prompt', key: 'system_prompt',
      ellipsis: true, width: 300,
    },
    {
      title: '状态', dataIndex: 'is_active', key: 'is_active',
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '操作', key: 'action',
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title="专业领域管理"
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingId(null); form.resetFields(); setModalOpen(true); }}>新建领域</Button>}
      >
        <Table columns={columns} dataSource={domains} rowKey="id" loading={loading} />
      </Card>

      <Modal
        title={editingId ? '编辑领域' : '新建领域'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingId(null); }}
        onOk={() => form.submit()}
        destroyOnClose
        width={600}
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="领域名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea placeholder="领域描述" rows={2} />
          </Form.Item>
          <Form.Item name="system_prompt" label="系统提示词">
            <TextArea
              placeholder="设置该领域下 AI 回答的专业指导，例如：你是一名法律顾问，请以专业法律术语回答问题..."
              rows={6}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default DomainPage;
