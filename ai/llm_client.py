import os
import json
from typing import Optional


# ── Strategy 1: Databricks Foundation Model API (preferred on Databricks) ──

def call_foundation_model(
    messages: list[dict],
    system_prompt: str,
    model: str = "databricks-claude-sonnet-4-5",
    max_tokens: int = 1500,
    temperature: float = 0.7,
) -> dict:
    """Call Claude via Databricks Foundation Model API endpoint."""
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    response = w.serving_endpoints.query(
        name=model,
        messages=full_messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    content = response.choices[0].message.content if response.choices else ""
    tokens = 0
    if hasattr(response, "usage") and response.usage:
        tokens = getattr(response.usage, "total_tokens", 0)

    return {"content": content, "tokens_used": tokens}


# ── Strategy 2: Direct Anthropic SDK (fallback / local dev) ──

def call_anthropic_direct(
    messages: list[dict],
    system_prompt: str,
    max_tokens: int = 1500,
    temperature: float = 0.7,
) -> dict:
    """Call Claude via direct Anthropic API."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "content": _knowledge_fallback(messages),
            "tokens_used": 0,
        }

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=messages,
    )

    content = response.content[0].text if response.content else ""
    tokens = response.usage.input_tokens + response.usage.output_tokens

    return {"content": content, "tokens_used": tokens}


# ── Strategy 3: Knowledge-base-only fallback ──

def _knowledge_fallback(messages: list[dict]) -> str:
    """Return a knowledge-base answer when no LLM is available."""
    last_msg = messages[-1]["content"] if messages else ""
    return (
        f"I received your question about: \\'{last_msg[:100]}\\'. "
        "I am currently running in knowledge-base-only mode (no LLM API configured). "
        "To get full conversational responses, configure either ANTHROPIC_API_KEY "
        "or a Databricks Foundation Model API endpoint. "
        "In the meantime, check the relevant topics returned in this response."
    )


# ── Unified interface ──

def get_llm_response(
    messages: list[dict],
    system_prompt: str,
    max_tokens: int = 1500,
    temperature: float = 0.7,
) -> dict:
    """
    Get LLM response using best available strategy:
    1. Databricks Foundation Model API (if on Databricks with serving endpoint)
    2. Direct Anthropic SDK (if ANTHROPIC_API_KEY set)
    3. Knowledge-base-only fallback
    """
    serving_endpoint = os.getenv("SERVING_ENDPOINT_NAME")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if serving_endpoint:
        try:
            return call_foundation_model(
                messages, system_prompt,
                model=serving_endpoint,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            print(f"Foundation Model API failed: {e}, falling back to Anthropic SDK")

    if anthropic_key:
        try:
            return call_anthropic_direct(
                messages, system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            print(f"Anthropic SDK failed: {e}, falling back to knowledge-base only")

    return {
        "content": _knowledge_fallback(messages),
        "tokens_used": 0,
    }