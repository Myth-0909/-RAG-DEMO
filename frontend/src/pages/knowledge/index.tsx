import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, Upload,
  message, Popconfirm, Drawer, List, Badge, Tooltip, Divider,
} from 'antd';
import {
  PlusOutlined, UploadOutlined, DeleteOutlined, FileTextOutlined,
  EyeOutlined, ReloadOutlined, DatabaseOutlined, FileOutlined,
  AppstoreOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import {
  getKnowledgeBases, createKnowledgeBase, deleteKnowledgeBase,
  getDocuments, uploadDocument, deleteDocument, getChunks, getDomains,
} from '@/services/api';

const { TextArea } = Input;

const strategyLabels: Record<string, { label: string; color: string }> = {
  recursive: { label: '递归分块', color: '#5b8ec9' },
  fixed: { label: '固定分块', color: '#8a8580' },
  parent_child: { label: '父子分块', color: '#e8653a' },
  semantic: { label: '语义分块', color: '#4a9e6e' },
  hybrid: { label: '混合分块', color: '#9b59b6' },
};

const statusConfig: Record<string, { color: string; text: string }> = {
  pending: { color: 'default', text: '等待中' },
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

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  // Auto-polling: refresh doc list when any doc is pending/processing
  const hasActiveProcessing = docs.some(
    (d) => d.status === 'pending' || d.status === 'processing',
  );

  const refreshDocs = useCallback(async () => {
    if (!selectedKb) return;
    try {
      const res = await getDocuments(selectedKb.id);
      setDocs(res.data);
      // Also refresh KB list for updated document_count
      const kbRes = await getKnowledgeBases();
      setKbs(kbRes.data);
    } catch {
      // silent
    }
  }, [selectedKb]);

  useEffect(() => {
    if (docDrawerOpen && hasActiveProcessing) {
      pollRef.current = setInterval(refreshDocs, 3000);
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [docDrawerOpen, hasActiveProcessing, refreshDocs]);

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
      message.success('已删除');
      fetchData();
    } catch {
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
      message.success('已上传，系统自动分析内容并分块');
      // Refresh immediately to show pending status, then polling takes over
      refreshDocs();
    } catch {
      message.error('上传失败');
    }
    return false;
  };

  const handleDeleteDoc = async (docId: number) => {
    if (!selectedKb) return;
    try {
      await deleteDocument(selectedKb.id, docId);
      message.success('已删除');
      refreshDocs();
    } catch {
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

  const getDocStrategy = (doc: any): string | null => {
    return doc.metadata_json?.strategy?.selected || null;
  };

  const getDocAnalysis = (doc: any) => {
    return doc.metadata_json?.strategy || null;
  };

  // Stats
  const totalDocs = kbs.reduce((s, kb) => s + (kb.document_count || 0), 0);
  const activeKbs = kbs.filter(kb => kb.is_active).length;

  const kbColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: any) => (
        <a
          onClick={() => openDocs(record)}
          style={{ fontWeight: 500, color: '#1a1a1a' }}
        >
          {name}
        </a>
      ),
    },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true,
      render: (v: string) => <span style={{ color: '#8a8580' }}>{v || '—'}</span>,
    },
    {
      title: '文档',
      dataIndex: 'document_count',
      key: 'document_count',
      width: 80,
      render: (v: number) => (
        <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>{v}</span>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (v: boolean) => (
        <div style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: v ? '#4a9e6e' : '#c4c0ba',
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
          <Tooltip title="查看文档">
            <Button
              type="text"
              size="small"
              icon={<FileTextOutlined />}
              onClick={() => openDocs(record)}
              style={{ color: '#6b6560' }}
            />
          </Tooltip>
          <Popconfirm title="确认删除此知识库?" onConfirm={() => handleDelete(record.id)} okText="删除" cancelText="取消">
            <Button type="text" size="small" icon={<DeleteOutlined />} style={{ color: '#c4c0ba' }} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const docColumns = [
    { title: '文件名', dataIndex: 'original_filename', key: 'filename', ellipsis: true,
      render: (v: string) => <span style={{ fontWeight: 500 }}>{v}</span>,
    },
    {
      title: '类型', dataIndex: 'file_type', key: 'type', width: 60,
      render: (v: string) => (
        <span style={{
          fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
          letterSpacing: '0.04em', color: '#8a8580',
        }}>{v}</span>
      ),
    },
    {
      title: '大小', dataIndex: 'file_size', key: 'size', width: 80,
      render: (v: number) => (
        <span style={{ fontVariantNumeric: 'tabular-nums', color: '#6b6560', fontSize: 13 }}>
          {v ? `${(v / 1024).toFixed(1)} KB` : '—'}
        </span>
      ),
    },
    {
      title: '策略', key: 'strategy', width: 100,
      render: (_: any, record: any) => {
        const strategy = getDocStrategy(record);
        if (!strategy) return <span style={{ color: '#c4c0ba' }}>—</span>;
        const s = strategyLabels[strategy] || { label: strategy, color: '#8a8580' };
        return (
          <Tag style={{ background: s.color + '14', color: s.color, border: 'none', fontSize: 11 }}>
            {s.label}
          </Tag>
        );
      },
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (v: string) => {
        const s = statusConfig[v] || { color: 'default', text: v };
        return <Badge status={s.color as any} text={<span style={{ fontSize: 12 }}>{s.text}</span>} />;
      },
    },
    {
      title: '分块', dataIndex: 'chunk_count', key: 'chunks', width: 60,
      render: (v: number) => (
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>{v || '—'}</span>
      ),
    },
    {
      title: '', key: 'action', width: 80,
      render: (_: any, record: any) => (
        <Space size={2}>
          {record.status === 'completed' && (
            <Tooltip title="查看分块">
              <Button type="text" size="small" icon={<EyeOutlined />} onClick={() => openChunks(record)} style={{ color: '#6b6560' }} />
            </Tooltip>
          )}
          <Popconfirm title="确认删除?" onConfirm={() => handleDeleteDoc(record.id)} okText="删除" cancelText="取消">
            <Button type="text" size="small" icon={<DeleteOutlined />} style={{ color: '#c4c0ba' }} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const analysis = selectedDoc ? getDocAnalysis(selectedDoc) : null;

  return (
    <>
      {/* Page header */}
      <div className="page-header">
        <div>
          <h2>知识库</h2>
          <div className="page-desc">上传文档后系统自动分析内容并选择最优分块策略</div>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalOpen(true)}
          style={{ borderRadius: 8, fontWeight: 500 }}
        >
          新建知识库
        </Button>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <DatabaseOutlined style={{ fontSize: 16, color: '#e8653a' }} />
            <span className="stat-label">知识库总数</span>
          </div>
          <div className="stat-value">{kbs.length}</div>
        </div>
        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <AppstoreOutlined style={{ fontSize: 16, color: '#4a9e6e' }} />
            <span className="stat-label">活跃知识库</span>
          </div>
          <div className="stat-value">{activeKbs}</div>
        </div>
        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <FileOutlined style={{ fontSize: 16, color: '#5b8ec9' }} />
            <span className="stat-label">文档总数</span>
          </div>
          <div className="stat-value">{totalDocs}</div>
        </div>
      </div>

      {/* Table */}
      <div style={{
        background: '#fff',
        borderRadius: 12,
        border: '1px solid #eae8e4',
        overflow: 'hidden',
      }}>
        <Table
          columns={kbColumns}
          dataSource={kbs}
          rowKey="id"
          loading={loading}
          pagination={false}
          style={{ margin: 0 }}
          locale={{
            emptyText: (
              <div className="empty-state">
                <DatabaseOutlined className="empty-icon" />
                <div className="empty-title">暂无知识库</div>
                <div className="empty-desc">点击右上角按钮创建第一个知识库</div>
              </div>
            ),
          }}
        />
      </div>

      {/* Create modal */}
      <Modal
        title={<span style={{ fontWeight: 600 }}>新建知识库</span>}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        okText="创建"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} onFinish={handleCreate} layout="vertical" style={{ marginTop: 20 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：产品手册库" style={{ borderRadius: 8 }} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea placeholder="简要描述此知识库的用途" rows={3} style={{ borderRadius: 8 }} />
          </Form.Item>
          <Form.Item name="domain_id" label="专业领域">
            <Select placeholder="选择领域（可选）" allowClear options={domains.map(d => ({ label: d.name, value: d.id }))} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Document drawer */}
      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileTextOutlined style={{ color: '#e8653a' }} />
            <span style={{ fontWeight: 600 }}>{selectedKb?.name}</span>
            <span style={{ fontSize: 13, color: '#8a8580', fontWeight: 400 }}>文档列表</span>
          </div>
        }
        open={docDrawerOpen}
        onClose={() => setDocDrawerOpen(false)}
        width={780}
        extra={
          <Space>
            {hasActiveProcessing && (
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                fontSize: 12,
                color: '#e8653a',
              }}>
                <span style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: '#e8653a',
                  animation: 'pulse 1.5s infinite',
                }} />
                处理中，自动刷新...
              </span>
            )}
            <Button icon={<ReloadOutlined />} onClick={refreshDocs} size="small">刷新</Button>
            <Upload beforeUpload={handleUpload} showUploadList={false} accept=".pdf,.docx,.txt,.md">
              <Button type="primary" icon={<UploadOutlined />} size="small" style={{ borderRadius: 6 }}>上传</Button>
            </Upload>
          </Space>
        }
      >
        <Table
          columns={docColumns}
          dataSource={docs}
          rowKey="id"
          size="small"
          pagination={false}
          locale={{
            emptyText: (
              <div className="empty-state" style={{ padding: '40px 20px' }}>
                <FileOutlined className="empty-icon" />
                <div className="empty-title">暂无文档</div>
                <div className="empty-desc">上传文件后系统自动分析内容并智能分块</div>
              </div>
            ),
          }}
        />
      </Drawer>

      {/* Chunk drawer */}
      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <AppstoreOutlined style={{ color: '#e8653a' }} />
            <span style={{ fontWeight: 600 }}>{selectedDoc?.original_filename}</span>
            <span style={{ fontSize: 13, color: '#8a8580', fontWeight: 400 }}>
              {chunks.length} 个分块
            </span>
          </div>
        }
        open={chunkDrawerOpen}
        onClose={() => setChunkDrawerOpen(false)}
        width={640}
      >
        {/* Analysis info banner */}
        {analysis && (
          <div style={{
            background: '#fafaf8',
            border: '1px solid #eae8e4',
            borderRadius: 10,
            padding: '14px 16px',
            marginBottom: 20,
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 8,
            }}>
              <ThunderboltOutlined style={{ color: '#e8653a', fontSize: 14 }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: '#1a1a1a' }}>
                自动分析结果
              </span>
              <Tag style={{
                background: (strategyLabels[analysis.selected]?.color || '#8a8580') + '14',
                color: strategyLabels[analysis.selected]?.color || '#8a8580',
                border: 'none',
                fontSize: 11,
                marginLeft: 'auto',
              }}>
                {analysis.label || analysis.selected}
              </Tag>
            </div>
            <div style={{
              fontSize: 12,
              color: '#6b6560',
              lineHeight: 1.6,
            }}>
              {analysis.reasoning}
            </div>
          </div>
        )}

        <List
          dataSource={chunks}
          renderItem={(item: any) => (
            <List.Item style={{ borderBottom: '1px solid #f0eeeb', padding: '16px 0' }}>
              <div style={{ width: '100%' }}>
                <div style={{
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  color: '#8a8580',
                  marginBottom: 8,
                }}>
                  分块 #{item.chunk_index + 1}
                  {item.token_count && (
                    <span style={{ fontWeight: 400, marginLeft: 8, color: '#c4c0ba' }}>
                      {item.token_count} 字符
                    </span>
                  )}
                </div>
                <div style={{
                  whiteSpace: 'pre-wrap',
                  fontSize: 13,
                  lineHeight: 1.7,
                  color: '#1a1a1a',
                }}>
                  {item.chunk_text}
                </div>
                {item.parent_text && (
                  <>
                    <Divider style={{ margin: '12px 0' }} />
                    <div style={{
                      fontSize: 12,
                      color: '#8a8580',
                      lineHeight: 1.6,
                      padding: '10px 12px',
                      background: '#fafaf8',
                      borderRadius: 8,
                      border: '1px solid #f0eeeb',
                    }}>
                      <span style={{ fontWeight: 600, color: '#6b6560' }}>父级上下文</span>
                      <div style={{ marginTop: 4 }}>{item.parent_text.slice(0, 200)}...</div>
                    </div>
                  </>
                )}
              </div>
            </List.Item>
          )}
        />
      </Drawer>
    </>
  );
};

export default KnowledgePage;
