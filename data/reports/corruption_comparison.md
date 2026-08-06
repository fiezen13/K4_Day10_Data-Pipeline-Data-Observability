# So sánh 3 trạng thái — Baseline / Corrupted / Repaired

Báo cáo dễ đọc cho người. Số liệu quality/freshness lấy từ cùng bộ check của lab.
**Evaluation RAG metrics** vẫn đang chờ Integration chạy evaluate (hiện `n/a`).

---

## 1. Kết luận nhanh

| Câu hỏi | Trả lời |
| --- | --- |
| Corruption có làm quality xấu đi không? | **Có** — corrupted FAIL |
| Corruption có làm freshness xấu đi không? | **Có** — stale + không fresh |
| Repair có kéo về gần baseline không? | **Có** — repaired PASS, khớp baseline |
| Repair có sửa tay corrupted không? | **Không** — rebuild từ `data/raw/crossref_records.json` |

Chuỗi chứng minh hiện tại:

**Corruption → quality/freshness xấu → (RAG metrics chờ Integration) → Repair → quality/freshness về gần baseline.**

---

## 2. Bảng quality / freshness

| Tín hiệu | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Quality status | PASS | FAIL | PASS |
| Freshness status | PASS | FAIL | PASS |
| Tổng số dòng | 24 | 23 | 24 |
| Duplicate paper IDs | 0 | 1 | 0 |
| Empty / short summaries | 0 | 3 | 0 |
| Stale rows (> 180 ngày) | 0 | 1 | 0 |
| Stale rate | 0% | 4.35% | 0% |

Corrupted fail các check:

- `paper_id_unique` (thêm duplicate)
- `summary_min_length` (blank summary; duplicate làm tăng số dòng lỗi)
- `freshness_within_threshold` (một paper bị làm stale)

---

## 3. Corruption đã làm gì?

Theo `data/results/corruption_log.json`:

| Loại | Số lần | Ý nghĩa |
| --- | ---: | --- |
| Drop latest records | 2 | Giảm volume corpus |
| Blank summary | 2 | Làm mất nội dung embed |
| Inject summary noise | 1 | Nhiễu text |
| Truncate title | 1 | Metadata hỏng |
| Make publication stale | 1 | Phá freshness |
| Duplicate record | 1 | Phá uniqueness |

Baseline **không bị ghi đè** (`input_dataframe_mutated: false`).  
Dataset corrupted nằm riêng: `data/clean/papers_clean_corrupted.*`.

---

## 4. Repair — bằng chứng từ raw snapshot

Theo `data/results/repair_manifest.json` và `repair_evidence` trong corruption log:

| Kiểm chứng | Kết quả |
| --- | --- |
| Nguồn repair | `data/raw/crossref_records.json` |
| Method | `load_raw_records` → `build_clean_dataframe` |
| Cùng số dòng với baseline | true (24) |
| Cùng tập `paper_id` | true |
| Khớp title/summary/published | true (0 mismatch) |
| Repaired is clean | true |
| Gần baseline | true |

Artifact repaired: `data/clean/papers_clean_repaired.*`

---

## 5. Evaluation metrics (RAG)

| Metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Retrieval hit rate | n/a | n/a | n/a |
| Mean token F1 | n/a | n/a | n/a |
| Judge accuracy | n/a | n/a | n/a |
| Mean judge score | n/a | n/a | n/a |

**Chưa có** vì `phase1.py` / `corruption_flow.py` chưa chạy evaluate end-to-end.  
Khi Integration xong, regenerate `data/reports/corruption_report.md` với metrics thật.

---

## 6. File liên quan

| File | Vai trò |
| --- | --- |
| `data/quality/baseline_quality.json` | Quality baseline |
| `data/quality/corrupted_quality.json` | Quality corrupted |
| `data/quality/repaired_quality.json` | Quality repaired |
| `data/quality/freshness_report.json` | Freshness baseline |
| `data/quality/corrupted_freshness.json` | Freshness corrupted |
| `data/quality/repaired_freshness.json` | Freshness repaired |
| `data/results/corruption_log.json` | Corruption manifest + repair evidence |
| `data/results/repair_manifest.json` | Repair manifest độc lập |
| `data/reports/corruption_report.md` | Report do `reporting.py` sinh (lab) |
| `report/quality_checks.md` | Giải thích check/threshold |
