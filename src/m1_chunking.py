import os, sys, glob, re
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (DATA_DIR, HIERARCHICAL_PARENT_SIZE, HIERARCHICAL_CHILD_SIZE,
                    SEMANTIC_THRESHOLD)


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)
    parent_id: str | None = None


def load_documents(data_dir: str = DATA_DIR) -> list[dict]:
    """Load all markdown/text files from data/. (Đã implement sẵn)"""
    docs = []
    for fp in sorted(glob.glob(os.path.join(data_dir, "*.md"))):
        with open(fp, encoding="utf-8") as f:
            docs.append({"text": f.read(), "metadata": {"source": os.path.basename(fp)}})
    return docs


# ─── Baseline: Basic Chunking (để so sánh) ──────────────


def chunk_basic(text: str, chunk_size: int = 500, metadata: dict | None = None) -> list[Chunk]:
    """
    Basic chunking: split theo paragraph (\\n\\n).
    Đây là baseline — KHÔNG phải mục tiêu của module này.
    (Đã implement sẵn)
    """
    metadata = metadata or {}
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for i, para in enumerate(paragraphs):
        if len(current) + len(para) > chunk_size and current:
            chunks.append(Chunk(text=current.strip(), metadata={**metadata, "chunk_index": len(chunks)}))
            current = ""
        current += para + "\n\n"
    if current.strip():
        chunks.append(Chunk(text=current.strip(), metadata={**metadata, "chunk_index": len(chunks)}))
    return chunks


# ─── Strategy 1: Semantic Chunking ───────────────────────


def chunk_semantic(text: str, threshold: float = SEMANTIC_THRESHOLD,
                   metadata: dict | None = None) -> list[Chunk]:
    """
    Split text by sentence similarity — nhóm câu cùng chủ đề.
    Tốt hơn basic vì không cắt giữa ý.

    Args:
        text: Input text.
        threshold: Cosine similarity threshold. Dưới threshold → tách chunk mới.
        metadata: Metadata gắn vào mỗi chunk.

    Returns:
        List of Chunk objects grouped by semantic similarity.
    """
    metadata = metadata or {}

    # 1. Split text into sentences
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n\n', text) if s.strip()]
    if not sentences:
        return []
    if len(sentences) == 1:
        return [Chunk(text=sentences[0], metadata={**metadata, "chunk_index": 0, "strategy": "semantic"})]

    # 2. Encode sentences using SentenceTransformer
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        model = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = model.encode(sentences, show_progress_bar=False)

        # 3. Compute cosine similarity between consecutive sentences
        def cosine_sim(a, b):
            denom = (np.linalg.norm(a) * np.linalg.norm(b))
            return float(np.dot(a, b) / denom) if denom > 0 else 0.0

        # 4. Group sentences by similarity threshold
        chunks: list[Chunk] = []
        current_group = [sentences[0]]

        for i in range(1, len(sentences)):
            sim = cosine_sim(embeddings[i - 1], embeddings[i])
            if sim < threshold:
                # Flush current group
                chunks.append(Chunk(
                    text=" ".join(current_group),
                    metadata={**metadata, "chunk_index": len(chunks), "strategy": "semantic"}
                ))
                current_group = []
            current_group.append(sentences[i])

        # Don't forget last group
        if current_group:
            chunks.append(Chunk(
                text=" ".join(current_group),
                metadata={**metadata, "chunk_index": len(chunks), "strategy": "semantic"}
            ))

        return chunks

    except ImportError:
        # Fallback: group by paragraph if sentence_transformers not available
        return chunk_basic(text, metadata=metadata)


# ─── Strategy 2: Hierarchical Chunking ──────────────────


def chunk_hierarchical(text: str, parent_size: int = HIERARCHICAL_PARENT_SIZE,
                       child_size: int = HIERARCHICAL_CHILD_SIZE,
                       metadata: dict | None = None) -> tuple[list[Chunk], list[Chunk]]:
    """
    Parent-child hierarchy: retrieve child (precision) → return parent (context).
    Đây là default recommendation cho production RAG.

    Args:
        text: Input text.
        parent_size: Chars per parent chunk.
        child_size: Chars per child chunk.
        metadata: Metadata gắn vào mỗi chunk.

    Returns:
        (parents, children) — mỗi child có parent_id link đến parent.
    """
    metadata = metadata or {}
    parents: list[Chunk] = []
    children: list[Chunk] = []

    # 1. Split text into paragraphs, then accumulate into parent chunks
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    current_parent_text = ""
    p_index = 0

    for para in paragraphs:
        # If adding this paragraph exceeds parent_size, flush current parent
        if len(current_parent_text) + len(para) > parent_size and current_parent_text:
            pid = f"parent_{p_index}"
            parent = Chunk(
                text=current_parent_text.strip(),
                metadata={**metadata, "chunk_type": "parent", "parent_id": pid}
            )
            parents.append(parent)

            # 2. Split parent into child chunks using sliding window
            parent_text = current_parent_text.strip()
            c_index = 0
            for start in range(0, len(parent_text), child_size):
                child_text = parent_text[start: start + child_size].strip()
                if child_text:
                    child = Chunk(
                        text=child_text,
                        metadata={**metadata, "chunk_type": "child", "child_index": c_index},
                        parent_id=pid,
                    )
                    children.append(child)
                    c_index += 1

            p_index += 1
            current_parent_text = ""

        current_parent_text += para + "\n\n"

    # Flush remaining text as last parent
    if current_parent_text.strip():
        pid = f"parent_{p_index}"
        parent = Chunk(
            text=current_parent_text.strip(),
            metadata={**metadata, "chunk_type": "parent", "parent_id": pid}
        )
        parents.append(parent)

        parent_text = current_parent_text.strip()
        c_index = 0
        for start in range(0, len(parent_text), child_size):
            child_text = parent_text[start: start + child_size].strip()
            if child_text:
                child = Chunk(
                    text=child_text,
                    metadata={**metadata, "chunk_type": "child", "child_index": c_index},
                    parent_id=pid,
                )
                children.append(child)
                c_index += 1

    return parents, children


# ─── Strategy 3: Structure-Aware Chunking ────────────────


def chunk_structure_aware(text: str, metadata: dict | None = None) -> list[Chunk]:
    """
    Parse markdown headers → chunk theo logical structure.
    Giữ nguyên tables, code blocks, lists — không cắt giữa chừng.

    Args:
        text: Markdown text.
        metadata: Metadata gắn vào mỗi chunk.

    Returns:
        List of Chunk objects, mỗi chunk = 1 section (header + content).
    """
    metadata = metadata or {}

    # 1. Split by markdown headers (H1, H2, H3)
    sections = re.split(r'(^#{1,3}\s+.+$)', text, flags=re.MULTILINE)

    chunks: list[Chunk] = []
    current_header = ""
    current_content = ""

    # 2. Pair each header with its content
    for part in sections:
        if re.match(r'^#{1,3}\s+', part):
            # Flush previous section
            if current_content.strip():
                section_text = f"{current_header}\n{current_content}".strip()
                chunks.append(Chunk(
                    text=section_text,
                    metadata={
                        **metadata,
                        "section": current_header.strip(),
                        "strategy": "structure",
                        "chunk_index": len(chunks),
                    }
                ))
            current_header = part.strip()
            current_content = ""
        else:
            current_content += part

    # 3. Don't forget the last section
    if current_content.strip():
        section_text = f"{current_header}\n{current_content}".strip() if current_header else current_content.strip()
        chunks.append(Chunk(
            text=section_text,
            metadata={
                **metadata,
                "section": current_header.strip(),
                "strategy": "structure",
                "chunk_index": len(chunks),
            }
        ))

    # Fallback: if no headers found, use basic chunking
    if not chunks:
        return chunk_basic(text, metadata=metadata)

    return chunks


# ─── A/B Test: Compare All Strategies ────────────────────


def compare_strategies(documents: list[dict]) -> dict:
    """
    Run all strategies on documents and compare.

    Returns:
        {"basic": {...}, "semantic": {...}, "hierarchical": {...}, "structure": {...}}
    """
    results: dict[str, dict] = {
        "basic": {"chunks": [], "num_chunks": 0, "avg_length": 0, "min_length": 0, "max_length": 0},
        "semantic": {"chunks": [], "num_chunks": 0, "avg_length": 0, "min_length": 0, "max_length": 0},
        "hierarchical": {"chunks": [], "num_chunks": 0, "avg_length": 0, "min_length": 0, "max_length": 0},
        "structure": {"chunks": [], "num_chunks": 0, "avg_length": 0, "min_length": 0, "max_length": 0},
    }

    for doc in documents:
        text = doc["text"]
        meta = doc.get("metadata", {})

        # Run each strategy
        basic_chunks = chunk_basic(text, metadata=meta)
        semantic_chunks = chunk_semantic(text, metadata=meta)
        _, hier_children = chunk_hierarchical(text, metadata=meta)
        structure_chunks = chunk_structure_aware(text, metadata=meta)

        for key, chunks in [
            ("basic", basic_chunks),
            ("semantic", semantic_chunks),
            ("hierarchical", hier_children),
            ("structure", structure_chunks),
        ]:
            results[key]["chunks"].extend(chunks)

    # 2. Compute stats per strategy
    print(f"\n{'Strategy':<25} | {'Chunks':>6} | {'Avg Len':>7} | {'Min':>5} | {'Max':>5}")
    print("-" * 60)

    for name, data in results.items():
        chunks = data["chunks"]
        if chunks:
            lengths = [len(c.text) for c in chunks]
            data["num_chunks"] = len(chunks)
            data["avg_length"] = int(sum(lengths) / len(lengths))
            data["min_length"] = min(lengths)
            data["max_length"] = max(lengths)
        print(f"{name:<25} | {data['num_chunks']:>6} | {data['avg_length']:>7} | {data['min_length']:>5} | {data['max_length']:>5}")

    # Remove raw chunk objects from return value (not serializable)
    return {k: {kk: vv for kk, vv in v.items() if kk != "chunks"} for k, v in results.items()}


if __name__ == "__main__":
    docs = load_documents()
    print(f"Loaded {len(docs)} documents")
    results = compare_strategies(docs)
    for name, stats in results.items():
        print(f"  {name}: {stats}")
