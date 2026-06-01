---
name: remove-ai-design-patterns
description: 识别和消除 AI 生成前端代码中的典型设计指纹（紫蓝渐变、默认配色、通用布局等）
source: auto-skill
extracted_at: '2026-06-01T10:20:00.000Z'
---

# 消除 AI 设计指纹

AI 生成的前端代码有一套高度可辨识的视觉模式。以下是识别清单和替代方案。

## 1. 紫蓝渐变（最高频指纹）

**问题**：`linear-gradient(135deg, #667eea, #764ba2)` 几乎是 AI 生成的标配登录页背景。

**修复**：
- 暗色分割布局（左品牌区 + 右表单区）
- 温暖的米白/奶油色背景 + 单色强调
- 带微妙噪点纹理的纯色背景

## 2. 默认蓝色主色

**问题**：Ant Design 默认蓝 `#1677ff`、Tailwind 默认蓝 `#3b82f6` 被大量 AI 代码直接使用。

**修复**：选择一个有辨识度的主色并全局统一：
- 暖橘 `#e8653a`（温暖专业感）
- 深绿 `#2d6a4f`（稳重可靠）
- 靛蓝 `#4338ca`（现代但不俗套）

## 3. 纯黑投影

**问题**：`box-shadow: 0 8px 24px rgba(0,0,0,0.15)` 纯黑半透明阴影。

**修复**：使用暖色调投影匹配背景色温：
```css
box-shadow: 0 1px 3px rgba(30,27,22,0.04), 0 4px 12px rgba(30,27,22,0.03);
```

## 4. 零自定义字体

**问题**：完全依赖系统字体或 Inter。

**修复**：引入一个有辨识度的字体：
- DM Sans（几何感，适合后台管理）
- Geist（Vercel 风格，现代）
- Outfit（圆润，友好）

## 5. 三列等宽卡片

**问题**：特性展示永远是三个等宽等高的 Card 并排。

**修复**：
- 2 列 zig-zag 布局
- 统计数字卡片（左图标 + 大数字 + 小标签）
- 非对称网格

## 6. 千篇一律的 Table-in-Card

**问题**：每个管理页面都是 `<Card title="xxx"><Table ... /></Card>`。

**修复**：
- 统一 `page-header` 模式（标题 + 描述 + 操作按钮）
- Table 放在无边框圆角容器中
- 状态用指示灯（小圆点）替代 Tag
- 自定义空状态（图标 + 标题 + 描述）

## 7. 基础聊天气泡

**问题**：纯色圆角矩形，左右对称。

**修复**：
- 非对称圆角（用户 `16px 16px 4px 16px`，助手 `16px 16px 16px 4px`）
- 用户气泡深灰/黑色，助手气泡白色 + 细边框
- 来源引用区域用分割线 + 小号字体

## 8. 无纹理无动画

**问题**：纯平面感，元素出现/消失无过渡。

**修复**：
- SVG 噪点纹理覆盖层（`opacity: 0.018`，`pointer-events: none`）
- 全局 cubic-bezier 过渡（`all 0.2s cubic-bezier(0.4, 0, 0.2, 1)`）
- 按钮点击反馈（`scale(0.97)`）
- 卡片悬停提升（`translateY(-2px)`）

## 9. 通用空状态

**问题**：Ant Design `<Empty description="xxx" />`，所有页面长得一样。

**修复**：自定义空状态组件：
```jsx
<div className="empty-state">
  <DatabaseOutlined className="empty-icon" />
  <div className="empty-title">暂无知识库</div>
  <div className="empty-desc">点击右上角按钮创建第一个知识库</div>
</div>
```
每个页面用不同图标，描述文案具体到当前上下文。

## 10. Ant Design 主题定制要点

```tsx
<ConfigProvider theme={{
  token: {
    colorPrimary: '#e8653a',       // 替换默认蓝
    colorBgLayout: '#f4f3f1',      // 暖灰背景
    colorBorder: '#eae8e4',        // 暖色边框
    borderRadius: 8,               // 统一圆角
    fontFamily: "'DM Sans', ...",  // 自定义字体
    boxShadow: '0 1px 3px rgba(30,27,22,0.04)',  // 暖色投影
  },
  components: {
    Table: {
      headerBg: '#fafaf8',         // 表头暖灰
      headerColor: '#6b6560',      // 表头文字
    },
    Tag: {
      defaultBg: '#f4f3f1',        // Tag 暖灰背景
    },
  },
}}>
```

## CSS 全局基础模板

```css
/* 噪点纹理 */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: none;
  opacity: 0.018;
  background-image: url("data:image/svg+xml,...fractalNoise...");
}

/* 自定义滚动条 */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.12); border-radius: 3px; }

/* 全局过渡 */
a, button, input, .ant-btn, .ant-card { transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); }

/* 按钮点击反馈 */
.ant-btn:active { transform: scale(0.97); }

/* 表头风格 */
.ant-table-thead > tr > th {
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #6b6560;
}
```

## 检查清单

- [ ] 登录页没有紫蓝渐变
- [ ] 主色不是默认蓝
- [ ] 投影不是纯黑 rgba
- [ ] 有自定义字体
- [ ] 有噪点纹理
- [ ] 有全局过渡动画
- [ ] 按钮有点击反馈
- [ ] 空状态是自定义的
- [ ] 侧边栏有品牌标识
- [ ] 状态用小圆点而非 Tag
