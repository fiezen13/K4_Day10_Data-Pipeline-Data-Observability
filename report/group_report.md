# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K4 |
| Tên nhóm | K4-Day10-Data-Pipeline-Data-Observability |
| Repository | K4_Day10_Data-Pipeline-Data-Observability (branch `main`) |
| Ngày hoàn thành | 2026-08-06 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Trần Văn Toàn | 2A202601218 | Thành viên 1 — Source Ingestion | `src/ingestion/crossref.py` |
| 2 | Trần Hoàng Khôi | 2A202601778 | Thành viên 2 — Cleaning & Test Set | `src/ingestion/cleaning.py`, `src/evaluation/testset.py` |
| 3 | Trần Minh Hiển | 2A202601812 | Thành viên 3 — Observability & Reporting | `src/observability/quality.py`, `src/observability/reporting.py` |
| 4 | Phạm Hải Yến | 2A202601152 | Thành viên 4 — Corruption & Repair | `src/ingestion/corruption.py` |
| 5 | Trương Minh Tâm | 2A202602005 | Thành viên 5 — Integration & Comparison | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` |

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành toàn bộ 2 pha của bài lab: baseline pipeline chạy trên dữ liệu sạch lấy từ Crossref API, và corruption flow đo lường tác động của dữ liệu lỗi lên RAG agent rồi phục hồi từ raw snapshot. Baseline pipeline tạo đủ artifact ở cả 6 thư mục (`data/raw`, `data/clean`, `data/embeddings`, `data/eval`, `data/results`, `data/quality`, `data/reports`) với 24 bài báo khoa học được fetch, làm sạch và index thành công, đạt `retrieval_hit_rate = 1.0` và `judge_accuracy = 0.9722` (LLM judge thật, `gpt-4o-mini`) trên bộ 36 câu hỏi đánh giá.

Corruption flow áp dụng 6 kịch bản lỗi có kiểm soát (xóa bài mới nhất, xóa summary, thêm nhiễu, cắt ngắn title, làm cũ ngày xuất bản, tạo bản ghi trùng lặp), được thiết kế để chủ động nhắm vào các tài liệu nằm trong `ground_truth_doc_ids` của bộ test set đóng băng — 6/12 tài liệu mục tiêu bị tác động trực tiếp. Kết quả: `retrieval_hit_rate` giảm từ 1.0 xuống 0.944, `judge_accuracy` giảm từ 0.9722 xuống 0.75, và data quality chuyển từ PASS sang FAIL (2 check thất bại: `paper_id_unique`, `summary_min_length`). Sau khi repair từ raw snapshot (không sửa tay), toàn bộ metrics phục hồi chính xác về mức baseline (delta = 0 trên mọi chỉ số).

Giới hạn còn lại: Crossref API không trả về trường `subject` cho các bài báo trong tập dữ liệu này, nên bộ test set không có câu hỏi loại `categories`; đánh giá `ragas` chưa được bật (mặc định `RUN_RAGAS` tắt để tiết kiệm thời gian chạy).

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API
    -> raw response/raw records (data/raw/)
    -> cleaning và data modeling (data/clean/)
    -> embedding + ChromaDB index (data/embeddings/, data/chroma/)
    -> evaluation baseline (data/eval/, data/results/baseline_*)
    -> quality/freshness reports (data/quality/)
    -> corruption (data/clean/papers_corrupted.*, data/results/corruption_log.json)
    -> re-index và re-evaluate (data/results/corrupted_*)
    -> repair từ dữ liệu nguồn (data/clean/papers_clean_repaired.*)
    -> re-evaluate repaired (data/results/repaired_*)
    -> comparison report (data/reports/corruption_report.md)
```

### Trách nhiệm của từng khối

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref REST API | Fetch với retry/backoff (429/503/timeout), parse JATS-XML abstract, chuẩn hóa DOI thành `paper_id` | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Trần Văn Toàn (2A202601218) |
| Cleaning | Raw `PaperRecord` list | Lọc record thiếu title/summary ngắn (<100 ký tự), chuẩn hóa authors/categories, tính `age_days`, dựng `text_for_embedding` | `data/clean/papers_clean.csv`, `.json` | Trần Hoàng Khôi (2A202601778) |
| Embedding/index | Cleaned dataframe | `sentence-transformers/all-MiniLM-L6-v2` (384 chiều) + ChromaDB persistent collection | `data/embeddings/papers_embeddings.json`, `data/chroma/` | Starter code (không chỉnh sửa logic lõi) |
| Evaluation | Cleaned dataframe | Sinh 36 câu hỏi (summary/authors/date) với `ground_truth_doc_ids`, đóng băng dùng chung cho 3 trạng thái | `data/eval/test_set.json` | Trần Hoàng Khôi (2A202601778) |
| Observability | Cleaned/corrupted/repaired dataframe | 7 quality checks (row count, null, uniqueness, độ dài summary, freshness) + freshness report | `data/quality/*_quality.json`, `data/quality/freshness_report*.json` | Trần Minh Hiển (2A202601812) |
| Corruption/repair | Baseline clean dataframe + raw records | 6 kịch bản corrupt có nhắm mục tiêu vào test set; repair bằng cách chạy lại `build_clean_dataframe` từ raw snapshot | `data/clean/papers_corrupted.*`, `data/results/corruption_log.json`, `data/clean/papers_clean_repaired.*` | Phạm Hải Yến (2A202601152) |
| Orchestration | Toàn bộ module trên | Ghép pipeline theo đúng thứ tự Raw → Clean → Quality → Index → Evaluate → Report; baseline chạy trước, corruption chạy sau; path/collection riêng cho 3 trạng thái | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` | Trương Minh Tâm (2A202602005) |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
| --- | --- |
| `LLM_PROVIDER` | `openai` |
| `LLM_MODEL` | `gpt-4o-mini` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 (giới hạn `max_results=24`) |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày |
| Random seed (corruption) | 42 |

Không dán nội dung API key hoặc file `.env` vào báo cáo.

### Lệnh cài đặt

```bash
uv sync
```

Hoặc:

```bash
python -m pip install -e .
```

### Lệnh chạy

Baseline:

```bash
uv run python script/run_phase1.py
```

Corruption flow:

```bash
uv run python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh | Trạng thái | Thời điểm chạy gần nhất | Bằng chứng |
| --- | --- | --- | --- |
| Baseline pipeline | Thành công | 2026-08-06 09:55 UTC | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow | Thành công | 2026-08-06 09:58 UTC | `data/results/corrupted_metrics.json`, `data/results/repaired_metrics.json`, `data/reports/corruption_report.md` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | Crossref REST API — `https://api.crossref.org/works` |
| Query/filter | `query=agentic retrieval augmented generation large language model`, `filter=from-pub-date:2026-02-07,has-abstract:true` |
| Thời điểm lấy dữ liệu | 2026-08-06 |
| Số record nhận được | 24 raw records → 24 clean rows (không record nào bị loại sau khi nâng ngưỡng summary lên 100 ký tự) |
| Cơ chế retry/backoff | Retry tối đa 5 lần với exponential backoff (1.5s × 2^n) cho HTTP 429/500/502/503/504 và lỗi timeout/connection |

### Raw và clean schema

| Trường | Kiểu dữ liệu | Bắt buộc? | Ý nghĩa | Xử lý khi thiếu/sai |
| --- | --- | --- | --- | --- |
| `paper_id` | string | Có | DOI chuẩn hóa (lowercase), fallback về URL nếu không có DOI | Record bị loại nếu rỗng |
| `title` | string | Có | Tiêu đề bài báo, đã strip JATS/XML tags | Record bị loại nếu < 3 ký tự |
| `summary` | string | Có | Abstract đã strip tag, chuẩn hóa whitespace | Record bị loại nếu < 100 ký tự |
| `authors_joined` | string | Không | Danh sách tác giả nối bằng dấu phẩy | Rỗng nếu Crossref không trả về author |
| `categories_joined` | string | Không | Danh sách subject nối bằng dấu phẩy | Rỗng nếu Crossref không trả về `subject` (xảy ra với toàn bộ 24 record trong lần fetch này) |
| `published` | string (YYYY-MM-DD) | Có | Ngày xuất bản chuẩn hóa | Rỗng nếu Crossref thiếu ngày |
| `age_days` | int | Có | Số ngày từ `published` đến thời điểm chạy pipeline | `None` nếu không parse được ngày |
| `text_for_embedding` | string | Có | `Title: {title} | Authors: {authors_joined} | Summary: {summary}` | Luôn được rebuild sau mọi bước cleaning/corruption |

### Quy tắc cleaning

| Quy tắc | Quality dimension liên quan | Số record bị tác động | Cách xác minh |
| --- | --- | --- | --- |
| Loại record thiếu `paper_id` hoặc title < 3 ký tự | Completeness | 0/24 (không có record nào trong lần fetch này) | `data/quality/baseline_quality.json` — check `paper_id_not_null`, `title_not_null` PASS |
| Loại record có `summary` < 100 ký tự | Completeness/Validity | 0/24 | `data/quality/baseline_quality.json` — check `summary_min_length` PASS |
| Drop duplicate theo `paper_id` | Uniqueness | 0/24 | `data/quality/baseline_quality.json` — check `paper_id_unique` PASS (`duplicate_count=0`) |

Cách tạo `text_for_embedding`: ghép `title`, `authors_joined` và `summary` (đã strip tag XML/HTML) theo format cố định `Title: [title] | Authors: [authors] | Summary: [summary]` để nhất quán giữa baseline, corrupted, repaired.

Cách tạo `paper_id`: ưu tiên DOI (chuẩn hóa lowercase) từ trường `DOI` của Crossref; nếu thiếu DOI thì fallback về `URL` của record. `paper_id` không bị thay đổi qua các bước cleaning/corruption/repair, đảm bảo `ground_truth_doc_ids` trong test set luôn tham chiếu đúng.

Cách tính `age_days`: `age_days = (run_date - published_date).days`, dùng `run_date` là thời điểm pipeline baseline/repair thực thi.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 36 |
| Các `question_type` | `summary` (12), `authors` (12), `date` (12) — không có `categories` vì Crossref không trả `subject` cho tập dữ liệu này |
| Ground-truth document ID | `ground_truth_doc_ids = [paper_id]` — 1 tài liệu nguồn cho mỗi câu hỏi, lấy trực tiếp từ `paper_id` đã chuẩn hóa |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` (384 chiều) |
| Vector store/collection | ChromaDB, collection riêng cho mỗi trạng thái: `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k` | 4 |
| LLM provider/model | `openai` / `gpt-4o-mini` |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` — sinh một lần ở bước baseline, không tái tạo lại cho corrupted/repaired |

Test set được giữ nguyên khi đánh giá cả ba trạng thái vì mục tiêu là đo tác động của **thay đổi dữ liệu** lên chất lượng RAG, không phải đo tác động của việc thay đổi bộ câu hỏi. Nếu regenerate test set cho mỗi trạng thái, sự khác biệt về câu hỏi/ground truth sẽ trộn lẫn với tác động của corruption, khiến kết quả so sánh không còn ý nghĩa nhân quả.

## 7. Kết quả baseline

### Artifact checklist

| Artifact | Đường dẫn thực tế | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw response/records | `data/raw/crossref_response.json`, `crossref_records.json` | Có | 24 records |
| Cleaned dataset | `data/clean/papers_clean.csv`, `.json` | Có | 24 rows |
| Embedding manifest/index | `data/embeddings/papers_embeddings.json`, `data/chroma/` | Có | Collection `papers-baseline` |
| Evaluation set | `data/eval/test_set.json` | Có | 36 câu hỏi |
| Baseline metrics | `data/results/baseline_metrics.json`, `baseline_answers.json` | Có | — |
| Quality/freshness | `data/quality/baseline_quality.json`, `freshness_report.json` | Có | Tất cả check PASS |
| Baseline report | `data/reports/phase1_report.md` | Có | — |

### Baseline metrics

| Metric | Giá trị | Diễn giải |
| --- | --: | --- |
| `retrieval_hit_rate` | 1.0000 | 100% câu hỏi tìm đúng tài liệu nguồn trong top-4 kết quả retrieval |
| `mean_token_f1` | 1.0000 | Câu trả lời của agent khớp hoàn toàn (theo token) với ground truth trên toàn bộ 36 câu |
| `judge_accuracy` | 0.9722 | LLM judge (`gpt-4o-mini`) đánh giá 35/36 câu trả lời đúng về mặt nội dung |
| `mean_judge_score` | 4.8889 | Điểm trung bình trên thang 1–5 |
| Ragas | Bỏ qua (`RUN_RAGAS` không bật) | Không chạy để tiết kiệm thời gian; có thể bật bằng `RUN_RAGAS=1` |

## 8. Data quality và freshness

### Quality checks

| Check | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline | Bằng chứng |
| --- | --- | --- | --- | --- |
| `row_count_positive` | Completeness | row_count > 0 | PASS (24) | `data/quality/baseline_quality.json` |
| `paper_id_not_null` | Completeness | 0 null/rỗng | PASS (0) | `data/quality/baseline_quality.json` |
| `paper_id_unique` | Uniqueness | 0 duplicate | PASS (0) | `data/quality/baseline_quality.json` |
| `title_not_null` | Completeness | 0 null/rỗng | PASS (0) | `data/quality/baseline_quality.json` |
| `summary_min_length` | Validity | 0 record < 100 ký tự | PASS (0) | `data/quality/baseline_quality.json` |
| `text_for_embedding_not_empty` | Completeness | 0 rỗng | PASS (0) | `data/quality/baseline_quality.json` |
| `freshness_within_threshold` | Timeliness | stale_rate < 50% | PASS (0.00%) | `data/quality/baseline_quality.json` |

### Freshness

| Thuộc tính | Giá trị |
| --- | --- |
| Freshness được đo tại | `data/clean/papers_clean.json` (cleaned dataset) |
| Timestamp mới nhất | `2026-08-01` |
| Ngưỡng freshness | 180 ngày |
| Trạng thái baseline | Fresh |
| Lý do | Bài báo cũ nhất trong tập (`2026-02-12`) vẫn cách thời điểm chạy pipeline dưới 180 ngày; 0/24 record bị đánh dấu stale |

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair |
| --- | --- | --: | --- | --- | --- |
| Drop latest | Xóa 2 bài xuất bản gần nhất nhất (loại trừ tài liệu nằm trong test set để tránh miss tuyệt đối) | 2 | `row_count` giảm | Row count giữ 24 vì có 2 duplicate bù lại | Repair từ raw khôi phục đúng 24 record gốc |
| Blank summary | Gán `summary = ""` trên các dòng ưu tiên nằm trong test set | 3 | `summary_min_length` FAIL | `summary_min_length`: FAIL, 5 record dưới 100 ký tự (gồm cả bản ghi bị noise) | `build_clean_dataframe` từ raw phục hồi summary gốc |
| Add noise | Chèn chuỗi rác `asdkj##garbled$$1234...` vào cuối summary | 3 | `text_for_embedding` bị nhiễu, ảnh hưởng retrieval | Retrieval hit rate giảm 1.0 → 0.944 | Repair rebuild `text_for_embedding` từ raw summary sạch |
| Truncate title | Cắt title còn 12 ký tự đầu | 3 | Title mất ngữ nghĩa, ảnh hưởng exact-title lookup và semantic search | `mean_token_f1` giảm 1.0 → 0.763 | Repair khôi phục title đầy đủ từ raw |
| Stale date | Đẩy `published` lùi 5 năm | 3 | `freshness_within_threshold` bị ảnh hưởng | `stale_rows`: 0 → 5 (20.83%) | Repair tính lại `published`/`age_days` từ raw |
| Duplicate rows | Nhân đôi 2 dòng, giữ nguyên `paper_id` | 2 | `paper_id_unique` FAIL | `paper_id_unique`: FAIL, `duplicate_count=2` | Repair build lại từ raw, `drop_duplicates` theo `paper_id` loại bỏ hoàn toàn |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log ghi đầy đủ paper_id bị tác động theo từng loại corruption, cùng `original_row_count`/`corrupted_row_count` và timestamp sinh log. Corruption được thiết kế **chủ động nhắm mục tiêu** vào các `paper_id` nằm trong `ground_truth_doc_ids` của test set (6/12 tài liệu mục tiêu bị tác động trực tiếp), thay vì chọn ngẫu nhiên toàn bộ dataset — đảm bảo tác động luôn đo được trên metrics thay vì phụ thuộc may rủi.

Repair đảm bảo phục hồi từ nguồn đáng tin cậy: `corruption_flow.py` không sửa trực tiếp `corrupted_df`, mà đọc lại `data/raw/crossref_records.json` (raw snapshot đã lưu từ bước ingestion, không đổi trong suốt quá trình) và chạy lại đúng hàm `build_clean_dataframe` dùng cho baseline. Vì repair đi từ raw thay vì "sửa" bản corrupted, mọi trường bị corrupt (summary, title, published, duplicate) đều được tái tạo từ dữ liệu gốc chứ không phải bị che giấu hay chỉnh tay.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét |
| --- | --: | --: | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.9444 | 1.0000 | -0.0556 | +0.0556 (100%) | Nhiễu trong `text_for_embedding` (noise + truncate title) làm giảm nhẹ độ chính xác semantic search |
| `mean_token_f1` | 1.0000 | 0.7627 | 1.0000 | -0.2373 | +0.2373 (100%) | Bị ảnh hưởng nặng nhất — blank summary và title bị cắt khiến agent không trích được câu trả lời đúng |
| `judge_accuracy` | 0.9722 | 0.7500 | 0.9722 | -0.2222 | +0.2222 (100%) | LLM judge (`gpt-4o-mini`) đánh giá thêm ~22% câu trả lời sai lệch khi dữ liệu nguồn bị hỏng |
| `mean_judge_score` | 4.8889 | 4.1667 | 4.8889 | -0.7222 | +0.7222 (100%) | Giảm gần 1 điểm trên thang 5 điểm |
| Quality checks pass/fail | PASS (7/7) | FAIL (5/7) | PASS (7/7) | 2 check FAIL (`paper_id_unique`, `summary_min_length`) | Phục hồi hoàn toàn | Duplicate rows và blank summary là nguyên nhân trực tiếp gây FAIL |
| Freshness status | Fresh (0% stale) | Fresh (20.83% stale, dưới ngưỡng 50%) | Fresh (0% stale) | Stale rate tăng nhưng chưa vượt ngưỡng cảnh báo | Phục hồi hoàn toàn | Stale date corruption làm tăng stale rate rõ rệt dù chưa đủ để đổi trạng thái tổng thể |

Hai kết luận nhân quả được hỗ trợ bởi artifact:

1. **Blank summary + noise injection** (`data/results/corruption_log.json`, tác động 6 record) → `summary_min_length` check chuyển PASS→FAIL và `text_for_embedding` bị nhiễu (`data/quality/corrupted_quality.json`) → `mean_token_f1` giảm mạnh nhất trong 4 metrics (1.0 → 0.7627, `data/results/corrupted_metrics.json`), vì agent trích câu trả lời trực tiếp từ `summary` trong metadata retrieval.
2. **Repair action** (`build_clean_dataframe` chạy lại trên `data/raw/crossref_records.json`) → toàn bộ 7/7 quality checks trở lại PASS và freshness trở lại 0% stale (`data/quality/repaired_quality.json`, `freshness_report_repaired.json`) → cả 4 agent metrics phục hồi chính xác về giá trị baseline (delta = 0.0000 trên `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`), chứng minh repair từ raw snapshot khôi phục hoàn toàn chất lượng hệ thống.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Lần chạy corruption flow đầu tiên cho thấy `retrieval_hit_rate` không đổi so với baseline dù đã áp dụng 6 kịch bản corruption.
- **Nguyên nhân:** `corrupt_clean_dataframe` chọn dòng để corrupt hoàn toàn ngẫu nhiên trên toàn bộ dataframe, không kiểm tra các dòng đó có nằm trong `ground_truth_doc_ids` của test set đóng băng hay không — corruption vô tình chỉ rơi vào các tài liệu không bao giờ được hỏi tới.
- **Cách xử lý:** Sửa `corrupt_clean_dataframe` để nhận thêm tham số `target_paper_ids` (tập hợp toàn bộ `ground_truth_doc_ids` từ `test_set.json`), ưu tiên các paper_id này khi chọn nạn nhân cho mỗi loại corruption (trừ "drop latest" — loại trừ target để không tạo miss tuyệt đối làm mất khả năng đo mức suy giảm dần).
- **Cách xác minh:** So khớp `data/results/corruption_log.json` với `ground_truth_doc_ids` trong `data/eval/test_set.json` — xác nhận 6/12 tài liệu mục tiêu bị tác động trực tiếp; chạy lại `script/run_corruption_flow.py` cho thấy metrics sụt giảm rõ rệt và có ý nghĩa thống kê so với lần chạy đầu.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| Crossref không trả `subject` cho tập dữ liệu này | Test set thiếu loại câu hỏi `categories` | Đổi query/filter để ưu tiên các publisher có gắn subject taxonomy, hoặc bổ sung fallback lấy category từ `container-title` |
| `RUN_RAGAS` mặc định tắt | Chưa có chỉ số Ragas (answer_relevancy, faithfulness...) để đối chiếu | Bật `RUN_RAGAS=1` trong lần chạy cuối trước khi nộp, đo thời gian chạy thêm để cân nhắc |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
