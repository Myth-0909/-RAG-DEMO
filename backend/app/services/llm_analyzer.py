"""
LLM-based document analyzer.

Uses the LLM to:
1. Assess whether extracted text needs data cleaning
2. Analyze content and recommend chunking strategy (outputs JSON)

Supports streaming to show the model's thinking process in real-time.
Includes timeout, retry, and graceful fallback on LLM failures.
"""

import json
import re
import time
import logging
from typing import Dict, Any, Tuple, Callable, List

import httpx
from openai import OpenAI

from app.config import settings
from app.services.model_config_service import get_current_llm_config

logger = logging.getLogger(__name__)

_client = None

# Max chars sent to LLM per call (keeps requests within model context limits)
MAX_CLEANING_CHARS = 6000
MAX_CHUNKING_CHARS = 6000

# LLM request timeout (seconds) — generous for streaming
_LLM_TIMEOUT = httpx.Timeout(connect=10.0, read=180.0, write=10.0, pool=10.0)

# Retry config
_MAX_RETRIES = 2
_RETRY_DELAY = 3.0


def get_llm_client() -> OpenAI:
    """Create a new client per request to respect dynamic config changes."""
    cfg = get_current_llm_config()
    return OpenAI(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        timeout=_LLM_TIMEOUT,
        max_retries=0,
    )


def _truncate_text(text: str, max_chars: int) -> Tuple[str, bool]:
    """Truncate text for LLM context window. Returns (text, was_truncated)."""
    if len(text) <= max_chars:
        return text, False
    half = max_chars // 2
    return text[:half] + "\n\n... [中间内容省略] ...\n\n" + text[-half:], True


def _call_llm_stream(
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    on_thinking: Callable[[str], None],
) -> str:
    """
    Call LLM with streaming, retry on transient failures.
    Returns the full response text. Raises on persistent failure.
    """
    client = get_llm_client()
    cfg = get_current_llm_config()
    last_error = None

    for attempt in range(_MAX_RETRIES + 1):
        if attempt > 0:
            logger.info(f"LLM retry attempt {attempt}/{_MAX_RETRIES}")
            time.sleep(_RETRY_DELAY * attempt)

        try:
            full_response = ""
            stream = client.chat.completions.create(
                model=cfg.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,
                max_tokens=max_tokens,
                stream=True,
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    on_thinking(token)

            return full_response

        except Exception as e:
            last_error = e
            logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")
            continue

    raise last_error


# ─── Step 1: Cleaning Assessment ─────────────────────────────────────────────

CLEANING_SYSTEM_PROMPT = """你是一个数据清洗分析专家。分析从文档中提取的文本，判断是否需要数据清洗。

关注以下问题：
1. 编码异常：Unicode 特殊字符、乱码
2. 格式噪音：多余空行、重复空格
3. 文档伪影：PDF 页码、页眉页脚、断行连字符
4. OCR 错误
5. 表格/列表格式损坏

## 针对混乱场景的具体清洗规则

### 表格处理
- 若表格行列错乱、合并单元格混乱：建议用统一字符分隔符（如 |）重新对齐，尽量恢复行列结构。若无法判断原始结构，按最可能的网格形式输出，并标记 [表格结构推测，待确认]
- 若表格内容跨页或中断，标记 [表格接上页]

### 图片处理
- 不评估图片内容，建议输出占位标记 [图片：原始图注或文件名]，若无图注则标记 [图片]
- 若图片内包含文字且无法提取，标记（图中文字未提取，需人工查阅原图）

### 标题与层级识别
- 根据字号、加粗、缩进或前后文逻辑，推测标题层级。使用 Markdown 风格标记：# 一级，## 二级，### 三级
- 特别注意：中文文档中编号样式相同的行不一定是同级标题（如「三、系统架构」下的「1 前端」「2 后端」是子项，不是独立标题），需从语义和上下文判断父子关系
- 若无法确定层级，统一用 ### 标记，并标注（标题层级推测）

### 段落与换行
- 将连续文本合并为自然段落（删除孤立换行符），保留原文中的空行表示分段
- 列表项（如 -、1.）保留原样，每项单独一行

### 特殊元素
- 页眉、页脚、页码：移动到文档开始处用 [页眉：...]、[页脚：...]、[页码：...] 标记，注明原位置
- 水印文字：若可提取，在文档末尾增加 [水印文字：...]

以 JSON 格式回复（不要使用代码块）：
{
  "needs_cleaning": true或false,
  "issues_found": ["问题1", "问题2"],
  "cleaning_actions": ["操作1", "操作2"],
  "severity": "none/low/medium/high",
  "reasoning": "分析推理过程"
}"""

CLEANING_USER_TEMPLATE = """{file_type} 文档提取文本，总长度 {total_chars} 字符。
{truncation_note}

--- 文本开始 ---
{text}
--- 文本结束 ---

请分析是否需要数据清洗，以 JSON 格式回复。"""


def assess_cleaning_stream(
    text: str,
    file_type: str,
    on_thinking: Callable[[str], None],
) -> Dict[str, Any]:
    """
    Use LLM (streaming) to assess whether text needs cleaning.
    Falls back to rule-based assessment on LLM failure.
    """
    fallback = _fallback_cleaning_assessment(text, file_type)

    truncated, was_truncated = _truncate_text(text, MAX_CLEANING_CHARS)
    truncation_note = f"（原文 {len(text)} 字符，此处为截取样本）" if was_truncated else ""

    user_msg = CLEANING_USER_TEMPLATE.format(
        file_type=file_type.upper(),
        total_chars=len(text),
        truncation_note=truncation_note,
        text=truncated,
    )

    try:
        response = _call_llm_stream(
            system_prompt=CLEANING_SYSTEM_PROMPT,
            user_message=user_msg,
            max_tokens=800,
            on_thinking=on_thinking,
        )
        result = _parse_json_response(response, fallback=fallback)
        # Ensure required keys exist
        for key in ("needs_cleaning", "issues_found", "cleaning_actions", "severity"):
            if key not in result:
                result[key] = fallback[key]
        return result
    except Exception as e:
        logger.error(f"LLM cleaning assessment failed, using fallback: {e}")
        on_thinking(f"\n\n⚠ LLM 调用失败（{e}），切换到规则分析模式...")
        return fallback


def _fallback_cleaning_assessment(text: str, file_type: str) -> Dict[str, Any]:
    """Rule-based fallback when LLM is unavailable."""
    issues = []
    actions = []

    if "\u00a0" in text or "\u200b" in text or "\ufeff" in text:
        issues.append("发现 Unicode 特殊字符")
        actions.append("清理特殊编码字符")

    if "\n\n\n\n" in text:
        issues.append("发现多余连续空行")
        actions.append("合并多余空行")

    if file_type == "pdf":
        page_nums = len(re.findall(r'\n\s*\d+\s*\n', text))
        if page_nums > 0:
            issues.append(f"发现 {page_nums} 处 PDF 页码")
            actions.append("移除 PDF 页码")
        if re.search(r'第\s*\d+\s*页\s*共\s*\d+\s*页', text):
            issues.append("发现页眉页脚标记")
            actions.append("移除页眉页脚")

    severity = "none"
    if len(issues) >= 3:
        severity = "high"
    elif len(issues) >= 1:
        severity = "low"

    return {
        "needs_cleaning": len(issues) > 0,
        "issues_found": issues if issues else ["未发现明显问题"],
        "cleaning_actions": actions if actions else ["无需清洗"],
        "severity": severity,
        "reasoning": f"基于规则检测到 {len(issues)} 个问题（LLM 不可用时的降级分析）",
    }


# ─── Step 2: Chunking Strategy Analysis ──────────────────────────────────────

CHUNKING_SYSTEM_PROMPT = """你是一个文档分块策略专家。分析文档内容特征，输出最优的向量化分块方案。

## 标题层级识别（重要）
文档中常出现编号样式一致的歧义标题，需要从语义上判断父子关系而非仅看编号格式：
- "三、系统架构" 下的 "1 前端设计" "2 后端设计" 是该章节的子项，不是独立标题
- "1. 概述" 和 "1.1 背景" 是父子关系，但 "1 xxx" 紧跟在 "五、xxx" 之后可能是子项
- 判断依据：子项编号通常在其父标题之后连续出现、内容围绕父标题展开

请在 heading_hierarchy 中描述真实的标题层级树，明确标注哪些是父标题、哪些是其子项。这直接影响分块时是否将子项与父标题保留在同一个块中。

## 可用策略
1. recursive（递归字符分块）：按段落和标点逐层切分，适合大多数文档
2. fixed（固定大小分块）：按固定字符数切分，适合格式不规范的文档
3. parent_child（父子分块）：大段作为父块，内部切为子块，适合多层标题层级的技术文档
4. semantic（语义分块）：通过语义相似度合并片段，适合叙述型长文本
5. hybrid（混合分块）：表格独立处理，不同章节用不同策略，适合混合文档

## 输出 JSON（不要使用代码块）
{
  "strategy": "策略名称",
  "chunk_size": 300到800之间的整数,
  "chunk_overlap": 50到200之间的整数,
  "analysis": {
    "document_type": "文档类型",
    "structure_features": "结构特征",
    "content_characteristics": "内容特征",
    "heading_hierarchy": "用树形描述标题的父子层级关系，标注哪些是父标题、哪些子项是其下一级",
    "heading_boundaries": [{"parent": "父标题文本", "children": ["子项1", "子项2"], "note": "这些子项应归属于该父标题"}],
    "special_elements": [],
    "recommended_reasoning": "选择理由（需说明标题层级如何影响策略选择）"
  },
  "quality_score": 0.0到1.0
}"""

CHUNKING_USER_TEMPLATE = """{file_type} 文档内容，总长度 {total_chars} 字符。
{truncation_note}

--- 文档内容开始 ---
{text}
--- 文档内容结束 ---

请分析内容特征，输出分块方案 JSON。"""


def analyze_chunking_strategy_stream(
    text: str,
    file_type: str,
    on_thinking: Callable[[str], None],
) -> Dict[str, Any]:
    """
    Use LLM (streaming) to analyze content and recommend chunking strategy.
    Falls back to heuristic analysis on LLM failure.
    """
    fallback = _fallback_chunking_plan(text)

    truncated, was_truncated = _truncate_text(text, MAX_CHUNKING_CHARS)
    truncation_note = f"（原文 {len(text)} 字符，此处为截取样本）" if was_truncated else ""

    user_msg = CHUNKING_USER_TEMPLATE.format(
        file_type=file_type.upper(),
        total_chars=len(text),
        truncation_note=truncation_note,
        text=truncated,
    )

    try:
        response = _call_llm_stream(
            system_prompt=CHUNKING_SYSTEM_PROMPT,
            user_message=user_msg,
            max_tokens=1000,
            on_thinking=on_thinking,
        )
        plan = _parse_json_response(response, fallback=None)
        if plan is None:
            logger.warning("LLM chunking response could not be parsed, using fallback")
            plan = fallback
        plan = _normalize_chunking_plan(plan)
        return plan
    except Exception as e:
        logger.error(f"LLM chunking analysis failed, using fallback: {e}")
        on_thinking(f"\n\n⚠ LLM 调用失败（{e}），切换到规则分析模式...")
        return fallback


# ─── Response Parsing ─────────────────────────────────────────────────────────

def _parse_json_response(response: str, fallback: Any = None) -> Any:
    """Extract and parse JSON from LLM response, handling various formats."""
    text = response.strip()

    # Remove markdown code block wrappers
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start != -1 and brace_end > brace_start:
        json_str = text[brace_start:brace_end + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Fix trailing commas
            fixed = re.sub(r',\s*([}\]])', r'\1', json_str)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

    logger.warning(f"Failed to parse LLM JSON response: {text[:200]}...")
    return fallback


def _normalize_chunking_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure the chunking plan has valid values."""
    valid_strategies = {"recursive", "fixed", "parent_child", "semantic", "hybrid"}

    strategy = plan.get("strategy", "recursive")
    if strategy not in valid_strategies:
        strategy = "recursive"

    chunk_size = plan.get("chunk_size", 500)
    if not isinstance(chunk_size, (int, float)):
        chunk_size = 500
    chunk_size = max(200, min(1500, int(chunk_size)))

    chunk_overlap = plan.get("chunk_overlap", 100)
    if not isinstance(chunk_overlap, (int, float)):
        chunk_overlap = 100
    chunk_overlap = max(0, min(chunk_size // 2, int(chunk_overlap)))

    plan["strategy"] = strategy
    plan["chunk_size"] = chunk_size
    plan["chunk_overlap"] = chunk_overlap

    if "analysis" not in plan or not isinstance(plan["analysis"], dict):
        plan["analysis"] = {
            "document_type": "未知",
            "structure_features": "",
            "content_characteristics": "",
            "heading_hierarchy": "",
            "special_elements": [],
            "recommended_reasoning": "LLM 未提供详细分析",
        }

    return plan


def _fallback_chunking_plan(text: str) -> Dict[str, Any]:
    """Generate a fallback chunking plan based on simple heuristics."""
    total_chars = len(text)
    if total_chars < 1000:
        strategy = "recursive"
        reasoning = f"文档较短（{total_chars} 字符），使用递归分块"
    elif text.count('|') > 20:
        strategy = "hybrid"
        reasoning = "文档包含表格，使用混合分块"
    elif re.search(r'^#{2,3}\s', text, re.MULTILINE):
        strategy = "parent_child"
        reasoning = "文档有多层标题，使用父子分块"
    else:
        strategy = "recursive"
        reasoning = "基于规则分析，使用默认递归分块"

    return {
        "strategy": strategy,
        "chunk_size": 500,
        "chunk_overlap": 100,
        "analysis": {
            "document_type": "未分析",
            "structure_features": "",
            "content_characteristics": "",
            "heading_hierarchy": "未分析（LLM 不可用，基于规则回退）",
            "heading_boundaries": [],
            "special_elements": [],
            "recommended_reasoning": reasoning,
        },
        "quality_score": 0.5,
    }


# ─── Step 5.5: LLM Chunk Refinement ───────────────────────────────────────

REFINE_SYSTEM_PROMPT = """你是文档分块精炼专家。审核代码分块产出的每个 chunk，识别并修复影响检索质量的问题。

## 操作类型

对每个 chunk，选择以下操作之一：

### keep（保留）
chunk 语义完整、表述清晰、不会引起歧义，无需修改。
例如：「薪酬福利的联系人是周筱莉，联系方式是0571-86621852。」— 精确且自洽 ✓

### rewrite（重写）
chunk 包含正确信息，但表述可能导致检索歧义或语义不完整。请重写为更精确的文本。

示例：
  原始：「网络、打印机的联系人是李 东，联系方式是18668097301。」
  问题：「网络」一词过于宽泛，容易被「网络中心」等查询误匹配
  重写：「办公设备（网络与打印机）相关问题的联系人是李东，电话18668097301。」

  原始：「董事局主席吴建荣」
  问题：单独一行缺乏上下文，不知道这是哪个公司
  重写：「浙江中南控股集团董事局主席为吴建荣。」

### split（拆分）
chunk 包含多个独立主题，彼此无直接关联。请拆分为多个语义自洽的子 chunk。

示例：
  原始（378字符包含8个电话号码）：
    安全部门
    大厦消控中心电话：89892851
    保安监控电话：86621912
    ...
    网络中心电话：89892870 内线882870

  拆分为：
    1. 安全部门 - 大厦消控中心电话：89892851，内线882851。
    2. 安全部门 - 保安监控电话：86621912，内线881912。
    3. 安全部门 - 网络中心电话：89892870，内线882870。

## 核心规则

1. **绝不增删事实数据**：人名、电话、地址、数字等原始信息必须完整保留
2. **增加消歧上下文**：模糊表述需要添加限定词（如部门名、章节名、主题域）
3. **拆分时每个子chunk必须语义完整**：包含主题词 + 具体数据
4. **表格行chunk保持自然语言格式**：如「事项为XXX，联系人是XXX」

## 输出格式

对每个 chunk 输出 JSON：
```json
{
  "chunk_index": 原始索引,
  "action": "keep" | "rewrite" | "split",
  "texts": ["精炼后的文本1", "精炼后的文本2", ...],
  "reason": "操作理由，一句话"
}
```

注意：
- keep 时 texts 只包含原始文本（1个元素）
- rewrite 时 texts 包含重写后的文本（1个元素）
- split 时 texts 包含多个子 chunk 文本

请输出纯 JSON 数组，不要用 markdown 代码块包裹。"""

REFINE_USER_TEMPLATE = """请审核以下 {count} 个分块，对需要优化的 chunk 执行 rewrite 或 split 操作。

文档名：{filename}

--- 分块列表开始 ---
{chunks_text}
--- 分块列表结束 ---

请逐条审核，输出 JSON 数组。"""


def _build_refine_batches(
    chunks: List[Any],
    batch_size: int = 15,
) -> List[List[Any]]:
    """Split chunks into batches for LLM processing."""
    batches = []
    for i in range(0, len(chunks), batch_size):
        batches.append(chunks[i:i + batch_size])
    return batches


def refine_chunks_stream(
    chunks: List[Any],
    filename: str = "",
    on_thinking: Callable[[str], None] = None,
) -> List[Any]:
    """
    LLM-driven chunk refinement: review, rewrite, and split chunks
    to improve retrieval quality.

    Args:
        chunks: List of ChunkResult objects from code-based chunking.
        filename: Original document filename for context.
        on_thinking: Callback for streaming LLM tokens.

    Returns:
        Refined list of ChunkResult objects.
    """
    if not chunks:
        return chunks

    if on_thinking is None:
        on_thinking = lambda _: None

    # Build batch input text
    def _format_chunk(chunk, idx: int) -> str:
        meta = chunk.metadata or {}
        ctype = meta.get("chunk_type", "text")
        return (
            f"[chunk {idx}] type={ctype}\n"
            f"text: {chunk.text}\n"
        )

    batches = _build_refine_batches(chunks)
    all_results = []

    for batch_idx, batch in enumerate(batches):
        chunks_text = "\n".join(
            _format_chunk(c, c.chunk_index) for c in batch
        )
        user_msg = REFINE_USER_TEMPLATE.format(
            count=len(batch),
            filename=filename,
            chunks_text=chunks_text,
        )

        on_thinking(f"\n\n📦 批次 {batch_idx + 1}/{len(batches)}（{len(batch)} 个 chunk）...\n")

        try:
            response = _call_llm_stream(
                system_prompt=REFINE_SYSTEM_PROMPT,
                user_message=user_msg,
                max_tokens=2000,
                on_thinking=on_thinking,
            )
            results = _parse_json_response(response, fallback=None)
        except Exception as e:
            logger.error(f"LLM chunk refinement failed for batch {batch_idx}: {e}")
            on_thinking(f"\n⚠ 精炼失败（{e}），保留原始 chunk\n")
            # Keep original chunks for this batch
            all_results.extend([
                {"chunk_index": c.chunk_index, "action": "keep", "texts": [c.text], "reason": "LLM 调用失败，保留原始"}
                for c in batch
            ])
            continue

        if not isinstance(results, list):
            logger.warning(f"LLM refinement returned non-list, keeping original chunks")
            all_results.extend([
                {"chunk_index": c.chunk_index, "action": "keep", "texts": [c.text], "reason": "LLM 返回格式异常"}
                for c in batch
            ])
            continue

        # Validate and apply results
        batch_map = {c.chunk_index: c for c in batch}
        for item in results:
            if not isinstance(item, dict):
                continue
            idx = item.get("chunk_index")
            action = item.get("action", "keep")
            texts = item.get("texts", [])
            reason = item.get("reason", "")

            if idx not in batch_map:
                continue

            original = batch_map[idx]
            if action == "keep" or not texts:
                all_results.append({
                    "chunk_index": idx,
                    "action": "keep",
                    "texts": [original.text],
                    "reason": reason or "无需优化",
                })
            elif action in ("rewrite", "split"):
                all_results.append({
                    "chunk_index": idx,
                    "action": action,
                    "texts": texts,
                    "reason": reason,
                })

        on_thinking(f"✅ 批次 {batch_idx + 1} 完成\n")

    # Build refined ChunkResult list
    from app.services.chunking import ChunkResult

    refined = []
    new_idx = 0
    for item in all_results:
        original_idx = item["chunk_index"]
        # Find original chunk for metadata inheritance
        original = next((c for c in chunks if c.chunk_index == original_idx), None)
        base_meta = dict(original.metadata) if original and original.metadata else {}

        for text in item["texts"]:
            if not text.strip():
                continue
            meta = dict(base_meta)
            meta["refine_action"] = item["action"]
            meta["refine_reason"] = item.get("reason", "")
            refined.append(ChunkResult(
                text=text.strip(),
                parent_text=original.parent_text if original else "",
                metadata=meta,
                chunk_index=new_idx,
            ))
            new_idx += 1

    logger.info(
        f"LLM refinement: {len(chunks)} chunks → {len(refined)} chunks "
        f"(kept={sum(1 for i in all_results if i['action']=='keep')}, "
        f"rewritten={sum(1 for i in all_results if i['action']=='rewrite')}, "
        f"split={sum(1 for i in all_results if i['action']=='split')})"
    )

    return refined
