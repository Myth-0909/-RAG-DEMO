import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Table, Button, Tag, Badge, Drawer, Space, Tooltip, message } from 'antd';
import {
  ThunderboltOutlined, ReloadOutlined, EyeOutlined,
  RedoOutlined, LoadingOutlined, CheckCircleOutlined,
  CloseCircleOutlined, ClockCircleOutlined, FileTextOutlined,
  ClearOutlined, ScissorOutlined, BulbOutlined, AppstoreOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import {
  getProcessingTasks, getProcessingTask, retryProcessingTask,
} from '@/services/api';

const STEPS_CONFIG = [
  { key: 'convert', title: '文档转换', icon: <FileTextOutlined /> },
  { key: 'clean', title: '清洗评估', icon: <ClearOutlined /> },
  { key: 'apply', title: '执行清洗', icon: <ScissorOutlined /> },
  { key: 'analyze', title: '分块分析', icon: <BulbOutlined /> },
  { key: 'chunk', title: '执行分块', icon: <AppstoreOutlined /> },
  { key: 'embed', title: '向量化存储', icon: <DatabaseOutlined /> },
];

const statusConfig: Record<string, { color: string; text: string; badge: string }> = {
  pending: { color: 'default', text: '等待中', badge: 'default' },
  processing: { color: 'processing', text: '处理中', badge: 'processing' },
  completed: { color: 'success', text: '已完成', badge: 'success' },
  failed: { color: 'error', text: '失败', badge: 'error' },
};

const stepLabels: Record<string, string> = {
  convert: '文档转换',
  extract: '文本提取',
  clean: '清洗评估',
  apply: '执行清洗',
  analyze: '内容分析',
  chunk: '智能分块',
  embed: '向量化存储',
  complete: '处理完成',
  error: '出错',
};

const strategyLabels: Record<string, { label: string; color: string }> = {
  recursive: { label: '递归分块', color: '#3f6f8f' },
  fixed: { label: '固定分块', color: '#7d8a96' },
  parent_child: { label: '父子分块', color: '#3f6f8f' },
  semantic: { label: '语义分块', color: '#547b63' },
  hybrid: { label: '混合分块', color: '#7a678c' },
};

function RenderEventDetail({ event }: { event: any }) {
  const { step, status, data } = event;
  const [previewExpanded, setPreviewExpanded] = useState(false);
  if (!data || Object.keys(data).length === 0) return null;

  switch (step) {
    case 'convert':
    case 'extract':
      if (status === 'done') {
        return (
          <div className="process-result">
            <div className="process-result-row">
              <span className="process-result-label">Markdown 字符数</span>
              <span className="process-result-value">{data.chars?.toLocaleString()}</span>
            </div>
            {data.converter && (
              <div className="process-result-row">
                <span className="process-result-label">转换器</span>
                <span className="process-result-value">{data.converter}</span>
              </div>
            )}
            {data.quality && (
              <div className="process-result-row">
                <span className="process-result-label">质量评分</span>
                <span className="process-result-value">{data.quality.score}</span>
              </div>
            )}
            {data.warnings?.length > 0 && (
              <div className="process-issues">
                {data.warnings.map((warning: string, i: number) => (
                  <div key={i} className="process-issue-item">• {warning}</div>
                ))}
              </div>
            )}
            {data.preview && (
              <div
                className={`process-preview${previewExpanded ? ' process-preview-expanded' : ''}`}
                onClick={() => setPreviewExpanded(!previewExpanded)}
                style={{ cursor: 'pointer' }}
                title={previewExpanded ? '点击收起' : '点击展开完整内容'}
              >
                {previewExpanded ? data.preview : data.preview.slice(0, 150) + '...'}
                <div className="process-preview-toggle">
                  {previewExpanded ? '收起 ▲' : '展开 ▼'}
                </div>
              </div>
            )}
          </div>
        );
      }
      return null;

    case 'clean':
      if (status === 'done' && data.assessment) {
        const a = data.assessment;
        return (
          <div className="process-result">
            <div className="process-result-row">
              <span className="process-result-label">是否需要清洗</span>
              <Tag color={a.needs_cleaning ? '#3f6f8f' : '#547b63'} style={{ border: 'none' }}>
                {a.needs_cleaning ? '需要' : '不需要'}
              </Tag>
            </div>
            {a.severity && a.severity !== 'none' && (
              <div className="process-result-row">
                <span className="process-result-label">严重程度</span>
                <span className="process-result-value">{a.severity}</span>
              </div>
            )}
            {a.issues_found?.length > 0 && (
              <div className="process-issues">
                {a.issues_found.map((issue: string, i: number) => (
                  <div key={i} className="process-issue-item">• {issue}</div>
                ))}
              </div>
            )}
          </div>
        );
      }
      return null;

    case 'apply':
      if (status === 'done') {
        return (
          <div className="process-result">
            {data.message && <div className="process-result-message">{data.message}</div>}
            {data.report && !data.report.skipped && (
              <>
                <div className="process-result-row">
                  <span className="process-result-label">移除字符</span>
                  <span className="process-result-value">{data.report.chars_removed?.toLocaleString()}</span>
                </div>
                {data.chars_before && (
                  <div className="process-result-row">
                    <span className="process-result-label">清洗前后</span>
                    <span className="process-result-value">
                      {data.chars_before?.toLocaleString()} → {data.chars_after?.toLocaleString()}
                    </span>
                  </div>
                )}
              </>
            )}
          </div>
        );
      }
      return null;

    case 'analyze':
      if (status === 'done' && data.plan) {
        const plan = data.plan;
        const color = strategyLabels[plan.strategy]?.color || '#7d8a96';
        return (
          <div className="process-result">
            <div className="process-result-row">
              <span className="process-result-label">推荐策略</span>
              <Tag style={{ background: color + '18', color, border: 'none', fontWeight: 600 }}>
                {strategyLabels[plan.strategy]?.label || plan.strategy}
              </Tag>
            </div>
            <div className="process-result-row">
              <span className="process-result-label">分块大小</span>
              <span className="process-result-value">{plan.chunk_size} 字符</span>
            </div>
            <div className="process-result-row">
              <span className="process-result-label">重叠窗口</span>
              <span className="process-result-value">{plan.chunk_overlap} 字符</span>
            </div>
            {plan.analysis?.document_type && (
              <div className="process-result-row">
                <span className="process-result-label">文档类型</span>
                <span className="process-result-value">{plan.analysis.document_type}</span>
              </div>
            )}
            {plan.analysis?.recommended_reasoning && (
              <div className="process-reasoning">{plan.analysis.recommended_reasoning}</div>
            )}
          </div>
        );
      }
      return null;

    case 'chunk':
      if (status === 'done') {
        return (
          <div className="process-result">
            <div className="process-result-row">
              <span className="process-result-label">分块数量</span>
              <span className="process-result-value">{data.count} 个</span>
            </div>
            <div className="process-result-row">
              <span className="process-result-label">使用策略</span>
              <span className="process-result-value">{data.strategy}</span>
            </div>
          </div>
        );
      }
      return null;

    case 'embed':
      if (status === 'done') {
        return (
          <div className="process-result">
            <div className="process-result-row">
              <span className="process-result-label">已嵌入</span>
              <span className="process-result-value">{data.chunks_embedded} 个分块</span>
            </div>
          </div>
        );
      }
      return null;

    case 'complete':
      return (
        <div className="process-result process-result-success">
          <ThunderboltOutlined style={{ color: '#3f6f8f', fontSize: 16 }} />
          <span>处理完成！共 {data.chunk_count} 个分块（{data.strategy_label}）</span>
        </div>
      );

    case 'error':
      return (
        <div className="process-result process-result-error">
          <span>{data.message}</span>
        </div>
      );

    default:
      return null;
  }
}

const ProcessingTasksPage: React.FC = () => {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedTask, setSelectedTask] = useState<any>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [taskDetail, setTaskDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getProcessingTasks();
      setTasks(res.data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchTasks(); }, [fetchTasks]);

  const hasActive = tasks.some(t => t.status === 'pending' || t.status === 'processing');

  useEffect(() => {
    if (hasActive) {
      pollRef.current = setInterval(fetchTasks, 3000);
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [hasActive, fetchTasks]);

  const openDetail = async (task: any) => {
    setSelectedTask(task);
    setDrawerOpen(true);
    setDetailLoading(true);
    try {
      const res = await getProcessingTask(task.id);
      setTaskDetail(res.data);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleRetry = async (taskId: number) => {
    try {
      await retryProcessingTask(taskId);
      message.success('已重新启动处理');
      fetchTasks();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '重试失败');
    }
  };

  const completedCount = tasks.filter(t => t.status === 'completed').length;
  const processingCount = tasks.filter(t => t.status === 'processing' || t.status === 'pending').length;
  const failedCount = tasks.filter(t => t.status === 'failed').length;

  const columns = [
    {
      title: '文档',
      dataIndex: 'document_name',
      key: 'document_name',
      ellipsis: true,
      render: (v: string) => (
        <span style={{ fontWeight: 500, color: '#202a34' }}>{v || '—'}</span>
      ),
    },
    {
      title: '知识库',
      dataIndex: 'knowledge_base_name',
      key: 'knowledge_base_name',
      ellipsis: true,
      render: (v: string) => (
        <span style={{ color: '#667482', fontSize: 13 }}>{v || '—'}</span>
      ),
    },
    {
      title: '当前步骤',
      dataIndex: 'current_step',
      key: 'current_step',
      width: 120,
      render: (v: string, record: any) => {
        if (!v) return <span style={{ color: '#b3bec8' }}>—</span>;
        if (record.status === 'processing') {
          return (
            <span style={{ color: '#3f6f8f', fontSize: 12, fontWeight: 500 }}>
              <LoadingOutlined style={{ marginRight: 4 }} />
              {stepLabels[v] || v}
            </span>
          );
        }
        return (
          <span style={{ fontSize: 12, color: '#667482' }}>{stepLabels[v] || v}</span>
        );
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v: string) => {
        const s = statusConfig[v] || { color: 'default', text: v };
        return <Badge status={s.badge as any} text={<span style={{ fontSize: 12 }}>{s.text}</span>} />;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (v: string) => (
        <span style={{ fontSize: 12, color: '#7d8a96', fontVariantNumeric: 'tabular-nums' }}>
          {v ? new Date(v).toLocaleString('zh-CN') : '—'}
        </span>
      ),
    },
    {
      title: '',
      key: 'action',
      width: 100,
      render: (_: any, record: any) => (
        <Space size={2}>
          <Tooltip title="查看详情">
            <Button
              type="text"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => openDetail(record)}
              className="action-icon-button"
            />
          </Tooltip>
          {record.status === 'failed' && (
            <Tooltip title="重试">
              <Button
                type="text"
                size="small"
                icon={<RedoOutlined />}
                onClick={() => handleRetry(record.id)}
                className="action-icon-button"
              />
            </Tooltip>
          )}
        </Space>
      ),
    },
  ];

  const events = taskDetail?.events || [];

  const buildStepStates = () => {
    return STEPS_CONFIG.map(stepCfg => {
      const stepEvents = events.filter((e: any) => e.step === stepCfg.key);
      const hasDone = stepEvents.some((e: any) => e.status === 'done');
      const hasError = stepEvents.some((e: any) => e.status === 'error');
      const thinkingEvents = stepEvents.filter((e: any) => e.status === 'thinking');
      const doneEvent = stepEvents.find((e: any) => e.status === 'done');

      let status: string = 'pending';
      if (hasError) status = 'error';
      else if (hasDone) status = 'done';
      else if (thinkingEvents.length > 0) status = 'thinking';

      const thinkingTokens = thinkingEvents
        .filter((e: any) => e.data?.token)
        .map((e: any) => e.data.token)
        .join('');

      return {
        ...stepCfg,
        status,
        thinkingTokens,
        result: doneEvent?.data || null,
        message: thinkingEvents.find((e: any) => e.data?.message)?.data?.message || null,
      };
    });
  };

  const stepStates = taskDetail ? buildStepStates() : [];

  const hasActiveDetail = taskDetail?.status === 'processing' || taskDetail?.status === 'pending';

  useEffect(() => {
    if (!drawerOpen || !hasActiveDetail || !selectedTask) return;
    const interval = setInterval(async () => {
      try {
        const res = await getProcessingTask(selectedTask.id);
        setTaskDetail(res.data);
      } catch { /* silent */ }
    }, 2000);
    return () => clearInterval(interval);
  }, [drawerOpen, hasActiveDetail, selectedTask]);

  return (
    <>
      <div className="page-header">
        <div>
          <h2>处理任务</h2>
          <div className="page-desc">查看文档上传后的自动分析进度与模型处理过程</div>
        </div>
        <Button
          icon={<ReloadOutlined />}
          onClick={fetchTasks}
          style={{ borderRadius: 8, fontWeight: 500 }}
        >
          刷新
        </Button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <LoadingOutlined style={{ fontSize: 16, color: '#3f6f8f' }} />
            <span className="stat-label">处理中</span>
          </div>
          <div className="stat-value">{processingCount}</div>
        </div>
        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <CheckCircleOutlined style={{ fontSize: 16, color: '#547b63' }} />
            <span className="stat-label">已完成</span>
          </div>
          <div className="stat-value">{completedCount}</div>
        </div>
        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <CloseCircleOutlined style={{ fontSize: 16, color: '#e74c3c' }} />
            <span className="stat-label">失败</span>
          </div>
          <div className="stat-value">{failedCount}</div>
        </div>
      </div>

      <div className="content-panel">
        <Table
          columns={columns}
          dataSource={tasks}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{
            emptyText: (
              <div className="empty-state">
                <ClockCircleOutlined className="empty-icon" />
                <div className="empty-title">暂无处理任务</div>
                <div className="empty-desc">上传文档后系统会自动分析，处理进度将在此展示</div>
              </div>
            ),
          }}
        />
      </div>

      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ThunderboltOutlined style={{ color: '#3f6f8f' }} />
            <span style={{ fontWeight: 600 }}>处理详情</span>
            {taskDetail?.status === 'processing' && (
              <Tag color="#3f6f8f" style={{ border: 'none', fontSize: 11, marginLeft: 'auto' }}>
                <LoadingOutlined style={{ marginRight: 4 }} />
                处理中
              </Tag>
            )}
            {taskDetail?.status === 'completed' && (
              <Tag color="#547b63" style={{ border: 'none', fontSize: 11, marginLeft: 'auto' }}>
                <CheckCircleOutlined style={{ marginRight: 4 }} />
                已完成
              </Tag>
            )}
            {taskDetail?.status === 'failed' && (
              <Tag color="#e74c3c" style={{ border: 'none', fontSize: 11, marginLeft: 'auto' }}>
                <CloseCircleOutlined style={{ marginRight: 4 }} />
                失败
              </Tag>
            )}
          </div>
        }
        extra={
          <span style={{ fontSize: 12, color: '#7d8a96' }}>
            {taskDetail?.document_name}
          </span>
        }
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setTaskDetail(null); }}
        width={580}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#7d8a96' }}>
            <LoadingOutlined style={{ fontSize: 24 }} />
          </div>
        ) : (
          <div className="process-body">
            {stepStates.map((step: any, i: number) => {
              if (step.status === 'pending' && i > 0 && stepStates[i - 1].status === 'pending') {
                return null;
              }

              return (
                <div key={step.key} className={`process-step process-step-${step.status}`}>
                  <div className="process-step-header">
                    {step.status === 'pending' && <span className="process-step-dot process-step-pending" />}
                    {step.status === 'thinking' && <LoadingOutlined style={{ color: '#3f6f8f', fontSize: 14 }} />}
                    {step.status === 'done' && <CheckCircleOutlined style={{ color: '#547b63', fontSize: 14 }} />}
                    {step.status === 'error' && <CloseCircleOutlined style={{ color: '#e74c3c', fontSize: 14 }} />}
                    <span className="process-step-icon">{step.icon}</span>
                    <span className="process-step-title">{step.title}</span>
                    {step.status === 'thinking' && (
                      <span className="process-step-badge">思考中...</span>
                    )}
                  </div>

                  {step.thinkingTokens && (
                    <div className="process-thinking">
                      <pre className="process-thinking-text">{step.thinkingTokens}</pre>
                    </div>
                  )}

                  {step.status === 'done' && step.result && (
                    <RenderEventDetail event={{ step: step.key, status: 'done', data: step.result }} />
                  )}

                  {step.status === 'thinking' && step.message && !step.thinkingTokens && (
                    <div className="process-result">
                      <div className="process-result-message">{step.message}</div>
                    </div>
                  )}
                </div>
              );
            })}

            {taskDetail?.error_message && (
              <div className="process-step process-step-error">
                <div className="process-step-header">
                  <CloseCircleOutlined style={{ color: '#e74c3c', fontSize: 14 }} />
                  <span className="process-step-title">处理错误</span>
                </div>
                <div className="process-result process-result-error">
                  <span>{taskDetail.error_message}</span>
                </div>
              </div>
            )}

            {hasActiveDetail && (
              <div className="process-streaming-indicator">
                <span className="process-cursor" />
              </div>
            )}

            {taskDetail?.status === 'failed' && (
              <div style={{ padding: '16px', textAlign: 'center' }}>
                <Button
                  type="primary"
                  icon={<RedoOutlined />}
                  onClick={() => handleRetry(taskDetail.id)}
                  style={{ borderRadius: 8 }}
                >
                  重新处理
                </Button>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </>
  );
};

export default ProcessingTasksPage;
