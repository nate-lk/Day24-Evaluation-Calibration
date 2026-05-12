#!/usr/bin/env python3
"""Lab 24 Phase B.4 — Quantify position and length bias; write judge_bias_report.md."""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairwise", default=os.path.join(ROOT, "phase-b", "pairwise_results.csv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "phase-b", "judge_bias_report.md"))
    args = ap.parse_args()

    df = pd.read_csv(args.pairwise)
    run1_a_wins = (df["run1_winner"] == "A").sum()
    total = len(df)
    pos_rate = run1_a_wins / total if total else 0.0

    df["len_a"] = df["answer_a"].astype(str).str.len()
    df["len_b"] = df["answer_b"].astype(str).str.len()
    df["len_diff"] = df["len_b"] - df["len_a"]
    b_wins_when_longer = ((df["winner_after_swap"] == "B") & (df["len_diff"] > 0)).sum()
    b_total_longer = (df["len_diff"] > 0).sum()
    b_rate = (b_wins_when_longer / b_total_longer) if b_total_longer else 0.0

    a_wins_when_longer = ((df["winner_after_swap"] == "A") & (df["len_diff"] < 0)).sum()
    a_total_longer = (df["len_diff"] < 0).sum()
    a_rate = (a_wins_when_longer / a_total_longer) if a_total_longer else 0.0

    grp = df.groupby("winner_after_swap")["len_diff"].mean().round(1)
    tbl_md = "\n".join(f"| {k} | {v} |" for k, v in grp.items())
    tbl_md = "| winner_after_swap | mean len_diff (B-A) |\n|---|---|\n" + tbl_md

    lines = [
        "# Judge Bias Observations",
        "",
        "## Bias 1: Position bias (Answer A listed first in run 1)",
        "",
        f"- `run1_winner == 'A'`: **{run1_a_wins} / {total}** = **{pos_rate:.1%}**",
        "- Expected ~50% if no position bias; >55% suggests first-slot favoritism.",
        "",
        "## Bias 2: Length bias",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| B wins when B is longer | {b_wins_when_longer} / {b_total_longer} = **{b_rate:.1%}** |",
        f"| A wins when A is longer | {a_wins_when_longer} / {a_total_longer} = **{a_rate:.1%}** |",
        "",
        "## Table: mean len_diff (B-A) by final winner",
        "",
        tbl_md,
        "",
        "## Mitigation strategy",
        "",
        "- Keep **swap-and-average** for pairwise comparisons.",
        "- Add **length-normalized** presentation to the judge (truncate both to same token budget) for future runs.",
        "- Prefer **rubric-based absolute scoring** when stakes are high.",
        "",
    ]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
