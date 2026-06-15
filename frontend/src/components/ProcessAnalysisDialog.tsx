import React, { useEffect, useRef, useState } from 'react';
import { Drawer, Tag, Button } from 'antd';
import {
  FileTextOutlined, ThunderboltOutlined, CheckCircleOutlined,
  LoadingOutlined, CloseCircleOutlined, ScissorOutlined,
  DatabaseOutlined, AppstoreOutlined, ClearOutlined,
  BulbOutlined,
} from '@ant-design/icons';
import ConvertedTextViewer from './ConvertedTextViewer';

interface ProcessEvent {
  step: string;
  status: string;
  data: any;
}

interface StepState {
  key: string;
  title: string;
  icon: React.ReactNode;
  status: 'pending' | 'thinking' | 'done' | 'error';
  thinkingTokens: string;
  result: any;
}

type StepStatus = 'pending' | 'thinking' | 'done' | 'error';

const STEPS_CONFIG = [
  { key: 'convert', title: '文档转换', icon: <FileTextOutlined /> },
  { key: 'clean', title: '清洗评估', icon: <ClearOutlined /> },
  { key: 'apply', title: '执行清洗', icon: <ScissorOutlined /> },
  { key: 'analyze', title: '分块分析', icon: <BulbOutlined /> },
  { key: 'chunk', title: '执行分块', icon: <AppstoreOutlined /> },
  { key: 'embed', title: '向量化存储', icon: <DatabaseOutlined /> },
];

const strategyColors: Record<string, string> = {
  recursive: '#3f6f8f',
  fixed: '#7d8a96',
  parent_child: '#3f6f8f',
  semantic: '#547b63',
  hybrid: '#7a678c',
};

interface ProcessAnalysisDialogProps {
  open: boolean;
  onClose: () => void;
  docId: number | null;
  kbId: number | null;
  fileName: string;
  events: ProcessEvent[];
  isStreaming: boolean;
}

function StepStatusIcon({ status }: { status: string }) {
  if (status === 'pending') {
    return <span className="process-step-dot process-step-pending" />;
  }
  if (status === 'thinking') {
    return <LoadingOutlined style={{ color: '#3f6f8f', fontSize: 14 }} />;
  }
  if (status === 'done') {
    return <CheckCircleOutlined style={{ color: '#547b63', fontSize: 14 }} />;
  }
  if (status === 'error') {
    return <CloseCircleOutlined style={{ color: '#e74c3c', fontSize: 14 }} />;
  }
  return null;
}

function RenderStepResult({ step, data, onViewConverted }: { step: string; data: any; onViewConverted?: () => void }) {
  if (!data || Object.keys(data).length === 0) return null;

  switch (step) {
    case 'convert':
    case 'extract':
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
            <Button
              type="link"
              size="small"
              icon={<FileTextOutlined />}
              onClick={onViewConverted}
              style={{ padding: 0, marginTop: 8, fontSize: 12 }}
            >
              查看完整转换内容（{data.chars?.toLocaleString()} 字符）
            </Button>
          )}
        </div>
      );

    case 'clean':
      if (data.assessment) {
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

    case 'analyze':
      if (data.plan) {
        const plan = data.plan;
        const color = strategyColors[plan.strategy] || '#7d8a96';
        const strategyLabels: Record<string, string> = {
          recursive: '递归字符分块',
          fixed: '固定大小分块',
          parent_child: '父子分块',
          semantic: '语义分块',
          hybrid: '混合分块',
        };
        return (
          <div className="process-result">
            <div className="process-result-row">
              <span className="process-result-label">推荐策略</span>
              <Tag style={{ background: color + '18', color, border: 'none', fontWeight: 600 }}>
                {strategyLabels[plan.strategy] || plan.strategy}
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

    case 'embed':
      return (
        <div className="process-result">
          <div className="process-result-row">
            <span className="process-result-label">已嵌入</span>
            <span className="process-result-value">{data.chunks_embedded} 个分块</span>
          </div>
        </div>
      );

    case 'complete':
      return (
        <div className="process-result process-result-success">
          <ThunderboltOutlined style={{ color: '#3f6f8f', fontSize: 16 }} />
          <span>
            处理完成！共 {data.chunk_count} 个分块
            （{data.strategy_label}）
          </span>
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

const ProcessAnalysisDialog: React.FC<ProcessAnalysisDialogProps> = ({
  open,
  onClose,
  docId,
  kbId,
  fileName,
  events,
  isStreaming,
}) => {
  const bodyRef = useRef<HTMLDivElement>(null);

  const initialSteps: StepState[] = STEPS_CONFIG.map((s) => ({
    key: s.key,
    title: s.title,
    icon: s.icon,
    status: 'pending' as StepStatus,
    thinkingTokens: '',
    result: null,
  }));

  const [steps, setSteps] = useState<StepState[]>(initialSteps);
  const [convertedViewerOpen, setConvertedViewerOpen] = useState(false);

  useEffect(() => {
    const newSteps: StepState[] = STEPS_CONFIG.map((s) => ({
      key: s.key,
      title: s.title,
      icon: s.icon,
      status: 'pending',
      thinkingTokens: '',
      result: null,
    }));

    for (const event of events) {
      const stepIdx = newSteps.findIndex((s) => s.key === event.step);
      if (stepIdx === -1) {
        if (event.step === 'error') {
          const lastActive = [...newSteps].reverse().find((s) => s.status !== 'pending');
          if (lastActive) {
            lastActive.status = 'error';
            lastActive.result = event.data;
          }
        }
        continue;
      }

      const step = newSteps[stepIdx];
      if (event.status === 'thinking') {
        step.status = 'thinking';
        if (event.data?.token) {
          step.thinkingTokens += event.data.token;
        }
        if (event.data?.message) {
          step.result = event.data;
        }
      } else if (event.status === 'done') {
        step.status = 'done';
        step.result = event.data;
      } else if (event.status === 'error') {
        step.status = 'error';
        step.result = event.data;
      }
    }

    setSteps(newSteps);
  }, [events]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [steps]);

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={560}
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ThunderboltOutlined style={{ color: '#3f6f8f' }} />
          <span style={{ fontWeight: 600 }}>LLM 文档分析</span>
          {isStreaming && (
            <Tag color="#3f6f8f" style={{ border: 'none', fontSize: 11, marginLeft: 'auto' }}>
              <LoadingOutlined style={{ marginRight: 4 }} />
              分析中
            </Tag>
          )}
        </div>
      }
      extra={
        <span style={{ fontSize: 12, color: '#7d8a96' }}>{fileName}</span>
      }
    >
      <div className="process-body" ref={bodyRef}>
        {steps.map((step, i) => {
          if (step.status === 'pending' && !steps.slice(0, i).some((s) => s.status !== 'pending')) {
            // Don't show pending steps until previous step is done
            if (i > 0 && steps[i - 1].status === 'pending') return null;
          }

          return (
            <div
              key={step.key}
              className={`process-step process-step-${step.status}`}
            >
              <div className="process-step-header">
                <StepStatusIcon status={step.status} />
                <span className="process-step-icon">{step.icon}</span>
                <span className="process-step-title">{step.title}</span>
                {step.status === 'thinking' && (
                  <span className="process-step-badge">思考中...</span>
                )}
              </div>

              {/* Thinking tokens (streamed LLM output) */}
              {step.thinkingTokens && (
                <div className="process-thinking">
                  <pre className="process-thinking-text">{step.thinkingTokens}</pre>
                </div>
              )}

              {/* Non-token result data */}
              {step.status === 'done' && step.result && (
                <RenderStepResult step={step.key} data={step.result} onViewConverted={() => setConvertedViewerOpen(true)} />
              )}
              {step.status === 'error' && step.result && (
                <RenderStepResult step="error" data={step.result} />
              )}
              {step.status === 'thinking' && step.result && !step.thinkingTokens && (
                <div className="process-result">
                  {step.result.message && (
                    <div className="process-result-message">{step.result.message}</div>
                  )}
                  {step.result.actions?.length > 0 && (
                    <div className="process-issues">
                      {step.result.actions.map((action: string, j: number) => (
                        <div key={j} className="process-issue-item">• {action}</div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {isStreaming && (
          <div className="process-streaming-indicator">
            <span className="process-cursor" />
          </div>
        )}
      </div>

      <ConvertedTextViewer
        open={convertedViewerOpen}
        onClose={() => setConvertedViewerOpen(false)}
        kbId={kbId!}
        docId={docId!}
        fileName={fileName}
      />
    </Drawer>
  );
};

export default ProcessAnalysisDialog;
