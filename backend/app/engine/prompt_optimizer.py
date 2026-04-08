from typing import Any, Dict, List, Optional

# Analysis instruction appended to system prompt for structured intent/emotion extraction
ANALYSIS_INSTRUCTION = """

在回答用户问题后，请在回复末尾输出以下格式的分析结果：

<analysis>
{
  "emotion": "positive|negative|confused|urgent|neutral",
  "intent": "用一句话描述用户的真实意图",
  "complexity": "low|medium|high",
  "key_facts": ["从对话中提取的关键信息"],
  "needs_tool": true或false,
  "suggested_tools": ["建议使用的工具名称"]
}
</analysis>

注意：分析内容不会展示给用户，仅用于优化后续对话质量。
"""


def _build_fewshot_section(fewshot_examples: List[Dict[str, str]]) -> str:
    """将 few-shot 示例格式化为 prompt 片段。"""
    if not fewshot_examples:
        return ""

    parts: List[str] = ["\n\n## 优质回答示例（供参考）"]
    for i, ex in enumerate(fewshot_examples, 1):
        user_msg = ex.get("user_message", "")
        ai_resp = ex.get("ai_response", "")
        # 截断过长的示例
        if len(ai_resp) > 500:
            ai_resp = ai_resp[:500] + "..."
        parts.append(f"\n### 示例 {i}\n用户: {user_msg}\n助手: {ai_resp}")

    return "\n".join(parts)


def build_optimized_prompt(
    system_prompt: Optional[str],
    messages: List[Dict[str, Any]],
    intent: Optional[str] = None,
    context_window: int = 10,
    fewshot_examples: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, Any]]:
    """
    5-layer prompt fusion:
    1. Base System Layer - default BridgeAI system behavior
    2. Agent Layer - agent-specific system prompt
    3. Few-shot Layer - high-rated conversation examples from feedback loop
    4. Context Layer - intent-aware context hints
    5. Analysis Layer - structured analysis instruction

    Args:
        system_prompt: Agent-specific system prompt (layer 2)
        messages: User conversation messages
        intent: Detected intent from previous classification
        context_window: Number of recent messages to include
        fewshot_examples: High-rated few-shot examples [{user_message, ai_response}]

    Returns:
        Optimized message list ready for LLM invocation
    """
    optimized: List[Dict[str, Any]] = []

    # --- Layer 1: Base System ---
    base_system = (
        "You are BridgeAI, an intelligent assistant platform. "
        "You are helpful, accurate, and concise. "
        "Always respond in the same language as the user's message."
    )

    # --- Layer 2: Agent System Prompt ---
    combined_system = base_system
    if system_prompt:
        combined_system = f"{base_system}\n\n{system_prompt}"

    # --- Layer 3: Few-shot Examples ---
    fewshot_section = _build_fewshot_section(fewshot_examples or [])
    if fewshot_section:
        combined_system = f"{combined_system}{fewshot_section}"

    # --- Layer 4: Context (intent hint) ---
    if intent:
        intent_hints = {
            "question": "The user is asking a question. Provide a clear and informative answer.",
            "generation": "The user wants you to create or generate content. Be creative and thorough.",
            "debugging": "The user needs help debugging. Be systematic and provide actionable solutions.",
            "summarization": "The user wants a summary. Be concise and capture key points.",
            "general": "Respond naturally and helpfully.",
        }
        hint = intent_hints.get(intent, "")
        if hint:
            combined_system = f"{combined_system}\n\n{hint}"

    # --- Layer 5: Analysis Instruction ---
    combined_system = f"{combined_system}\n{ANALYSIS_INSTRUCTION}"

    optimized.append({"role": "system", "content": combined_system})

    # Add conversation messages (limited to context window)
    recent_messages = messages[-context_window:] if len(messages) > context_window else messages
    for msg in recent_messages:
        optimized.append({"role": msg["role"], "content": msg["content"]})

    return optimized
