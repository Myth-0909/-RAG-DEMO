import React, { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Space, message, Popconfirm } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, GlobalOutlined } from '@ant-design/icons';
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
        message.success('已更新');
      } else {
        await createDomain(values);
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
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteDomain(id);
      message.success('已删除');
      fetchData();
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (v: string) => <span style={{ fontWeight: 500 }}>{v}</span>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (v: string) => <span style={{ color: '#7d8a96' }}>{v || '—'}</span>,
    },
    {
      title: '系统提示词',
      dataIndex: 'system_prompt',
      key: 'system_prompt',
      ellipsis: true,
      width: 300,
      render: (v: string) => (
        <span style={{ color: '#667482', fontSize: 13 }}>
          {v ? v.slice(0, 60) + (v.length > 60 ? '...' : '') : '—'}
        </span>
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
          <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)} okText="删除" cancelText="取消" okButtonProps={{ danger: true }}>
            <Button type="text" size="small" icon={<DeleteOutlined />} className="danger-icon-button" />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <div className="page-header">
        <div>
          <h2>专业领域</h2>
          <div className="page-desc">配置不同领域的系统提示词与专业知识</div>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => { setEditingId(null); form.resetFields(); setModalOpen(true); }}
          style={{ borderRadius: 8, fontWeight: 500 }}
        >
          新建领域
        </Button>
      </div>

      <div className="content-panel">
        <Table
          columns={columns}
          dataSource={domains}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{
            emptyText: (
              <div className="empty-state">
                <GlobalOutlined className="empty-icon" />
                <div className="empty-title">暂无领域</div>
                <div className="empty-desc">创建领域以配置专业问答的上下文</div>
              </div>
            ),
          }}
        />
      </div>

      <Modal
        title={<span style={{ fontWeight: 600 }}>{editingId ? '编辑领域' : '新建领域'}</span>}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingId(null); }}
        onOk={() => form.submit()}
        okText={editingId ? '保存' : '创建'}
        cancelText="取消"
        destroyOnClose
        width={560}
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical" style={{ marginTop: 20 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：法律顾问" style={{ borderRadius: 8 }} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="领域简述" style={{ borderRadius: 8 }} />
          </Form.Item>
          <Form.Item name="system_prompt" label="系统提示词">
            <TextArea
              placeholder="设置该领域 AI 回答的专业指导，例如：&#10;你是一名资深法律顾问，请以专业法律术语回答问题，引用相关法条。"
              rows={5}
              style={{ borderRadius: 8 }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default DomainPage;
