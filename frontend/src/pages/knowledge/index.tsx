import React, { useEffect, useState } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, Select, Space, Tag, Upload,
  message, Popconfirm, Drawer, List, Badge, Progress, Tooltip,
} from 'antd';
import {
  PlusOutlined, UploadOutlined, DeleteOutlined, FileTextOutlined,
  EyeOutlined, ReloadOutlined,
} from '@ant-design/icons';
import {
  getKnowledgeBases, createKnowledgeBase, deleteKnowledgeBase,
  getDocuments, uploadDocument, deleteDocument, getChunks, getDomains,
} from '@/services/api';

const { TextArea } = Input;

const chunkStrategies = [
  { label: '递归字符分块', value: 'recursive' },
  { label: '固定大小分块', value: 'fixed' },
  { label: '父子分块', value: 'parent_child' },
  { label: '语义分块', value: 'semantic' },
];

const statusMap: Record<string, { color: string; text: string }> = {
  pending: { color: 'default', text: '待处理' },
  processing: { color: 'processing', text: '处理中' },
  completed: { color: 'success', text: '已完成' },
  failed: { color: 'error', text: '失败' },
};

const KnowledgePage: React.FC = () => {
  const [kbs, setKbs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [domains, setDomains] = useState<any[]>([]);
  const [form] = Form.useForm();

  const [selectedKb, setSelectedKb] = useState<any>(null);
  const [docs, setDocs] = useState<any[]>([]);
  const [docDrawerOpen, setDocDrawerOpen] = useState(false);

  const [chunkDrawerOpen, setChunkDrawerOpen] = useState(false);
  const [chunks, setChunks] = useState<any[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<any>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [kbRes, domainRes] = await Promise.all([getKnowledgeBases(), getDomains()]);
      setKbs(kbRes.data);
      setDomains(domainRes.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleCreate = async (values: any) => {
    try {
      await createKnowledgeBase(values);
      message.success('创建成功');
      setModalOpen(false);
      form.resetFields();
      fetchData();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '创建失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteKnowledgeBase(id);
      message.success('删除成功');
      fetchData();
    } catch (err: any) {
      message.error('删除失败');
    }
  };

  const openDocs = async (kb: any) => {
    setSelectedKb(kb);
    setDocDrawerOpen(true);
    const res = await getDocuments(kb.id);
    setDocs(res.data);
  };

  const handleUpload = async (file: File) => {
    if (!selectedKb) return false;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('metadata_json', JSON.stringify({ author: 'admin' }));
    try {
      await uploadDocument(selectedKb.id, formData);
      message.success('上传成功，正在后台处理');
      const res = await getDocuments(selectedKb.id);
      setDocs(res.data);
    } catch (err: any) {
      message.error('上传失败');
    }
    return false;
  };

  const handleDeleteDoc = async (docId: number) => {
    if (!selectedKb) return;
    try {
      await deleteDocument(selectedKb.id, docId);
      message.success('删除成功');
      const res = await getDocuments(selectedKb.id);
      setDocs(res.data);
    } catch (err: any) {
      message.error('删除失败');
    }
  };

  const openChunks = async (doc: any) => {
    if (!selectedKb) return;
    setSelectedDoc(doc);
    setChunkDrawerOpen(true);
    const res = await getChunks(selectedKb.id, doc.id);
    setChunks(res.data);
  };

  const kbColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '分块策略', dataIndex: 'chunk_strategy', key: 'chunk_strategy',
      render: (v: string) => chunkStrategies.find(s => s.value === v)?.label || v,
    },
    { title: '文档数', dataIndex: 'document_count', key: 'document_count' },
    {
      title: '状态', dataIndex: 'is_active', key: 'is_active',
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '操作', key: 'action',
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" icon={<FileTextOutlined />} onClick={() => openDocs(record)}>文档</Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const docColumns = [
    { title: '文件名', dataIndex: 'original_filename', key: 'filename', ellipsis: true },
    { title: '类型', dataIndex: 'file_type', key: 'type', width: 80 },
    {
      title: '大小', dataIndex: 'file_size', key: 'size', width: 100,
      render: (v: number) => v ? `${(v / 1024).toFixed(1)} KB` : '-',
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (v: string) => {
        const s = statusMap[v] || { color: 'default', text: v };
        return <Badge status={s.color as any} text={s.text} />;
      },
    },
    { title: '分块数', dataIndex: 'chunk_count', key: 'chunks', width: 80 },
    {
      title: '操作', key: 'action', width: 120,
      render: (_: any, record: any) => (
        <Space>
          {record.status === 'completed' && (
            <Tooltip title="查看分块">
              <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => openChunks(record)} />
            </Tooltip>
          )}
          <Popconfirm title="确定删除？" onConfirm={() => handleDeleteDoc(record.id)}>
            <Button type="link" danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title="知识库管理"
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新建知识库</Button>}
      >
        <Table columns={kbColumns} dataSource={kbs} rowKey="id" loading={loading} />
      </Card>

      <Modal title="新建知识库" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()} destroyOnClose>
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="知识库名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea placeholder="知识库描述" rows={3} />
          </Form.Item>
          <Form.Item name="domain_id" label="专业领域">
            <Select placeholder="选择领域" allowClear options={domains.map(d => ({ label: d.name, value: d.id }))} />
          </Form.Item>
          <Form.Item name="chunk_strategy" label="分块策略" initialValue="recursive">
            <Select options={chunkStrategies} />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title={`文档列表 - ${selectedKb?.name || ''}`}
        open={docDrawerOpen}
        onClose={() => setDocDrawerOpen(false)}
        width={800}
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => selectedKb && getDocuments(selectedKb.id).then(r => setDocs(r.data))}>刷新</Button>
            <Upload beforeUpload={handleUpload} showUploadList={false}>
              <Button type="primary" icon={<UploadOutlined />}>上传文档</Button>
            </Upload>
          </Space>
        }
      >
        <Table columns={docColumns} dataSource={docs} rowKey="id" size="small" pagination={false} />
      </Drawer>

      <Drawer
        title={`分块详情 - ${selectedDoc?.original_filename || ''}`}
        open={chunkDrawerOpen}
        onClose={() => setChunkDrawerOpen(false)}
        width={700}
      >
        <List
          dataSource={chunks}
          renderItem={(item: any, index: number) => (
            <List.Item>
              <List.Item.Meta
                title={`分块 #${item.chunk_index + 1}`}
                description={
                  <div>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{item.chunk_text}</div>
                    {item.parent_text && (
                      <div style={{ marginTop: 8, padding: 8, background: '#f5f5f5', borderRadius: 4, fontSize: 12, color: '#666' }}>
                        <strong>父级上下文：</strong>{item.parent_text.slice(0, 200)}...
                      </div>
                    )}
                  </div>
                }
              />
            </List.Item>
          )}
        />
      </Drawer>
    </>
  );
};

export default KnowledgePage;
