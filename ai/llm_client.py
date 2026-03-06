"""
Mortgage Agent MVP - LLM Client

Calls Foundation Model API endpoints via Databricks SDK.
Set MODEL_ENDPOINT to whichever endpoint is available in your workspace Serving tab.

To check available models:
  1. Open your Databricks workspace
  2. Click "Serving" in the left sidebar
  3. Foundation Model API endpoints are listed at the top
  4. Copy the exact endpoint name (e.g. "databricks-gpt-oss-20b")
"""

import os
import logging
from databricks.sdk.core import Config
import requests

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("llm_client")


# Set this to the endpoint name visible in your Serving tab.
# Leave empty to use knowledge-base-only fallback.
MODEL_ENDPOINT = os.getenv("MODEL_ENDPOINT", "")

if MODEL_ENDPOINT:
    logger.info(f"Using Foundation Model API endpoint: {MODEL_ENDPOINT}")
else:
    MODEL_ENDPOINT = "databricks-gpt-oss-20b"
    logger.info("No Foundation Model API endpoint configured.")


def call_foundation_model(
    messages: list[dict],
    system_prompt: str,
    max_tokens: int,
    temperature: float,
) -> dict:
    """
    Call Foundation Model API using direct REST + Config() auth.
    Returns plain dicts -- no SDK dataclass serialization issues.
    """
    cfg = Config()
    auth_headers = cfg.authenticate()
    
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    
    url = f"{cfg.host}/serving-endpoints/{MODEL_ENDPOINT}/invocations"
    
    resp = requests.post(
        url,
        headers={
            **auth_headers,
            "Content-Type": "application/json",
        },
        json={
            "messages": full_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=60,
        )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Model serving returned {resp.status_code}: {resp.text[:500]}"
        )
        
    data = resp.json()
    
    content = ""
    tokens = 0
    
    choices = data.get("choices", [])
    if choices:
        msg = choices[0].get("message", {})
        raw_content = msg.get("content", "")
        
        # Some models (e.g. databricks-gpt-oss-20b) return content as a list
        # of blocks with types like "reasoning" and "text" instead of a plain string.
        if isinstance(raw_content, str):
            content = raw_content
        elif isinstance(raw_content, list):
            # Extract only the actual text blocks, skip reasoning/thinking blocks
            text_parts = []
            for block in raw_content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    text_parts.append(block)
            content = "\n".join(text_parts)
        else:
            content = str(raw_content)
    
    usage = data.get("usage", {})
    tokens = usage.get("total_tokens", 0)

    return {"content": content, "tokens_used": tokens}

def _knowledge_fallback(messages: list[dict]) -> str:
    """Fallback when no LLM is configured."""
    last_msg = messages[-1]["content"] if messages else ""
    return (
        f'I received your question about: "{last_msg[:100]}". '
        "I am running in knowledge-base-only mode (no LLM endpoint configured). "
        "Set the MODEL_ENDPOINT environment variable to a Foundation Model API "
        "endpoint name from your Serving tab to enable full AI responses. "
        "Check the relevant topics returned with this response for information."
    )

def get_llm_response(
    messages: list[dict],
    system_prompt: str,
    max_tokens: int = 1500,
    temperature: float = 0.7,
) -> dict:
    """
    Get LLM response. Strategy:
      1. Databricks Foundation Model API (if MODEL_ENDPOINT is set)
      2. Knowledge-base-only fallback
    """
    if MODEL_ENDPOINT:
        try:
            return call_foundation_model(messages, system_prompt, max_tokens, temperature)
        except Exception as e:
            logger.info(f"Foundation Model API error: {e}")

    return {
        "content": _knowledge_fallback(messages),
        "tokens_used": 0,
    }