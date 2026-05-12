from config import TEST_SET_PATH
import os
import sys
import json
from dataclasses import dataclass
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class EvalResult:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


def load_test_set(path: str = TEST_SET_PATH) -> list[dict]:
    """Load test set from JSON. (Đã implement sẵn)"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_ragas(questions: list[str], answers: list[str],
                   contexts: list[list[str]], ground_truths: list[str]) -> dict:
    """Run RAGAS evaluation with 4 metrics."""
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )
    from datasets import Dataset

    # 1. Build HuggingFace Dataset — RAGAS expects list[list[str]] for contexts
    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,          # must be list[list[str]]
        "ground_truth": ground_truths,
    })

    # 2. Run evaluation
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy,
                 context_precision, context_recall],
    )

    # 3. Extract per-question scores
    df = result.to_pandas()
    
    # Mapping RAGAS 0.2+ columns to our internal names
    col_map = {
        "user_input": "question",
        "retrieved_contexts": "contexts",
        "response": "answer",
        "reference": "ground_truth"
    }

    per_question: list[EvalResult] = []
    for _, row in df.iterrows():
        per_question.append(EvalResult(
            question=str(row.get("user_input") or row.get("question") or ""),
            answer=str(row.get("response") or row.get("answer") or ""),
            contexts=list(row.get("retrieved_contexts") or row.get("contexts") or []),
            ground_truth=str(row.get("reference") or row.get("ground_truth") or ""),
            faithfulness=float(row.get("faithfulness", 0.0) or 0.0),
            answer_relevancy=float(row.get("answer_relevancy", 0.0) or 0.0),
            context_precision=float(row.get("context_precision", 0.0) or 0.0),
            context_recall=float(row.get("context_recall", 0.0) or 0.0),
        ))

    # 4. Aggregate mean scores
    def safe_mean(key: str) -> float:
        vals = [getattr(r, key)
                for r in per_question if getattr(r, key) is not None]
        return round(mean(vals), 4) if vals else 0.0

    return {
        "faithfulness":       safe_mean("faithfulness"),
        "answer_relevancy":   safe_mean("answer_relevancy"),
        "context_precision":  safe_mean("context_precision"),
        "context_recall":     safe_mean("context_recall"),
        "per_question":       per_question,
    }


def failure_analysis(eval_results: list[EvalResult], bottom_n: int = 10) -> list[dict]:
    """Analyze bottom-N worst questions using Diagnostic Tree."""

    # Diagnostic mapping
    DIAGNOSTIC_TREE = {
        "faithfulness": {
            "threshold": 0.85,
            "diagnosis": "LLM hallucinating — trả lời không dựa trên context",
            "suggested_fix": "Tighten system prompt: 'Chỉ trả lời dựa trên context được cung cấp.' Lower temperature.",
        },
        "context_recall": {
            "threshold": 0.75,
            "diagnosis": "Missing relevant chunks — context thiếu thông tin cần thiết",
            "suggested_fix": "Improve chunking strategy (hierarchical) hoặc tăng top-k retrieval, thêm BM25 hybrid.",
        },
        "context_precision": {
            "threshold": 0.75,
            "diagnosis": "Too many irrelevant chunks — context chứa noise",
            "suggested_fix": "Add reranking (bge-reranker-v2-m3) để lọc top-3 relevant chunks trước khi đưa vào LLM.",
        },
        "answer_relevancy": {
            "threshold": 0.80,
            "diagnosis": "Answer doesn't match question intent",
            "suggested_fix": "Improve prompt template: thêm few-shot examples, rõ ràng hóa format output.",
        },
    }

    # 1. Compute avg score per question
    scored = []
    for r in eval_results:
        avg = mean([r.faithfulness, r.answer_relevancy,
                   r.context_precision, r.context_recall])
        scored.append((avg, r))

    # 2. Sort ascending → bottom-N worst
    scored.sort(key=lambda x: x[0])
    bottom = scored[:bottom_n]

    failures: list[dict] = []
    for avg_score, r in bottom:
        # 3. Find worst metric
        metric_scores = {
            "faithfulness":      r.faithfulness,
            "answer_relevancy":  r.answer_relevancy,
            "context_precision": r.context_precision,
            "context_recall":    r.context_recall,
        }
        worst_metric = min(metric_scores, key=lambda m: metric_scores[m])
        diag = DIAGNOSTIC_TREE[worst_metric]

        failures.append({
            "question":      r.question,
            "worst_metric":  worst_metric,
            "score":         round(metric_scores[worst_metric], 4),
            "avg_score":     round(avg_score, 4),
            "diagnosis":     diag["diagnosis"],
            "suggested_fix": diag["suggested_fix"],
        })

    return failures


def save_report(results: dict, failures: list[dict], path: str = "ragas_report.json"):
    """Save evaluation report to JSON. (Đã implement sẵn)"""
    report = {
        "aggregate": {k: v for k, v in results.items() if k != "per_question"},
        "num_questions": len(results.get("per_question", [])),
        "failures": failures,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    test_set = load_test_set()
    print(f"Loaded {len(test_set)} test questions")
    print("Run pipeline.py first to generate answers, then call evaluate_ragas().")
