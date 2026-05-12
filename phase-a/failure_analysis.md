# Failure Cluster Analysis

## Bottom 10 Questions

| # | Question (truncated) | F | AR | CP | CR | Avg | Cluster |
|---|----------------------|---|----|----|-----|---------|
| 1 | Quy trình đánh giá tác động xử lý dữ liệu cá nhân bao gồm nh… | 0.00 | 0.00 | 1.00 | 0.67 | 0.42 | C1 |
| 2 | Bên kiểm soát dữ liệu có nghĩa vụ gì khi xảy ra sự cố lộ lọt… | 0.00 | 0.00 | 1.00 | 1.00 | 0.50 | C1 |
| 3 | Sự khác biệt giữa bên kiểm soát dữ liệu và bên xử lý dữ liệu… | 0.80 | 0.86 | 0.83 | 0.50 | 0.75 | C1 |
| 4 | Theo Nghị định 13/2023, liệt kê các điều kiện chính khi chuy… | 1.00 | 0.84 | 0.50 | 0.67 | 0.75 | C2 |
| 5 | Tổ chức nước ngoài chuyển dữ liệu cá nhân ra khỏi Việt Nam c… | 0.80 | 0.89 | 0.83 | 0.80 | 0.83 | C1 |
| 6 | Nguyên tắc xử lý dữ liệu cá nhân theo Nghị định 13/2023 là g… | 1.00 | 0.85 | 0.58 | 1.00 | 0.86 | C2 |
| 7 | Chủ thể dữ liệu cá nhân có những quyền gì theo Nghị định 13/… | 0.91 | 0.85 | 1.00 | 0.80 | 0.89 | C1 |
| 8 | Dữ liệu cá nhân nhạy cảm bao gồm những loại nào theo Nghị đị… | 1.00 | 0.81 | 1.00 | 1.00 | 0.95 | C2 |
| 9 | Dữ liệu cá nhân của trẻ em được xử lý theo quy định đặc biệt… | 1.00 | 0.84 | 1.00 | 1.00 | 0.96 | C2 |
| 10 | Điều kiện hợp pháp để xử lý dữ liệu cá nhân mà không cần sự … | 1.00 | 0.85 | 1.00 | 1.00 | 0.96 | C2 |

## Clusters Identified

### Cluster C1: Retrieval / grounding failures

**Pattern:** Low context_recall or faithfulness — thiếu chunk hoặc câu trả lời lệch context.

**Examples:**
- Quy trình đánh giá tác động xử lý dữ liệu cá nhân bao gồm những bước nào?
- Bên kiểm soát dữ liệu có nghĩa vụ gì khi xảy ra sự cố lộ lọt dữ liệu cá nhân?
- Sự khác biệt giữa bên kiểm soát dữ liệu và bên xử lý dữ liệu trong Nghị định 13/

**Root cause:** `top_k` hoặc hybrid retrieval chưa đủ; chunk nhỏ hoặc noise.

**Proposed fix:**

- Tăng `rerank_top_k` từ 3 → 5 trong `run_query` / `rag_answer_and_contexts`.
- Bật hoặc tinh chỉnh hybrid BM25+dense weights trong `HybridSearch`.

### Cluster C2: Precision / relevancy issues

**Pattern:** `context_precision` hoặc `answer_relevancy` thấp — nhiễu context hoặc câu trả lời lệch intent.

**Examples:**
- Theo Nghị định 13/2023, liệt kê các điều kiện chính khi chuyển dữ liệu cá nhân r
- Nguyên tắc xử lý dữ liệu cá nhân theo Nghị định 13/2023 là gì?
- Dữ liệu cá nhân nhạy cảm bao gồm những loại nào theo Nghị định 13/2023?

**Root cause:** Reranker hoặc prompt chưa ép trả lời đúng trích dẫn.

**Proposed fix:**

- Thêm re-ranker mạnh hơn hoặc tăng ngưỡng lọc score trước khi đưa vào LLM.
- Ràng buộc output: yêu cầu trích ý chính từ context, từ chối khi không đủ bằng chứng.
