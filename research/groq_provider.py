"""Groq free-tier compatible text provider; no model controls execution."""
from __future__ import annotations
import logging
import os

log=logging.getLogger(__name__)
DEFAULT="openai/gpt-oss-20b"
FALLBACK="openai/gpt-oss-120b"
DEPRECATED={"llama-3.3-70b-versatile","llama-3.1-8b-instant","qwen/qwen3.6-27b","groq/compound","groq/compound-mini"}


def candidates() -> list[str]:
    configured=os.getenv("GROQ_MODEL", DEFAULT).strip() or DEFAULT
    if configured in DEPRECATED:
        log.warning("Configured Groq model is retired for free-tier access; using supported default")
        configured=DEFAULT
    order=[configured, DEFAULT, FALLBACK]
    return list(dict.fromkeys(order))


async def complete(messages: list[dict], *, max_tokens:int=850) -> dict:
    """Try alternate public models only for model-related 4xx, not rate/auth errors."""
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY not configured")
    from groq import AsyncGroq, BadRequestError, NotFoundError, PermissionDeniedError
    last=None
    async with AsyncGroq(api_key=os.environ["GROQ_API_KEY"],timeout=25,max_retries=1) as client:
        for model in candidates():
            try:
                args = {"model":model,"temperature":0.1,"max_completion_tokens":max(1600,max_tokens),"messages":messages}
                if model.startswith("openai/gpt-oss-"):
                    args["reasoning_effort"] = "low"
                response=await client.chat.completions.create(**args)
                content=(response.choices[0].message.content or "").strip()
                if not content:
                    # GPT-OSS reasoning may consume tokens; fail explicitly.
                    raise RuntimeError("Groq returned an empty completion; check output/reasoning budget")
                return {"answer":content,"model":model}
            except (BadRequestError,NotFoundError,PermissionDeniedError) as exc:
                # PermissionDenied may also indicate org permissions: fallback helps.
                last=exc
                log.warning("Groq model %s unavailable (%s); trying alternate",model,type(exc).__name__)
                continue
    raise RuntimeError("None of the configured Groq models is accessible") from last
