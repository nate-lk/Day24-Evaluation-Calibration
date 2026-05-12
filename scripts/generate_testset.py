#!/usr/bin/env python3
"""Lab 24 Phase A.1 — Build testset_v1.csv (50 rows, 50/25/25 distribution)."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from config import DATA_DIR, OPENAI_API_KEY, TEST_SET_PATH  # noqa: E402


def _load_markdown_docs() -> list[dict]:
    import glob

    docs = []
    for fp in sorted(glob.glob(os.path.join(DATA_DIR, "*.md"))):
        with open(fp, encoding="utf-8") as f:
            docs.append({"text": f.read(), "source": os.path.basename(fp)})
    return docs


def _try_ragas_generator(out_csv: str, test_size: int) -> bool:
    if not OPENAI_API_KEY:
        return False
    try:
        from langchain_community.document_loaders import DirectoryLoader
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from ragas.testset import TestsetGenerator
        from ragas.testset.evolutions import multi_context, reasoning, simple
    except Exception:
        return False

    try:
        loader = DirectoryLoader(DATA_DIR, glob="**/*.md")
        documents = loader.load()
        if len(documents) < 2:
            return False
        gen = TestsetGenerator.from_langchain(
            generator_llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.3),
            critic_llm=ChatOpenAI(model="gpt-4o-mini", temperature=0),
            embeddings=OpenAIEmbeddings(),
        )
        testset = gen.generate_with_langchain_docs(
            documents=documents,
            test_size=test_size,
            distributions={simple: 0.5, reasoning: 0.25, multi_context: 0.25},
        )
        df = testset.to_pandas()
        df.to_csv(out_csv, index=False)
        return True
    except Exception:
        return False


def _fallback_rows(test_size: int = 50) -> pd.DataFrame:
    """Deterministic synthetic set from JSON + corpus chunks (no API)."""
    with open(TEST_SET_PATH, encoding="utf-8") as f:
        base = json.load(f)
    docs = _load_markdown_docs()
    chunks: list[str] = []
    for d in docs:
        parts = [p.strip() for p in d["text"].split("\n\n") if len(p.strip()) > 80]
        chunks.extend(parts[:12])
    if not chunks:
        chunks = [b.get("ground_truth", "")[:500] for b in base]

    evolution = (
        ["simple"] * (test_size // 2)
        + ["reasoning"] * (test_size // 4)
        + ["multi_context"] * (test_size - test_size // 2 - test_size // 4)
    )
    rows = []
    for i in range(test_size):
        b = base[i % len(base)]
        q = b["question"]
        gt = b["ground_truth"]
        if i >= len(base):
            q = f"[Biến thể {i}] {q}"
        if i == 9:
            q = "Theo Nghị định 13/2023, liệt kê các điều kiện chính khi chuyển dữ liệu cá nhân ra nước ngoài."
        ev = evolution[i]
        if ev == "simple":
            ctx = [chunks[i % len(chunks)]]
        elif ev == "reasoning":
            c0 = chunks[i % len(chunks)]
            ctx = [c0 + "\n\n" + (gt[:600])]
        else:
            c1 = chunks[i % len(chunks)]
            c2 = chunks[(i + 1) % len(chunks)]
            ctx = [c1, c2]
        rows.append(
            {
                "question": q,
                "ground_truth": gt,
                "contexts": json.dumps(ctx, ensure_ascii=False),
                "evolution_type": ev,
            }
        )
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        default=os.path.join(ROOT, "phase-a", "testset_v1.csv"),
        help="Output CSV path",
    )
    ap.add_argument("--test-size", type=int, default=50)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    if _try_ragas_generator(args.out, args.test_size):
        print(f"RAGAS TestsetGenerator wrote {args.out}")
        return
    df = _fallback_rows(args.test_size)
    df.to_csv(args.out, index=False)
    print(f"Fallback synthetic testset wrote {args.out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
