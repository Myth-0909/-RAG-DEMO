import { useEffect, useState } from 'react';
import { Drawer, Spin } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import { getConvertedText } from '../services/api';

interface ConvertedTextViewerProps {
  open: boolean;
  onClose: () => void;
  kbId: number;
  docId: number;
  fileName: string;
}

export default function ConvertedTextViewer({
  open,
  onClose,
  kbId,
  docId,
  fileName,
}: ConvertedTextViewerProps) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<{
    converted_text: string;
    converter: string;
    filename: string;
  } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open && kbId && docId) {
      setLoading(true);
      setError('');
      setData(null);
      getConvertedText(kbId, docId)
        .then((res) => {
          setData(res.data);
        })
        .catch((err: any) => {
          setError(err.response?.data?.detail || '获取转换内容失败');
        })
        .finally(() => setLoading(false));
    }
  }, [open, kbId, docId]);

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={720}
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileTextOutlined />
          <span style={{ fontWeight: 600 }}>{fileName} — 转换内容</span>
        </div>
      }
      extra={
        data ? (
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>
            {data.converter} · {data.converted_text.length.toLocaleString()} 字符
          </span>
        ) : null
      }
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <Spin size="large" tip="加载转换内容..." />
        </div>
      ) : error ? (
        <div style={{ textAlign: 'center', padding: '80px 0', color: 'var(--red)' }}>
          {error}
        </div>
      ) : data ? (
        <pre
          style={{
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontFamily: '"SF Mono", "Fira Code", "Cascadia Code", monospace',
            fontSize: 13,
            lineHeight: 1.7,
            color: '#2c2c2c',
            background: '#faf9f7',
            padding: 20,
            borderRadius: 8,
            maxHeight: 'calc(100vh - 160px)',
            overflowY: 'auto',
            margin: 0,
            border: '1px solid #eee',
          }}
        >
          {data.converted_text}
        </pre>
      ) : null}
    </Drawer>
  );
}
