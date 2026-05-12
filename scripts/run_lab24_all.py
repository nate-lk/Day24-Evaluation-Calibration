#!/usr/bin/env python3
"""Orchestrate Lab 24 artifact generation (best-effort; some steps need API keys + Qdrant)."""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd: list[str], **kwargs) -> int:
    print("+", " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT, **kwargs)


def write_human_labels_stub(pairwise_csv: str, out_csv: str) -> None:
    import pandas as pd

    df = pd.read_csv(pairwise_csv).head(10).copy()
    # Simulated human labels: mostly agree with judge; two intentional disagreements for calibration demo.
    hw = []
    for i, w in enumerate(df["winner_after_swap"].tolist()):
        w = str(w).lower()
        if i == 2:
            hw.append("b" if w == "a" else ("a" if w == "b" else "tie"))
        elif i == 7:
            hw.append("tie" if w != "tie" else "a")
        else:
            hw.append(w)
    notes = ["aligned with swap judge"] * 10
    notes[2] = "disagree: prefer longer answer"
    notes[7] = "disagree: call tie"
    out = pd.DataFrame(
        {
            "question": df["question"],
            "human_winner": [w.upper() if w in ("a", "b") else "tie" for w in hw],
            "confidence": ["high"] * 10,
            "notes": notes,
        }
    )
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    out.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv} (stub — replace with your own labels for real calibration)")


def main() -> int:
    os.makedirs(os.path.join(ROOT, "phase-a"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "phase-b"), exist_ok=True)
    if run([sys.executable, "scripts/generate_testset.py"]) != 0:
        return 1
    # Pairwise (slow: many RAG + judge calls). Skip with SKIP_PAIRWISE=1 after first run.
    skip_pw = os.getenv("SKIP_PAIRWISE", "").lower() in ("1", "true", "yes")
    if not skip_pw:
        if run([sys.executable, "scripts/run_pairwise_judge.py", "--limit", "30"]) != 0:
            return 1
        pw = os.path.join(ROOT, "phase-b", "pairwise_results.csv")
        write_human_labels_stub(pw, os.path.join(ROOT, "phase-b", "human_labels.csv"))
        if run([sys.executable, "scripts/run_bias_report.py"]) != 0:
            return 1
        if run([sys.executable, "phase-b", "kappa_analysis.py"]) != 0:
            return 1
    else:
        print("SKIP_PAIRWISE set — skipping pairwise, human_labels, bias, kappa.")
    skip_abs = os.getenv("SKIP_ABSOLUTE", "").lower() in ("1", "true", "yes")
    if not skip_abs:
        if run([sys.executable, "scripts/run_absolute_judge.py", "--limit", "30"]) != 0:
            return 1
    else:
        print("SKIP_ABSOLUTE set — skipping absolute judge (needs RAG + optional OpenAI).")
    print("\nOptional next steps (require services / spend):")
    print("  docker compose up -d   # Qdrant for retrieval")
    print("  python scripts/run_eval.py          # RAGAS on full testset")
    print("  python scripts/run_phase_c_eval.py  # guardrail CSVs + benchmark")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
