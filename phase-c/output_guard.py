"""Lab 24 Phase C.4 — Output safety check (Llama Guard 3 via Groq or stub)."""

from __future__ import annotations

import os
import time
from typing import Any

import requests


class OutputGuard:
    """Groq OpenAI-compatible API with llama-guard-3-8b; falls back to stub."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = os.getenv("LAB24_GUARD_MODEL", "llama-guard-3-8b")

    def check(self, user_input: str, agent_response: str) -> tuple[bool, str, float]:
        start = time.perf_counter()
        if not self.api_key:
            text = "safe (stub: set GROQ_API_KEY for Llama Guard)"
            return True, text, (time.perf_counter() - start) * 1000

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": agent_response},
            ],
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = requests.post(self.url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            result = f"unsafe (api error: {e})"
        ms = (time.perf_counter() - start) * 1000
        low = result.lower()
        is_safe = "safe" in low and "unsafe" not in low
        return is_safe, result, ms
