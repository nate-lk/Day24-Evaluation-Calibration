import os, sys, json, re
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY


@dataclass
class EnrichedChunk:
    """Chunk đã được làm giàu."""
    original_text: str
    enriched_text: str
    summary: str
    hypothesis_questions: list[str]
    auto_metadata: dict
    method: str  # "contextual", "summary", "hyqa", "full"


def _get_openai_client():
    """Helper: return OpenAI client nếu API key available."""
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=OPENAI_API_KEY)
    except ImportError:
        return None


# ─── Technique 1: Chunk Summarization ────────────────────


def summarize_chunk(text: str) -> str:
    """
    Tạo summary ngắn cho chunk.
    Embed summary thay vì (hoặc cùng với) raw chunk → giảm noise.

    Args:
        text: Raw chunk text.

    Returns:
        Summary string (2-3 câu).
    """
    client = _get_openai_client()

    if client:
        # Option A: LLM summarization
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Tóm tắt đoạn văn sau trong 2-3 câu ngắn gọn bằng tiếng Việt. Giữ lại các thông tin quan trọng.",
                    },
                    {"role": "user", "content": text},
                ],
                max_tokens=150,
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            pass

    # Option B: Extractive fallback — lấy 2 câu đầu
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    summary = ". ".join(sentences[:2])
    if summary and not summary.endswith("."):
        summary += "."
    return summary or text[:200]


# ─── Technique 2: Hypothesis Question-Answer (HyQA) ─────


def generate_hypothesis_questions(text: str, n_questions: int = 3) -> list[str]:
    """
    Generate câu hỏi mà chunk có thể trả lời.
    Index cả questions lẫn chunk → query match tốt hơn (bridge vocabulary gap).

    Args:
        text: Raw chunk text.
        n_questions: Số câu hỏi cần generate.

    Returns:
        List of question strings.
    """
    client = _get_openai_client()

    if client:
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"Dựa trên đoạn văn, tạo {n_questions} câu hỏi mà đoạn văn có thể trả lời. "
                            "Trả về mỗi câu hỏi trên 1 dòng, không đánh số."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                max_tokens=200,
                temperature=0.5,
            )
            raw = resp.choices[0].message.content.strip()
            questions = [
                q.strip().lstrip("0123456789.-) ")
                for q in raw.split("\n")
                if q.strip()
            ]
            return questions[:n_questions]
        except Exception:
            pass

    # Extractive fallback: extract key noun phrases as "... là gì?" questions
    # Find sentences containing key terms
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    questions: list[str] = []

    for sent in sentences[:n_questions]:
        sent = sent.strip()
        if len(sent) > 20:
            # Turn statement into question
            if sent.endswith("."):
                sent = sent[:-1]
            questions.append(f"{sent[:60].rstrip()} là gì?" if len(sent) > 60 else f"{sent} — điều này có nghĩa gì?")

    return questions[:n_questions] if questions else [f"Đoạn văn này nói về điều gì?"]


# ─── Technique 3: Contextual Prepend (Anthropic style) ──


def contextual_prepend(text: str, document_title: str = "") -> str:
    """
    Prepend context giải thích chunk nằm ở đâu trong document.
    Anthropic benchmark: giảm 49% retrieval failure (alone).

    Args:
        text: Raw chunk text.
        document_title: Tên document gốc.

    Returns:
        Text với context prepended.
    """
    client = _get_openai_client()

    if client:
        try:
            doc_info = f"Tài liệu: {document_title}\n\n" if document_title else ""
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Viết 1 câu ngắn (tối đa 30 từ) mô tả đoạn văn này nằm ở đâu trong tài liệu "
                            "và nói về chủ đề gì. Chỉ trả về 1 câu, không giải thích thêm."
                        ),
                    },
                    {"role": "user", "content": f"{doc_info}Đoạn văn:\n{text}"},
                ],
                max_tokens=80,
                temperature=0.2,
            )
            context_sentence = resp.choices[0].message.content.strip()
            return f"{context_sentence}\n\n{text}"
        except Exception:
            pass

    # Fallback: prepend document title if available
    if document_title:
        return f"Trích từ tài liệu: {document_title}.\n\n{text}"
    return text


# ─── Technique 4: Auto Metadata Extraction ──────────────


def extract_metadata(text: str) -> dict:
    """
    LLM extract metadata tự động: topic, entities, date_range, category.

    Args:
        text: Raw chunk text.

    Returns:
        Dict with extracted metadata fields.
    """
    client = _get_openai_client()

    if client:
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            'Trích xuất metadata từ đoạn văn. Trả về JSON hợp lệ: '
                            '{"topic": "...", "entities": ["..."], '
                            '"category": "policy|hr|it|finance|legal|other", "language": "vi|en"}'
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                max_tokens=150,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content.strip()
            return json.loads(raw)
        except Exception:
            pass

    # Rule-based fallback
    metadata: dict = {"language": "vi", "category": "other", "entities": [], "topic": ""}

    # Detect category by keywords
    text_lower = text.lower()
    if any(k in text_lower for k in ["nghị định", "điều ", "khoản ", "luật", "quy định"]):
        metadata["category"] = "legal"
    elif any(k in text_lower for k in ["doanh thu", "lợi nhuận", "tài chính", "vốn", "chi phí"]):
        metadata["category"] = "finance"
    elif any(k in text_lower for k in ["nhân viên", "nghỉ phép", "lương", "hợp đồng lao động"]):
        metadata["category"] = "hr"
    elif any(k in text_lower for k in ["hệ thống", "mạng", "bảo mật", "phần mềm", "dữ liệu"]):
        metadata["category"] = "it"

    # Extract Vietnamese entities (organizations, laws)
    entities = re.findall(r'Nghị định \d+/\d+/[A-Z\-]+|Điều \d+|Chương [IVX]+', text)
    metadata["entities"] = list(set(entities))[:5]

    # Topic: first significant noun phrase
    words = text.split()
    metadata["topic"] = " ".join(words[:5]) if words else ""

    return metadata


# ─── Full Enrichment Pipeline ────────────────────────────


def enrich_chunks(
    chunks: list[dict],
    methods: list[str] | None = None,
) -> list[EnrichedChunk]:
    """
    Chạy enrichment pipeline trên danh sách chunks.

    Args:
        chunks: List of {"text": str, "metadata": dict}
        methods: List of methods to apply. Default: ["contextual", "hyqa", "metadata"]
                 Options: "summary", "hyqa", "contextual", "metadata", "full"

    Returns:
        List of EnrichedChunk objects.
    """
    if methods is None:
        methods = ["contextual", "hyqa", "metadata"]

    use_summary = "summary" in methods or "full" in methods
    use_hyqa = "hyqa" in methods or "full" in methods
    use_contextual = "contextual" in methods or "full" in methods
    use_metadata = "metadata" in methods or "full" in methods

    enriched: list[EnrichedChunk] = []

    for chunk in chunks:
        text = chunk["text"]
        chunk_meta = chunk.get("metadata", {})
        source = chunk_meta.get("source", "")

        # Apply each technique
        summary = summarize_chunk(text) if use_summary else ""
        questions = generate_hypothesis_questions(text) if use_hyqa else []
        enriched_text = contextual_prepend(text, source) if use_contextual else text
        auto_meta = extract_metadata(text) if use_metadata else {}

        enriched.append(EnrichedChunk(
            original_text=text,
            enriched_text=enriched_text,
            summary=summary,
            hypothesis_questions=questions,
            auto_metadata={**chunk_meta, **auto_meta},
            method="+".join(methods),
        ))

    return enriched


# ─── Main ────────────────────────────────────────────────

if __name__ == "__main__":
    sample = (
        "Nhân viên chính thức được nghỉ phép năm 12 ngày làm việc mỗi năm. "
        "Số ngày nghỉ phép tăng thêm 1 ngày cho mỗi 5 năm thâm niên công tác."
    )

    print("=== Enrichment Pipeline Demo ===\n")
    print(f"Original: {sample}\n")

    s = summarize_chunk(sample)
    print(f"Summary: {s}\n")

    qs = generate_hypothesis_questions(sample)
    print(f"HyQA questions: {qs}\n")

    ctx = contextual_prepend(sample, "Sổ tay nhân viên VinUni 2024")
    print(f"Contextual: {ctx}\n")

    meta = extract_metadata(sample)
    print(f"Auto metadata: {meta}")
