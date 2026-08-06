# Giải thích các check chất lượng dữ liệu

Tài liệu này giải thích **các check và ngưỡng** dùng trong phần observability của lab.
Cùng một bộ check được áp dụng cho cả ba trạng thái: baseline → corrupted → repaired.

---

## Contract của lab (nên nhớ)

Trong lab này, dữ liệu “đạt” khi:

1. Mỗi paper có `summary` dài tối thiểu **100 ký tự**.
2. Mỗi paper có `age_days` và **không âm**.
3. Mọi paper nằm trong cửa sổ **180 ngày** (`age_days <= 180`).
4. Chỉ cần **1 paper stale** là freshness/quality fail (`stale_rows == 0`).

> Đây là rule để dễ demo corruption, không phải chuẩn bắt buộc cho mọi hệ thống RAG ngoài đời thực.

---

## Bảng check chính

| Check | Ngưỡng | Dimension | Phát hiện lỗi gì? | Fail thì ảnh hưởng RAG ra sao? | Khi fail nên làm gì? |
| --- | --- | --- | --- | --- | --- |
| `row_count_positive` | > 0 dòng | Volume | Dataset bị xóa hết / rỗng | Không còn gì để retrieve | Dừng pipeline |
| `paper_id_not_null` | 0 missing | Completeness | Mất `paper_id` | Không gắn ground truth, không lookup theo ID | Reject record/batch |
| `paper_id_unique` | 0 duplicate | Uniqueness | Thêm dòng trùng | Index bị nhiễu, retrieval kém ổn định | Dedupe / quarantine |
| `title_not_null` | 0 missing | Completeness | Title bị xóa/cắt | Khó tìm theo title, context kém | Quarantine |
| `summary_min_length` | ≥ 100 ký tự | Validity | Summary rỗng hoặc quá ngắn | Embedding yếu → hit rate giảm | Warn hoặc reject |
| `text_for_embedding_not_empty` | 0 empty | Completeness | Mất text dùng để embed | Record không vào semantic search | Reject record |
| `age_days_present` | 0 missing | Completeness | Thiếu `age_days` | Không đo được freshness | Warn / fail |
| `age_days_non_negative` | ≥ 0 | Validity | `age_days` âm (ngày lỗi) | Logic freshness sai | Fail / quarantine |
| `freshness_within_threshold` | ≤ 180 ngày | Timeliness | Làm stale date | Corpus cũ, câu trả lời lỗi thời | Fail theo lab contract |

---

## Các số liệu phụ (để đọc report)

| Metric | Cách hiểu ngắn gọn |
| --- | --- |
| `empty_summaries` | Summary trống hoàn toàn |
| `non_empty_short_summaries` | Có chữ nhưng ngắn hơn 100 ký tự |
| `short_summaries` | Tổng số summary không đạt (= empty + short) |
| `*_rate` | Tỷ lệ lỗi theo số dòng; hữu ích khi so sánh dataset khác size |
| `stale_rows` / `stale_rate` | Bao nhiêu paper ngoài cửa sổ 180 ngày |
| `missing_published` | Không đọc được ngày `published` |
| `missing_age_days` | Thiếu `age_days` |
| `mean_age_days` / `max_age_days` | Tuổi trung bình / lớn nhất của corpus |

**Lưu ý đọc số:**  
`empty_summaries` đã nằm trong `short_summaries`. Không cộng hai số này lại với nhau.

---

## File artifact theo từng trạng thái

| Trạng thái | Quality | Freshness |
| --- | --- | --- |
| Baseline | `data/quality/baseline_quality.json` | `data/quality/freshness_report.json` |
| Corrupted | `data/quality/corrupted_quality.json` | `data/quality/corrupted_freshness.json` |
| Repaired | `data/quality/repaired_quality.json` | `data/quality/repaired_freshness.json` |

Báo cáo Markdown:

| Báo cáo | File | Khi nào có |
| --- | --- | --- |
| Baseline | `data/reports/phase1_report.md` | Sau quality/freshness baseline |
| So sánh 3 trạng thái | `data/reports/corruption_report.md` | Sau khi có đủ corrupted + repaired + metrics |

Bản giải thích cho người đọc (file này): `report/quality_checks.md`

---

## Kết quả đã chạy (3 trạng thái)

| Trạng thái | Rows | Quality | Freshness | Ghi chú |
| --- | ---: | --- | --- | --- |
| Baseline | 24 | PASS | PASS | Mốc so sánh |
| Corrupted | 23 | FAIL | FAIL | Fail: duplicate, short summary, stale |
| Repaired | 24 | PASS | PASS | Rebuild từ raw; khớp baseline |

File đã có:

- `data/quality/baseline_quality.json`
- `data/quality/corrupted_quality.json`
- `data/quality/repaired_quality.json`
- `data/quality/freshness_report.json`
- `data/quality/corrupted_freshness.json`
- `data/quality/repaired_freshness.json`
- `data/results/corruption_log.json`
- `data/results/repair_manifest.json`
- `data/reports/phase1_report.md`
- `data/reports/corruption_report.md`
- `data/reports/corruption_comparison.md`
- `data/reports/comparison.json`

**Chưa có:** RAG metrics 3 trạng thái (cần Integration chạy evaluate).
