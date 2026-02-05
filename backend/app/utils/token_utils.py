import tiktoken
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Accurately count tokens using tiktoken."""
    if not text:
        return 0
    try:
        encoding = tiktoken.encoding_for_model(model)
    except (KeyError, ValueError):
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def count_messages_tokens(messages: List[Dict[str, Any]], model: str = "gpt-4o") -> int:
    """Count total tokens in a list of messages (OpenAI format)."""
    # Simplified overhead estimation
    total = 0
    for m in messages:
        total += 4  # Overhead per message
        total += count_tokens(m.get("content", ""), model)
        total += count_tokens(m.get("role", ""), model)
    total += 3  # Assistant overhead
    return total

def trim_messages(
    messages: List[Dict[str, Any]],
    max_input_tokens: int,
    strategy: str = "trim_context_first",
    model: str = "gpt-4o"
) -> List[Dict[str, Any]]:
    """
    Trim messages to fit within max_input_tokens based on strategy.
    
    Strategies:
    - none: No trimming
    - trim_context_first: Trims 'context' if present in content, then others.
    - trim_user_first: Trims user message content first.
    - summarize_context: Placeholder for now, acts like trim_context_first.
    """
    if strategy == "none" or not max_input_tokens or max_input_tokens <= 0:
        return messages

    current_total = count_messages_tokens(messages, model)
    if current_total <= max_input_tokens:
        return messages

    logger.info(f"[TOKEN_UTILS] Trimming messages: current={current_total}, max={max_input_tokens}, strategy={strategy}")
    
    # Clone to avoid mutating original
    trimmed = [dict(m) for m in messages]
    
    # target_reduction = current_total - max_input_tokens
    
    if strategy in {"trim_context_first", "summarize_context"}:
        # Look for user message containing "Context:" or similar
        for i, m in enumerate(trimmed):
            if m.get("role") == "user" and "Context:" in m.get("content", ""):
                content = m["content"]
                # Try to locate the context block. Usually: "... \nContext: <JSON> \n ..."
                # Simple approach: if it's very long, truncate the middle or end.
                parts = content.split("Context:", 1)
                before = parts[0]
                after = parts[1] if len(parts) > 1 else ""
                
                # Truncate 'after' (the context part)
                allowed_after_chars = int(len(after) * (max_input_tokens / current_total) * 0.8)
                if allowed_after_chars < 100:
                    allowed_after_chars = 100
                
                if len(after) > allowed_after_chars:
                    new_after = after[:allowed_after_chars] + "... [TRUNCATED]"
                    trimmed[i]["content"] = f"{before}Context: {new_after}"
                    break
    
    elif strategy == "trim_user_first":
        for i, m in enumerate(trimmed):
            if m.get("role") == "user":
                content = m["content"]
                allowed_chars = int(len(content) * (max_input_tokens / current_total) * 0.9)
                if len(content) > allowed_chars:
                    trimmed[i]["content"] = content[:allowed_chars] + "... [TRUNCATED]"
                    break

    # Final sweep: if still too long (rare if above logic worked), hard truncate messages from middle
    while count_messages_tokens(trimmed, model) > max_input_tokens:
        # Heaviest message is usually user
        user_msgs = [i for i, m in enumerate(trimmed) if m["role"] == "user" and len(m["content"]) > 100]
        if not user_msgs:
            # Drop earliest messages (except system)
            found = False
            for i in range(1, len(trimmed)):
                 if trimmed[i]["role"] != "system":
                     trimmed.pop(i)
                     found = True
                     break
            if not found: break # Can't trim further
        else:
            idx = user_msgs[-1]
            trimmed[idx]["content"] = trimmed[idx]["content"][:-100]

    return trimmed
