#!/usr/bin/env python3
"""Lab 24 — Run RAGAS on phase-a testset; optional CI thresholds."""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from src.lab24_rag import rag_answer_and_contexts  # noqa: E402
from src.m4_eval import evaluate_ragas, failure_analysis  # noqa: E402


def _parse_contexts(cell) -> list[str]:
    if isinstance(cell, list):
        return cell
    if isinstance(cell, str):
        s = cell.strip()
        if s.startswith("["):
            try:
                v = json.loads(s)
                if isinstance(v, list):
                    return [str(x) for x in v]
            except json.JSONDecodeError:
                pass
            try:
                v = ast.literal_eval(s)
                if isinstance(v, list):
                    return [str(x) for x in v]
            except (SyntaxError, ValueError):
                pass
        return [s]
    return []


def _write_failure_md(
    per_question: list,
    out_path: str,
    bottom_n: int = 10,
) -> None:
    """Markdown failure cluster report from per-question scores."""
    rows = []
    for r in per_question:
        avg = (
            r.faithfulness
            + r.answer_relevancy
            + r.context_precision
            + r.context_recall
        ) / 4.0
        rows.append((avg, r))
    rows.sort(key=lambda x: x[0])
    bottom = rows[:bottom_n]

    lines = [
        "# Failure Cluster Analysis",
        "",
        "## Bottom 10 Questions",
        "",
        "| # | Question (truncated) | F | AR | CP | CR | Avg | Cluster |",
        "|---|----------------------|---|----|----|-----|---------|",
    ]
    clusters: dict[str, list[str]] = {"C1": [], "C2": []}
    for i, (avg, r) in enumerate(bottom, 1):
        qshort = (r.question[:60] + "…") if len(r.question) > 60 else r.question
        qshort = qshort.replace("|", "/")
        metric_scores = [
            ("faithfulness", r.faithfulness),
            ("answer_relevancy", r.answer_relevancy),
            ("context_precision", r.context_precision),
            ("context_recall", r.context_recall),
        ]
        worst_name = min(metric_scores, key=lambda x: x[1])[0]
        cl = "C1" if worst_name in ("context_recall", "faithfulness") else "C2"
        clusters[cl].append(r.question[:80])
        lines.append(
            f"| {i} | {qshort} | {r.faithfulness:.2f} | {r.answer_relevancy:.2f} | "
            f"{r.context_precision:.2f} | {r.context_recall:.2f} | {avg:.2f} | {cl} |"
        )
    lines.extend(
        [
            "",
            "## Clusters Identified",
            "",
            "### Cluster C1: Retrieval / grounding failures",
            "",
            "**Pattern:** Low context_recall or faithfulness — thiếu chunk hoặc câu trả lời lệch context.",
            "",
            "**Examples:**",
        ]
    )
    for ex in clusters["C1"][:3]:
        lines.append(f"- {ex}")
    lines.extend(
        [
            "",
            "**Root cause:** `top_k` hoặc hybrid retrieval chưa đủ; chunk nhỏ hoặc noise.",
            "",
            "**Proposed fix:**",
            "",
            "- Tăng `rerank_top_k` từ 3 → 5 trong `run_query` / `rag_answer_and_contexts`.",
            "- Bật hoặc tinh chỉnh hybrid BM25+dense weights trong `HybridSearch`.",
            "",
            "### Cluster C2: Precision / relevancy issues",
            "",
            "**Pattern:** `context_precision` hoặc `answer_relevancy` thấp — nhiễu context hoặc câu trả lời lệch intent.",
            "",
            "**Examples:**",
        ]
    )
    for ex in clusters["C2"][:3]:
        lines.append(f"- {ex}")
    lines.extend(
        [
            "",
            "**Root cause:** Reranker hoặc prompt chưa ép trả lời đúng trích dẫn.",
            "",
            "**Proposed fix:**",
            "",
            "- Thêm re-ranker mạnh hơn hoặc tăng ngưỡng lọc score trước khi đưa vào LLM.",
            "- Ràng buộc output: yêu cầu trích ý chính từ context, từ chối khi không đủ bằng chứng.",
            "",
        ]
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _parse_thresholds(spec: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for s in spec:
        if "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = float(v.strip())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--testset",
        default=os.path.join(ROOT, "phase-a", "testset_v1.csv"),
    )
    ap.add_argument(
        "--out-dir",
        default=os.path.join(ROOT, "phase-a"),
    )
    ap.add_argument(
        "--threshold",
        action="append",
        default=[],
        help="metric=value e.g. faithfulness=0.5",
    )
    ap.add_argument("--max-rows", type=int, default=0, help="0 = all rows")
    args = ap.parse_args()

    df = pd.read_csv(args.testset)
    n = args.max_rows or len(df)
    df = df.head(n)

    questions, answers, all_contexts, ground_truths = [], [], [], []
    for _, row in df.iterrows():
        q = str(row["question"])
        gt = str(row.get("ground_truth", ""))
        ctx_template = _parse_contexts(row.get("contexts", ""))
        ans, ctx = rag_answer_and_contexts(q, rerank_top_k=3, use_llm=True)
        if not ctx:
            ctx = ctx_template
        questions.append(q)
        answers.append(ans)
        all_contexts.append(ctx)
        ground_truths.append(gt)

    results = evaluate_ragas(questions, answers, all_contexts, ground_truths)
    per = results.get("per_question", [])
    ragas_df = pd.DataFrame(
        [
            {
                "question": r.question,
                "answer": r.answer,
                "ground_truth": r.ground_truth,
                "faithfulness": r.faithfulness,
                "answer_relevancy": r.answer_relevancy,
                "context_precision": r.context_precision,
                "context_recall": r.context_recall,
            }
            for r in per
        ]
    )
    os.makedirs(args.out_dir, exist_ok=True)
    csv_path = os.path.join(args.out_dir, "ragas_results.csv")
    ragas_df.to_csv(csv_path, index=False)

    summary = {
        "faithfulness": float(results["faithfulness"]),
        "answer_relevancy": float(results["answer_relevancy"]),
        "context_precision": float(results["context_precision"]),
        "context_recall": float(results["context_recall"]),
    }
    with open(os.path.join(args.out_dir, "ragas_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    fails = failure_analysis(per, bottom_n=10)
    _write_failure_md(per, os.path.join(args.out_dir, "failure_analysis.md"))

    print(json.dumps(summary, indent=2))
    print(f"Wrote {csv_path} and ragas_summary.json, failure_analysis.md ({len(fails)} failures)")

    thr = _parse_thresholds(args.threshold)
    for k, v in thr.items():
        if k not in summary:
            continue
        if summary[k] < v:
            print(f"THRESHOLD_FAIL {k} {summary[k]} < {v}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
