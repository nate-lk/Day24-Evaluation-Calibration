#!/usr/bin/env python3
"""Lab 24 Phase B.3 — Cohen's kappa: human vs judge (aligned by question)."""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402
from sklearn.metrics import cohen_kappa_score  # noqa: E402


def interpret(kappa: float) -> str:
    if kappa < 0:
        return "WORSE than chance — kiểm tra lại nhãn và mapping A/B."
    if kappa < 0.2:
        return "Slight agreement — judge/prompt cần xem lại."
    if kappa < 0.4:
        return "Fair agreement — vẫn yếu."
    if kappa < 0.6:
        return "Moderate agreement — dùng được cho pilot/monitoring."
    if kappa < 0.8:
        return "Substantial agreement — gần production-ready."
    return "Almost perfect — hiếm; kiểm tra leakage/overfit."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--human", default=os.path.join(ROOT, "phase-b", "human_labels.csv"))
    ap.add_argument("--pairwise", default=os.path.join(ROOT, "phase-b", "pairwise_results.csv"))
    args = ap.parse_args()

    human = pd.read_csv(args.human)
    judge_df = pd.read_csv(args.pairwise)

    merged = human.merge(judge_df, on="question", how="inner")
    if len(merged) < 2:
        print("Need overlapping 'question' rows in human_labels.csv and pairwise_results.csv")
        sys.exit(1)

    h = merged["human_winner"].astype(str).str.lower().tolist()
    j = merged["winner_after_swap"].astype(str).str.lower().tolist()
    kappa = float(cohen_kappa_score(h, j))
    print(f"Cohen's kappa (n={len(merged)}): {kappa:.3f}")
    print(interpret(kappa))
    if kappa < 0.6:
        print(
            "\nRoot cause checklist: đồng bộ nghĩa A/B với answer_a/answer_b; "
            "length bias; judge prompt quá mơ hồ."
        )


if __name__ == "__main__":
    main()
