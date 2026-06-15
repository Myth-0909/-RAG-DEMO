import React, { useEffect, useState } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag,
  message, Popconfirm, Drawer, Timeline, Tooltip,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, HistoryOutlined,
  ReloadOutlined, RobotOutlined, ApiOutlined, KeyOutlined,
  CheckCircleOutlined, CloseCircleOutlined, UndoOutlined,
} from '@ant-design/icons';
import {
  getModelConfigs, createModelConfig, updateModelConfig, deleteModelConfig,
  getModelConfigHistory, getAllModelConfigHistory, restoreModelConfig,
  setModelConfigAsCurrent,
} from '@/services/api';

const configTypeLabels: Record<string, { label: string; color: string }> = {
  llm: { label: 'LLM', color: '#3f6f8f' },
  embedding: { label: 'Embedding', color: '#3f6f8f' },
};

const actionLabels: Record<string, { label: string; color: string }> = {
  created: { label: '创建', color: '#547b63' },
  updated: { label: '修改', color: '#3f6f8f' },
  deleted: { label: '删除', color: '#e74c3c' },
  restored: { label: '恢复', color: '#7a678c' },
};

const ModelConfigPage: React.FC = () => {
  const [configs, setConfigs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<any>(null);
  const [form] = Form.useForm();

  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false);
  const [historyData, setHistoryData] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedConfigName, setSelectedConfigName] = useState('');

  const fetchConfigs = async () => {
    setLoading(true);
    try {
      const res = await getModelConfigs();
      setConfigs(res.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchConfigs(); }, []);

  const openCreate = () => {
    setEditingConfig(null);
    form.resetFields();
    form.setFieldsValue({ config_type: 'llm' });
    setModalOpen(true);
  };

  const openEdit = (config: any) => {
    setEditingConfig(config);
    form.setFieldsValue({
      name: config.name,
      base_url: config.base_url,
      model_name: config.model_name,
      api_key: config.api_key,
      config_type: config.config_type,
    });
    setModalOpen(true);
  };

  const handleSubmit = async (values: any) => {
    try {
      if (editingConfig) {
        await updateModelConfig(editingConfig.id, values);
        message.success('修改成功');
      } else {
        await createModelConfig(values);
        message.success('创建成功');
      }
      setModalOpen(false);
      form.resetFields();
      fetchConfigs();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '操作失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteModelConfig(id);
      message.success('已删除');
      fetchConfigs();
    } catch {
      message.error('删除失败');
    }
  };

  const openHistory = async (config: any) => {
    setSelectedConfigName(config.name);
    setHistoryDrawerOpen(true);
    setHistoryLoading(true);
    try {
      const res = await getModelConfigHistory(config.id);
      setHistoryData(res.data);
    } catch {
      message.error('获取历史记录失败');
    } finally {
      setHistoryLoading(false);
    }
  };

  const openAllHistory = async () => {
    setSelectedConfigName('全部');
    setHistoryDrawerOpen(true);
    setHistoryLoading(true);
    try {
      const res = await getAllModelConfigHistory();
      setHistoryData(res.data);
    } catch {
      message.error('获取历史记录失败');
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleRestore = async (historyId: number) => {
    try {
      await restoreModelConfig(historyId);
      message.success('已恢复');
      fetchConfigs();
      const res = await getAllModelConfigHistory();
      setHistoryData(res.data);
    } catch (err: any) {
      message.error(err.response?.data?.detail || '恢复失败');
    }
  };

  const handleSetCurrent = async (id: number) => {
    try {
      await setModelConfigAsCurrent(id);
      message.success('已切换为当前使用模型');
      fetchConfigs();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '切换失败');
    }
  };

  const maskApiKey = (key: string) => {
    if (!key || key.length <= 8) return '****';
    return key.slice(0, 4) + '****' + key.slice(-4);
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => (
        <span style={{ fontWeight: 600, color: '#202a34' }}>{name}</span>
      ),
    },
    {
      title: '类型',
      dataIndex: 'config_type',
      key: 'config_type',
      width: 100,
      render: (type: string) => {
        const t = configTypeLabels[type] || { label: type, color: '#7d8a96' };
        return (
          <Tag style={{ background: t.color + '14', color: t.color, border: 'none', fontSize: 11 }}>
            {t.label}
          </Tag>
        );
      },
    },
    {
      title: '模型',
      dataIndex: 'model_name',
      key: 'model_name',
      ellipsis: true,
      render: (v: string) => (
        <span style={{ fontFamily: 'monospace', fontSize: 13, color: '#202a34' }}>{v}</span>
      ),
    },
    {
      title: 'Base URL',
      dataIndex: 'base_url',
      key: 'base_url',
      ellipsis: true,
      render: (v: string) => (
        <span style={{ fontFamily: 'monospace', fontSize: 12, color: '#667482' }}>{v}</span>
      ),
    },
    {
      title: 'API Key',
      dataIndex: 'api_key',
      key: 'api_key',
      width: 140,
      render: (v: string) => (
        <span style={{ fontFamily: 'monospace', fontSize: 12, color: '#7d8a96' }}>
          {maskApiKey(v)}
        </span>
      ),
    },
    {
      title: '状态',
      key: 'status',
      width: 120,
      render: (_: any, record: any) => (
        <Space size={4}>
          {record.is_current ? (
            <Tag style={{ background: '#547b6318', color: '#547b63', border: 'none', fontSize: 11 }}>
              <CheckCircleOutlined style={{ marginRight: 3 }} />当前使用
            </Tag>
          ) : (
            <Tag style={{ background: '#f1f5f8', color: '#7d8a96', border: 'none', fontSize: 11 }}>
              未启用
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: '',
      key: 'action',
      width: 180,
      render: (_: any, record: any) => (
        <Space size={2}>
          {!record.is_current && (
            <Tooltip title="设为当前使用">
              <Button
                type="text"
                size="small"
                onClick={() => handleSetCurrent(record.id)}
                className="action-icon-button"
                style={{ fontSize: 12 }}
              >
                切换
              </Button>
            </Tooltip>
          )}
          <Tooltip title="历史记录">
            <Button
              type="text"
              size="small"
              icon={<HistoryOutlined />}
              onClick={() => openHistory(record)}
              className="action-icon-button"
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => openEdit(record)}
              className="action-icon-button"
            />
          </Tooltip>
          <Popconfirm
            title="确认删除此配置？"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
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
          <h2>模型配置</h2>
          <div className="page-desc">管理 LLM 和 Embedding 模型的连接配置</div>
        </div>
        <Space>
          <Button icon={<HistoryOutlined />} onClick={openAllHistory}>操作历史</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} style={{ borderRadius: 8, fontWeight: 500 }}>
            新增配置
          </Button>
        </Space>
      </div>

      <div className="content-panel">
        <Table
          columns={columns}
          dataSource={configs}
          rowKey="id"
          loading={loading}
          pagination={false}
          style={{ margin: 0 }}
          locale={{
            emptyText: (
              <div className="empty-state">
                <RobotOutlined className="empty-icon" />
                <div className="empty-title">暂无模型配置</div>
                <div className="empty-desc">点击右上角按钮添加第一个模型配置</div>
              </div>
            ),
          }}
        />
      </div>

      {/* Create / Edit Modal */}
      <Modal
        title={<span style={{ fontWeight: 600 }}>{editingConfig ? '修改配置' : '新增配置'}</span>}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        okText={editingConfig ? '保存' : '创建'}
        cancelText="取消"
        destroyOnClose
        width={520}
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical" style={{ marginTop: 20 }}>
          <Form.Item name="name" label="配置名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input prefix={<RobotOutlined style={{ color: '#7d8a96' }} />} placeholder="例如：GPT-4o、本地 Gemma" style={{ borderRadius: 8 }} />
          </Form.Item>
          <Form.Item name="config_type" label="模型类型" rules={[{ required: true, message: '请选择类型' }]}>
            <Select
              options={[
                { label: 'LLM（大语言模型）', value: 'llm' },
                { label: 'Embedding（向量模型）', value: 'embedding' },
              ]}
            />
          </Form.Item>
          <Form.Item name="base_url" label="Base URL" rules={[{ required: true, message: '请输入 Base URL' }]}>
            <Input prefix={<ApiOutlined style={{ color: '#7d8a96' }} />} placeholder="例如：http://localhost:8000/v1" style={{ borderRadius: 8 }} />
          </Form.Item>
          <Form.Item name="model_name" label="模型名称" rules={[{ required: true, message: '请输入模型名称' }]}>
            <Input placeholder="例如：google/gemma-4-31B-it" style={{ borderRadius: 8 }} />
          </Form.Item>
          <Form.Item name="api_key" label="API Key" rules={[{ required: true, message: '请输入 API Key' }]}>
            <Input.Password prefix={<KeyOutlined style={{ color: '#7d8a96' }} />} placeholder="sk-..." style={{ borderRadius: 8 }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* History Drawer */}
      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <HistoryOutlined style={{ color: '#3f6f8f' }} />
            <span style={{ fontWeight: 600 }}>操作历史</span>
            <span style={{ fontSize: 13, color: '#7d8a96', fontWeight: 400 }}>
              {selectedConfigName}
            </span>
          </div>
        }
        open={historyDrawerOpen}
        onClose={() => setHistoryDrawerOpen(false)}
        width={560}
        extra={
          <Button icon={<ReloadOutlined />} onClick={openAllHistory} size="small">刷新</Button>
        }
      >
        {historyLoading ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#7d8a96' }}>加载中...</div>
        ) : historyData.length === 0 ? (
          <div className="empty-state" style={{ padding: '40px 20px' }}>
            <HistoryOutlined className="empty-icon" />
            <div className="empty-title">暂无历史记录</div>
          </div>
        ) : (
          <Timeline
            items={historyData.map((item: any) => {
              const action = actionLabels[item.action] || { label: item.action, color: '#7d8a96' };
              return {
                dot: (
                  <div style={{
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: action.color,
                  }} />
                ),
                children: (
                  <div style={{ paddingBottom: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <Tag style={{ background: action.color + '14', color: action.color, border: 'none', fontSize: 11 }}>
                        {action.label}
                      </Tag>
                      <span style={{ fontWeight: 600, fontSize: 13, color: '#202a34' }}>{item.name}</span>
                      <span style={{ fontSize: 11, color: '#b3bec8', marginLeft: 'auto' }}>
                        {new Date(item.created_at).toLocaleString('zh-CN')}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: '#667482', lineHeight: 1.8 }}>
                      <div><span style={{ color: '#7d8a96' }}>模型：</span>{item.model_name}</div>
                      <div><span style={{ color: '#7d8a96' }}>URL：</span>{item.base_url}</div>
                      <div><span style={{ color: '#7d8a96' }}>Key：</span><span style={{ fontFamily: 'monospace' }}>{maskApiKey(item.api_key)}</span></div>
                      {item.changed_by && (
                        <div><span style={{ color: '#7d8a96' }}>操作人：</span>{item.changed_by}</div>
                      )}
                    </div>
                    <Button
                      type="link"
                      size="small"
                      icon={<UndoOutlined />}
                      onClick={() => handleRestore(item.id)}
                      style={{ padding: 0, marginTop: 6, fontSize: 12 }}
                    >
                      恢复此版本
                    </Button>
                  </div>
                ),
              };
            })}
          />
        )}
      </Drawer>
    </>
  );
};

export default ModelConfigPage;
