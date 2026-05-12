#!/usr/bin/env python3
"""Lab 24 Phase B.2 — Absolute rubric scoring (4 dimensions + overall)."""

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

ABSOLUTE_PROMPT = PromptTemplate.from_template(
    """Score the answer on 4 dimensions, each 1-5 scale:
1. Factual accuracy (1=many errors, 5=fully accurate)
2. Relevance (1=off-topic, 5=directly answers)
3. Conciseness (1=verbose, 5=appropriately brief)
4. Helpfulness (1=unclear, 5=actionable)

Question: {question}
Answer: {answer}

Output JSON only:
{{"accuracy": int, "relevance": int, "conciseness": int, "helpfulness": int, "overall": float}}"""
)


def parse_json(text: str) -> dict:
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"accuracy": 3, "relevance": 3, "conciseness": 3, "helpfulness": 3, "overall": 3.0}


def absolute_score(question: str, answer: str, judge_llm) -> dict:
    if judge_llm is None:
        n = min(5, max(1, len(answer) // 200 + 1))
        return {
            "accuracy": n,
            "relevance": n,
            "conciseness": 5 - (n // 2),
            "helpfulness": n,
            "overall": float(n),
        }
    prompt = ABSOLUTE_PROMPT.format(question=question, answer=answer)
    out = judge_llm.invoke(prompt)
    text = getattr(out, "content", str(out))
    parsed = parse_json(text)
    if "overall" not in parsed or parsed["overall"] is None:
        dims = ["accuracy", "relevance", "conciseness", "helpfulness"]
        parsed["overall"] = sum(int(parsed.get(d, 3)) for d in dims) / 4.0
    return parsed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--testset", default=os.path.join(ROOT, "phase-a", "testset_v1.csv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "phase-b", "absolute_scores.csv"))
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
        ans, _ = rag_answer_and_contexts(q, rerank_top_k=3, use_llm=True)
        s = absolute_score(q, ans, judge_llm)
        rows.append(
            {
                "question": q,
                "answer": ans,
                "accuracy": s.get("accuracy"),
                "relevance": s.get("relevance"),
                "conciseness": s.get("conciseness"),
                "helpfulness": s.get("helpfulness"),
                "overall": s.get("overall"),
            }
        )
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    pd.DataFrame(rows).to_csv(args.out, index=False)
    print(f"Wrote {args.out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
