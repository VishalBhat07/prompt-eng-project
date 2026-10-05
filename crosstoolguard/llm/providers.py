"""LLM provider adapters — one chat interface, Groq/OpenAI/Anthropic behind it.

Single-user v1: keys come from server env (GROQ_API_KEY, OPENAI_API_KEY,
ANTHROPIC_API_KEY). Per-user vault arrives with auth; the adapter seam
stays the same.
"""

from __future__ import annotations

import os

PROVIDERS = {
    "groq": {"name": "Groq", "env": "GROQ_API_KEY",
             "models": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]},
    "openai": {"name": "OpenAI", "env": "OPENAI_API_KEY",
               "models": ["gpt-4o-mini", "gpt-4o"]},
    "anthropic": {"name": "Anthropic", "env": "ANTHROPIC_API_KEY",
                  "models": ["claude-sonnet-4-5", "claude-haiku-4-5"]},
}

DEFAULTS = {"groq": "openai/gpt-oss-120b", "openai": "gpt-4o-mini", "anthropic": "claude-sonnet-4-5"}


def is_configured(provider: str) -> bool:
    return bool(os.getenv(PROVIDERS[provider]["env"]))


def list_providers() -> list[dict]:
    return [{"id": pid, "name": meta["name"], "configured": is_configured(pid),
             "models": meta["models"]} for pid, meta in PROVIDERS.items()]


def resolve(provider: str | None, model: str | None) -> tuple[str, str]:
    """Provider + model with validation; model defaults per provider."""
    pid = provider or "groq"
    if pid not in PROVIDERS:
        raise ValueError(f"unknown provider: {pid}")
    chosen = model or DEFAULTS[pid]
    if chosen not in PROVIDERS[pid]["models"]:
        raise ValueError(f"unknown model {model!r} for provider {pid}")
    return pid, chosen


def complete(provider: str, model: str, messages: list[dict], max_tokens: int = 1024) -> str:
    """Blocking chat completion → assistant text. Raises on missing key."""
    api_key = os.getenv(PROVIDERS[provider]["env"])
    if not api_key:
        raise RuntimeError(f"{PROVIDERS[provider]['env']} unset")
    if provider == "groq":
        from groq import Groq

        return Groq(api_key=api_key).chat.completions.create(
            model=model, messages=messages, temperature=0,
            max_tokens=max_tokens).choices[0].message.content or ""
    if provider == "openai":
        from openai import OpenAI

        return OpenAI(api_key=api_key).chat.completions.create(
            model=model, messages=messages, temperature=0,
            max_tokens=max_tokens).choices[0].message.content or ""
    if provider == "anthropic":
        import anthropic

        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        convo = [m for m in messages if m["role"] != "system"]
        return anthropic.Anthropic(api_key=api_key).messages.create(
            model=model, system=system, messages=convo, temperature=0,
            max_tokens=max_tokens).content[0].text or ""
    raise ValueError(f"unknown provider: {provider}")
