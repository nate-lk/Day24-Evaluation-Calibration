"""Lab 24 Phase C.5 — Guarded RAG pipeline + latency timings (sync)."""

from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from input_guard import InputGuard, TopicGuard  # noqa: E402
from output_guard import OutputGuard  # noqa: E402

from src.lab24_rag import rag_answer_and_contexts  # noqa: E402


def refuse_response(reason: str) -> str:
    return (
        "Xin lỗi, hệ thống không thể xử lý yêu cầu này. "
        f"Lý do: {reason}. Vui lòng thử lại với nội dung phù hợp phạm vi trợ lý."
    )


def guarded_pipeline(user_input: str) -> tuple[str, dict[str, float]]:
    timings: dict[str, float] = {}
    input_guard = InputGuard()
    topic_guard = TopicGuard(
        allowed_topics=[
            "Nghị định 13/2023 và bảo vệ dữ liệu cá nhân",
            "Báo cáo tài chính và chỉ tiêu kế toán",
        ]
    )
    output_guard = OutputGuard()

    t0 = time.perf_counter()
    sanitized, _ = input_guard.sanitize(user_input)
    inj, inj_reason = input_guard.detect_injection(sanitized)
    if inj:
        timings["L1"] = (time.perf_counter() - t0) * 1000
        return refuse_response(inj_reason), timings
    topic_ok, topic_reason = topic_guard.check(sanitized)
    timings["L1"] = (time.perf_counter() - t0) * 1000
    if not topic_ok:
        return refuse_response(topic_reason), timings

    t0 = time.perf_counter()
    answer, _ctx = rag_answer_and_contexts(sanitized, rerank_top_k=3, use_llm=True)
    timings["L2"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    safe, guard_msg, _ms = output_guard.check(sanitized, answer)
    timings["L3"] = (time.perf_counter() - t0) * 1000
    if not safe:
        return refuse_response(f"output guard: {guard_msg[:120]}"), timings

    return answer, timings


def benchmark(n: int = 100) -> dict[str, list[float]]:
    import json

    test_path = os.path.join(ROOT, "test_set.json")
    with open(test_path, encoding="utf-8") as f:
        items = json.load(f)
    queries = [x["question"] for x in items] * max(1, (n + len(items) - 1) // len(items))
    queries = queries[:n]

    layers: dict[str, list[float]] = {"L1": [], "L2": [], "L3": []}
    for q in queries:
        _ans, t = guarded_pipeline(q)
        for k in layers:
            if k in t:
                layers[k].append(t[k])
    return layers


if __name__ == "__main__":
    import numpy as np

    layers = benchmark(min(20, 100))
    print("(quick demo n=20) percentiles ms:")
    for layer, vals in layers.items():
        if not vals:
            continue
        a = np.array(vals, dtype=float)
        print(
            f"  {layer}: P50={np.percentile(a, 50):.0f} "
            f"P95={np.percentile(a, 95):.0f} P99={np.percentile(a, 99):.0f}"
        )
