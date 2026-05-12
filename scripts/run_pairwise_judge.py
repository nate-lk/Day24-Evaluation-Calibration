#!/usr/bin/env python3
"""Lab 24 Phase B — Pairwise LLM judge with swap-and-average."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402
from langchain_core.prompts import PromptTemplate  # noqa: E402

from config import OPENAI_API_KEY  # noqa: E402
from src.lab24_rag import rag_answer_and_contexts  # noqa: E402

JUDGE_PROMPT = PromptTemplate.from_template(
    """You are an impartial evaluator. Compare two answers to the same question.

Question: {question}
Answer A: {answer_a}
Answer B: {answer_b}

Rate based on factual accuracy, relevance to question, and conciseness.

Output JSON only:
{{"winner": "A" or "B" or "tie", "reason": "short explanation"}}"""
)


def parse_judge_output(text: str) -> dict:
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"winner": "tie", "reason": "Parse error"}


def _heuristic_winner(question: str, a: str, b: str) -> str:
    """Deterministic fallback when no LLM key."""
    def score(x: str) -> float:
        toks = set(question.lower().split())
        return sum(1 for t in toks if len(t) > 2 and t in x.lower()) / max(len(toks), 1)

    sa, sb = score(a), score(b)
    if abs(sa - sb) < 0.05:
        return "tie"
    return "A" if sa > sb else "B"


def pairwise_judge_with_swap(
    question: str,
    ans1: str,
    ans2: str,
    judge_llm,
) -> tuple[str, str, str]:
    """Returns (final_winner, run1_winner, run2_winner_after_flip)."""
    if judge_llm is None:
        r1 = _heuristic_winner(question, ans1, ans2)
        r2_raw = _heuristic_winner(question, ans2, ans1)
        flip = {"A": "B", "B": "A", "tie": "tie"}
        r2_flipped = flip.get(r2_raw, "tie")
        if r1 == r2_flipped:
            return r1, r1, r2_flipped
        return "tie", r1, r2_flipped

    results = []
    p1 = JUDGE_PROMPT.format(question=question, answer_a=ans1, answer_b=ans2)
    out1 = judge_llm.invoke(p1)
    r1 = parse_judge_output(getattr(out1, "content", str(out1)))
    results.append(r1.get("winner", "tie"))

    p2 = JUDGE_PROMPT.format(question=question, answer_a=ans2, answer_b=ans1)
    out2 = judge_llm.invoke(p2)
    r2 = parse_judge_output(getattr(out2, "content", str(out2)))
    w2 = r2.get("winner", "tie")
    if w2 == "A":
        w2 = "B"
    elif w2 == "B":
        w2 = "A"
    results.append(w2)

    run1, run2 = results[0], results[1]
    if run1 == run2:
        return run1, run1, w2
    return "tie", run1, w2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--testset", default=os.path.join(ROOT, "phase-a", "testset_v1.csv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "phase-b", "pairwise_results.csv"))
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    judge_llm = None
    if OPENAI_API_KEY:
        try:
            from langchain_openai import ChatOpenAI

            judge_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        except Exception:
            judge_llm = None

    df = pd.read_csv(args.testset).head(args.limit)
    rows = []
    for _, r in df.iterrows():
        q = str(r["question"])
        a1, _ = rag_answer_and_contexts(q, rerank_top_k=3, use_llm=True)
        a2, _ = rag_answer_and_contexts(q, rerank_top_k=5, use_llm=True)
        final, run1, run2 = pairwise_judge_with_swap(q, a1, a2, judge_llm)
        rows.append(
            {
                "question": q,
                "answer_a": a1,
                "answer_b": a2,
                "winner_after_swap": final,
                "run1_winner": run1,
                "run2_winner": run2,
            }
        )

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    pd.DataFrame(rows).to_csv(args.out, index=False)
    print(f"Wrote {args.out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
