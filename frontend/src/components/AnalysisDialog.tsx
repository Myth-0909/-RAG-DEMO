import React from 'react';
import { Modal, Tag } from 'antd';
import {
  FileTextOutlined, BarChartOutlined, ThunderboltOutlined,
  TableOutlined, PictureOutlined, UnorderedListOutlined,
  OrderedListOutlined, CodeOutlined, FontSizeOutlined,
} from '@ant-design/icons';

const strategyLabels: Record<string, { label: string; color: string; desc: string }> = {
  recursive: {
    label: '递归字符分块',
    color: '#3f6f8f',
    desc: '按段落和标点符号逐层递归切分，适合大多数文档。',
  },
  fixed: {
    label: '固定大小分块',
    color: '#7d8a96',
    desc: '按固定字符数切分，简单直接。',
  },
  parent_child: {
    label: '父子分块',
    color: '#3f6f8f',
    desc: '大段作为"父块"保留上下文，内部再切为"子块"，适合层级结构清晰的文档。',
  },
  semantic: {
    label: '语义分块',
    color: '#547b63',
    desc: '通过语义相似度合并相邻片段，适合叙述型长文本。',
  },
  hybrid: {
    label: '混合分块',
    color: '#7a678c',
    desc: '根据章节特征自动选择不同分块策略，适合内容混合的文档。',
  },
};

interface AnalysisDialogProps {
  open: boolean;
  onClose: () => void;
  doc: {
    original_filename: string;
    file_type: string;
    file_size: number;
    chunk_count: number;
    metadata_json?: {
      content_analysis?: {
        total_chars: number;
        total_sentences: number;
        total_paragraphs: number;
        headings: number;
        heading_levels: number;
        sections: number;
        avg_section_chars: number;
        lists: number;
        tables: number;
        images: number;
        code_blocks: number;
        avg_sentence_length: number;
        avg_paragraph_length: number;
      };
      scores?: {
        structure: number;
        narrative: number;
        density: number;
        hierarchy: number;
      };
      strategy?: {
        selected: string;
        label: string;
        reasoning: string;
      };
      cleaning?: {
        original_chars: number;
        cleaned_chars: number;
        chars_removed: number;
        encoding_fixed: number;
        artifacts_removed: number;
      };
    };
  } | null;
}

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.round(value * 100);
  return (
    <div className="analysis-score-bar">
      <div className="analysis-score-label">{label}</div>
      <div className="analysis-score-track">
        <div
          className="analysis-score-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <div className="analysis-score-value">{pct}%</div>
    </div>
  );
}

const AnalysisDialog: React.FC<AnalysisDialogProps> = ({ open, onClose, doc }) => {
  if (!doc) return null;

  const meta = doc.metadata_json;
  const analysis = meta?.content_analysis;
  const scores = meta?.scores;
  const strategy = meta?.strategy;
  const cleaning = meta?.cleaning;
  const strategyInfo = strategy ? strategyLabels[strategy.selected] : null;

  const messages: { role: 'system' | 'analyst'; icon: React.ReactNode; title: string; content: React.ReactNode }[] = [];

  // Message 1: Document overview
  messages.push({
    role: 'system',
    icon: <FileTextOutlined />,
    title: '文档概览',
    content: (
      <div className="analysis-stats-grid">
        <div className="analysis-stat">
          <span className="analysis-stat-num">{analysis?.total_chars?.toLocaleString() || '0'}</span>
          <span className="analysis-stat-label">总字符</span>
        </div>
        <div className="analysis-stat">
          <span className="analysis-stat-num">{analysis?.total_paragraphs || 0}</span>
          <span className="analysis-stat-label">段落</span>
        </div>
        <div className="analysis-stat">
          <span className="analysis-stat-num">{analysis?.total_sentences || 0}</span>
          <span className="analysis-stat-label">句子</span>
        </div>
        <div className="analysis-stat">
          <span className="analysis-stat-num">{doc.chunk_count}</span>
          <span className="analysis-stat-label">分块数</span>
        </div>
      </div>
    ),
  });

  // Message 2: Content structure detected
  if (analysis) {
    const structureItems: { icon: React.ReactNode; text: string }[] = [];

    if (analysis.headings > 0) {
      structureItems.push({
        icon: <OrderedListOutlined />,
        text: `检测到 ${analysis.headings} 个标题${analysis.heading_levels > 1 ? `，共 ${analysis.heading_levels} 层层级` : '（扁平结构）'}`,
      });
    }
    if (analysis.sections > 1) {
      structureItems.push({
        icon: <FontSizeOutlined />,
        text: `划分为 ${analysis.sections} 个章节，平均每章 ${Math.round(analysis.avg_section_chars)} 字符`,
      });
    }
    if (analysis.tables > 0) {
      structureItems.push({
        icon: <TableOutlined />,
        text: `检测到 ${analysis.tables} 个表格`,
      });
    }
    if (analysis.images > 0) {
      structureItems.push({
        icon: <PictureOutlined />,
        text: `通过 OCR 识别了 ${analysis.images} 张图片中的文字`,
      });
    }
    if (analysis.lists > 0) {
      structureItems.push({
        icon: <UnorderedListOutlined />,
        text: `检测到 ${analysis.lists} 个列表项`,
      });
    }
    if (analysis.code_blocks > 0) {
      structureItems.push({
        icon: <CodeOutlined />,
        text: `检测到 ${analysis.code_blocks} 个代码块`,
      });
    }

    if (structureItems.length > 0) {
      messages.push({
        role: 'analyst',
        icon: <BarChartOutlined />,
        title: '内容结构分析',
        content: (
          <div className="analysis-structure-list">
            {structureItems.map((item, i) => (
              <div key={i} className="analysis-structure-item">
                <span className="analysis-structure-icon">{item.icon}</span>
                <span>{item.text}</span>
              </div>
            ))}
          </div>
        ),
      });
    }
  }

  // Message 3: Scores
  if (scores) {
    messages.push({
      role: 'analyst',
      icon: <BarChartOutlined />,
      title: '内容特征评分',
      content: (
        <div className="analysis-scores">
          <ScoreBar label="层级深度" value={scores.hierarchy} color="#3f6f8f" />
          <ScoreBar label="结构化程度" value={scores.structure} color="#3f6f8f" />
          <ScoreBar label="叙述流畅性" value={scores.narrative} color="#547b63" />
          <ScoreBar label="信息密度" value={scores.density} color="#7a678c" />
        </div>
      ),
    });
  }

  // Message 4: Strategy decision
  if (strategy && strategyInfo) {
    messages.push({
      role: 'analyst',
      icon: <ThunderboltOutlined />,
      title: '分块策略决策',
      content: (
        <div className="analysis-strategy">
          <div className="analysis-strategy-header">
            <Tag style={{
              background: strategyInfo.color + '18',
              color: strategyInfo.color,
              border: 'none',
              fontSize: 13,
              fontWeight: 600,
              padding: '4px 12px',
              borderRadius: 6,
            }}>
              {strategyInfo.label}
            </Tag>
          </div>
          <div className="analysis-strategy-desc">{strategyInfo.desc}</div>
          <div className="analysis-strategy-reason">
            <div className="analysis-strategy-reason-label">选择理由</div>
            <div>{strategy.reasoning}</div>
          </div>
        </div>
      ),
    });
  }

  // Message 5: Cleaning summary
  if (cleaning && cleaning.chars_removed > 0) {
    messages.push({
      role: 'system',
      icon: <FileTextOutlined />,
      title: '内容清洗',
      content: (
        <div style={{ fontSize: 13, color: '#667482', lineHeight: 1.7 }}>
          清除了 {cleaning.chars_removed.toLocaleString()} 个冗余字符
          {cleaning.encoding_fixed > 0 && `，修复了 ${cleaning.encoding_fixed} 处编码问题`}
          {cleaning.artifacts_removed > 0 && `，移除了 ${cleaning.artifacts_removed} 处文档伪影`}
          。
        </div>
      ),
    });
  }

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={null}
      footer={null}
      width={520}
      className="analysis-dialog"
      closable={true}
      destroyOnHidden
    >
      <div className="analysis-dialog-header">
        <ThunderboltOutlined style={{ color: '#3f6f8f', fontSize: 18 }} />
        <div>
          <div className="analysis-dialog-title">文档分析完成</div>
          <div className="analysis-dialog-filename">{doc.original_filename}</div>
        </div>
      </div>

      <div className="analysis-dialog-body">
        {messages.map((msg, i) => (
          <div key={i} className={`analysis-bubble analysis-bubble-${msg.role}`}>
            <div className="analysis-bubble-header">
              <span className="analysis-bubble-icon">{msg.icon}</span>
              <span className="analysis-bubble-title">{msg.title}</span>
            </div>
            <div className="analysis-bubble-content">{msg.content}</div>
          </div>
        ))}
      </div>

      <div className="analysis-dialog-footer">
        <button className="analysis-dialog-btn" onClick={onClose}>
          知道了
        </button>
      </div>
    </Modal>
  );
};

export default AnalysisDialog;
