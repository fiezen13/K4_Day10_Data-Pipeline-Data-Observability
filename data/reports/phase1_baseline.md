# Báo cáo Baseline — Data Quality & Freshness

Báo cáo này đọc được độc lập, giải thích trạng thái dữ liệu **trước khi corruption**.
Số liệu lấy từ corpus clean hiện có (24 papers).

---

## 1. Kết luận nhanh

| Hạng mục | Kết quả |
| --- | --- |
| Data quality | **PASS** |
| Freshness | **PASS** |
| Có thể freeze làm baseline? | **Có** |
| Evaluation metrics (RAG) | Chưa có — chờ pipeline evaluate |

**Ý nghĩa:** dữ liệu clean hiện tại đủ sạch và đủ mới để dùng làm mốc so sánh cho corrupted/repaired.

---

## 2. Nguồn dữ liệu

| Thông tin | Giá trị |
| --- | --- |
| API | Crossref REST API |
| Query | agentic retrieval augmented generation large language model |
| Filter | `from-pub-date` + `has-abstract:true` |
| Số paper sau clean | 24 |
| Ngưỡng freshness | 180 ngày |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Retrieval top-k | 4 |

---

## 3. Chất lượng dữ liệu (Quality)

| Tín hiệu | Giá trị |
| --- | ---: |
| Overall status | PASS |
| Total rows | 24 |
| Failed checks | none |
| Null / duplicate paper_id | 0 / 0 |
| Null titles | 0 |
| Empty / short summaries | 0 |
| Empty embedding text | 0 |
| Negative age_days | 0 |
| Stale rows | 0 |

Tất cả check lab đều **PASS** (row count, paper_id, title, summary ≥ 100, text_for_embedding, age_days, freshness ≤ 180).

---

## 4. Freshness

| Tín hiệu | Giá trị |
| --- | ---: |
| Status | PASS |
| Latest published | 2026-08-01 |
| Oldest published | 2026-02-12 |
| Mean age | 76.58 ngày |
| Max age | 175 ngày (< 180) |
| Stale rows | 0 |

---

## 5. Liên hệ với corruption / repair

Sau khi đồng bộ artifact từ nhánh `yenn`:

| Trạng thái | Quality | Freshness | Rows |
| --- | --- | --- | ---: |
| Baseline | PASS | PASS | 24 |
| Corrupted | FAIL | FAIL | 23 |
| Repaired | PASS | PASS | 24 |

Xem chi tiết so sánh: `data/reports/corruption_comparison.md`.

---

## 6. File liên quan

| File | Vai trò |
| --- | --- |
| `data/quality/baseline_quality.json` | Quality JSON |
| `data/quality/freshness_report.json` | Freshness JSON |
| `data/reports/phase1_report.md` | Report do `reporting.py` sinh |
| `report/quality_checks.md` | Giải thích check/threshold |
| `data/reports/corruption_comparison.md` | So sánh 3 trạng thái (dễ đọc) |
