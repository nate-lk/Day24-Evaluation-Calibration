"""Lab 24 Phase C.1–C.2 — Input guards: PII scrub + topic scope."""

from __future__ import annotations

import re
import time
from typing import Callable

VN_PII = {
    "CCCD": r"\b\d{12}\b",
    "PHONE_VN": r"(?:\+84|0)\d{9,10}\b",
    "TAX_CODE": r"\b\d{10}(?:-\d{3})?\b",
    "EMAIL": r"\b[\w.-]+@[\w.-]+\.\w+\b",
}


JAILBREAK_PATTERNS = [
    r"\bjailbreak\b",
    r"\bDAN\b",
    r"ignore (all |previous )?rules",
    r"without restrictions",
    r"evil AI",
    r"no guidelines",
    r"how to hack",
    r"override",
    r"SYSTEM UPDATE",
    r"ignore corpus",
    r"exec\(",
    r"environment variables",
]


class InputGuard:
    """Presidio NER (optional) + Vietnamese regex layer."""

    def __init__(self) -> None:
        self.analyzer = None
        self.anonymizer = None
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine

            self.analyzer = AnalyzerEngine()
            self.anonymizer = AnonymizerEngine()
        except Exception:
            pass

    def scrub_vn(self, t: str) -> str:
        for name, pattern in VN_PII.items():
            t = re.sub(pattern, f"[{name}]", t, flags=re.IGNORECASE)
        return t

    def scrub_ner(self, t: str) -> str:
        if not self.analyzer or not self.anonymizer:
            return t
        try:
            results = self.analyzer.analyze(text=t, language="en")
            return self.anonymizer.anonymize(
                text=t, analyzer_results=results
            ).text
        except Exception:
            return t

    def detect_injection(self, t: str) -> tuple[bool, str]:
        low = t.lower()
        for pat in JAILBREAK_PATTERNS:
            if re.search(pat, low, re.IGNORECASE):
                return True, f"blocked pattern: {pat}"
        return False, ""

    def sanitize(self, t: str) -> tuple[str, float]:
        start = time.perf_counter()
        out = self.scrub_ner(self.scrub_vn(t))
        ms = (time.perf_counter() - start) * 1000
        return out, ms


class TopicGuard:
    """Embedding similarity to allowed topics, or keyword fallback."""

    def __init__(self, allowed_topics: list[str], threshold: float = 0.55) -> None:
        self.allowed_topics = allowed_topics
        self.threshold = threshold
        self._embed: Callable[[str], list[float]] | None = None
        self._topic_vecs: list[list[float]] = []
        self._init_embeddings()

    def _init_embeddings(self) -> None:
        from config import OPENAI_API_KEY

        if not OPENAI_API_KEY:
            return
        try:
            from langchain_openai import OpenAIEmbeddings

            emb = OpenAIEmbeddings()
            self._embed = lambda q: emb.embed_query(q)
            self._topic_vecs = [emb.embed_query(t) for t in self.allowed_topics]
        except Exception:
            self._embed = None

    def check(self, text: str) -> tuple[bool, str]:
        text_l = text.lower()
        if self._embed and self._topic_vecs:
            import numpy as np

            qv = np.array(self._embed(text), dtype=float)
            best_sim, best = -1.0, ""
            for topic, tv in zip(self.allowed_topics, self._topic_vecs):
                tv = np.array(tv, dtype=float)
                sim = float(np.dot(qv, tv) / (np.linalg.norm(qv) * np.linalg.norm(tv) + 1e-9))
                if sim > best_sim:
                    best_sim, best = sim, topic
            if best_sim >= self.threshold:
                return True, f"On topic: {best} ({best_sim:.2f})"
            return False, f"Off topic. Closest: {best} ({best_sim:.2f})"

        hits = [t for t in self.allowed_topics if t.lower() in text_l]
        if hits:
            return True, f"On topic (keyword): {hits[0]}"
        # generic domain keywords for this lab corpus
        domain_kw = ("nghị định", "dữ liệu", "cá nhân", "bctc", "báo cáo tài chính", "vốn", "nợ")
        if any(k in text_l for k in domain_kw):
            return True, "On topic (domain keyword heuristic)"
        return (
            False,
            "Off topic: câu hỏi không liên quan dữ liệu cá nhân / BCTC trong phạm vi lab.",
        )
