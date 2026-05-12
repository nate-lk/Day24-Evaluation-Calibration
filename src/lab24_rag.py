"""Lab 24: shared RAG entry for eval / judge / guarded pipeline."""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

from config import OPENAI_API_KEY

if TYPE_CHECKING:
    from src.m2_search import HybridSearch
    from src.m3_rerank import CrossEncoderReranker

_pipeline_lock = threading.Lock()
_search: HybridSearch | None = None
_reranker: CrossEncoderReranker | None = None


def get_pipeline():
    """Lazy-init production search + reranker (thread-safe)."""
    global _search, _reranker
    with _pipeline_lock:
        if _search is None or _reranker is None:
            from src.pipeline import build_pipeline

            _search, _reranker = build_pipeline()
    return _search, _reranker


def _answer_with_llm(question: str, contexts: list[str]) -> str | None:
    if not OPENAI_API_KEY or not contexts:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)
        context_str = "\n\n".join(contexts[:6])
        resp = client.chat.completions.create(
            model=os.getenv("LAB24_CHAT_MODEL", "gpt-4o-mini"),
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Bạn là trợ lý RAG. Trả lời CHỈ dựa trên context. "
                        "Nếu context không đủ, nói 'Không tìm thấy trong tài liệu.'"
                    ),
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context_str}\n\nCâu hỏi: {question}",
                },
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return None


def rag_answer_and_contexts(
    question: str,
    *,
    rerank_top_k: int | None = None,
    use_llm: bool = True,
) -> tuple[str, list[str]]:
    """Run retrieval (+ optional LLM). Falls back to top chunk if no LLM."""
    from src.pipeline import run_query

    search, reranker = get_pipeline()
    answer, contexts = run_query(
        question, search, reranker, rerank_top_k=rerank_top_k
    )
    if use_llm:
        llm_ans = _answer_with_llm(question, contexts)
        if llm_ans:
            answer = llm_ans
    return answer, contexts
