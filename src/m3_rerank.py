import os, sys, time
from dataclasses import dataclass
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RERANK_TOP_K


@dataclass
class RerankResult:
    text: str
    original_score: float
    rerank_score: float
    metadata: dict
    rank: int


class CrossEncoderReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """Lazy-load cross-encoder model (first call slow, subsequent fast)."""
        if self._model is None:
            try:
                # Option A: FlagEmbedding (preferred for bge models)
                from FlagEmbedding import FlagReranker
                self._model = FlagReranker(self.model_name, use_fp16=True)
                self._model_type = "flag"
            except ImportError:
                # Option B: sentence-transformers CrossEncoder fallback
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self.model_name)
                self._model_type = "cross_encoder"
        return self._model

    def rerank(self, query: str, documents: list[dict], top_k: int = RERANK_TOP_K) -> list[RerankResult]:
        """Rerank documents: top-20 → top-k using cross-encoder."""
        if not documents:
            return []

        model = self._load_model()

        # 1. Build (query, doc) pairs for cross-encoder scoring
        pairs = [(query, doc["text"]) for doc in documents]

        # 2. Score all pairs
        if self._model_type == "flag":
            scores = model.compute_score(pairs, normalize=True)
        else:
            scores = model.predict(pairs).tolist()

        # Ensure scores is a list (not numpy array)
        if not isinstance(scores, list):
            scores = list(scores)

        # 3. Combine scores with documents and sort descending
        scored_docs = sorted(
            zip(scores, documents),
            key=lambda x: x[0],
            reverse=True,
        )

        # 4. Return top_k as RerankResult
        results: list[RerankResult] = []
        for rank, (score, doc) in enumerate(scored_docs[:top_k]):
            results.append(RerankResult(
                text=doc["text"],
                original_score=float(doc.get("score", 0.0)),
                rerank_score=float(score),
                metadata=doc.get("metadata", {}),
                rank=rank,
            ))

        return results


class FlashrankReranker:
    """Lightweight alternative (<5ms). Optional."""
    def __init__(self):
        self._model = None

    def rerank(self, query: str, documents: list[dict], top_k: int = RERANK_TOP_K) -> list[RerankResult]:
        """Rerank using flashrank (fast, CPU-friendly)."""
        if not documents:
            return []

        try:
            from flashrank import Ranker, RerankRequest

            if self._model is None:
                self._model = Ranker()

            passages = [{"id": i, "text": doc["text"]} for i, doc in enumerate(documents)]
            request = RerankRequest(query=query, passages=passages)
            flash_results = self._model.rerank(request)

            results: list[RerankResult] = []
            for rank, item in enumerate(flash_results[:top_k]):
                idx = item["id"]
                results.append(RerankResult(
                    text=item["text"],
                    original_score=float(documents[idx].get("score", 0.0)),
                    rerank_score=float(item.get("score", 0.0)),
                    metadata=documents[idx].get("metadata", {}),
                    rank=rank,
                ))
            return results

        except ImportError:
            # Fallback to cross-encoder if flashrank not installed
            return CrossEncoderReranker().rerank(query, documents, top_k=top_k)


def benchmark_reranker(reranker, query: str, documents: list[dict], n_runs: int = 5) -> dict:
    """Benchmark latency over n_runs (excluding first warmup call)."""
    # Warmup: ensures model is loaded before timing
    reranker.rerank(query, documents)

    times: list[float] = []
    for _ in range(n_runs):
        start = time.perf_counter()
        reranker.rerank(query, documents)
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)

    sorted_times = sorted(times)
    p95_index = max(0, int(len(times) * 0.95) - 1)

    return {
        "avg_ms": round(mean(times), 2),
        "min_ms": round(min(times), 2),
        "max_ms": round(max(times), 2),
        "p95_ms": round(sorted_times[p95_index], 2),
        "n_runs": n_runs,
    }


if __name__ == "__main__":
    query = "Nhân viên được nghỉ phép bao nhiêu ngày?"
    docs = [
        {"text": "Nhân viên được nghỉ 12 ngày/năm.", "score": 0.8, "metadata": {}},
        {"text": "Mật khẩu thay đổi mỗi 90 ngày.", "score": 0.7, "metadata": {}},
        {"text": "Thời gian thử việc là 60 ngày.", "score": 0.75, "metadata": {}},
    ]
    reranker = CrossEncoderReranker()
    for r in reranker.rerank(query, docs):
        print(f"[{r.rank}] {r.rerank_score:.4f} | {r.text}")
