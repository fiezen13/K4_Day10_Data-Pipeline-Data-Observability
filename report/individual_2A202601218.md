# Member Role Report — Day 10: Data Pipeline & Data Observability

> Mỗi thành viên trong nhóm tự hoàn thành mẫu này để báo cáo đúng vai trò, phần việc và mức hiểu của mình. Không sao chép nguyên báo cáo chung hoặc báo cáo của thành viên khác. Thay nội dung trong dấu `[ ]` và xóa các dòng hướng dẫn không cần thiết trước khi nộp.

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Trần Văn Toàn          |
| MSSV               | 2A202601218                    |
| Khóa/Lớp         | K4             |
| Tên nhóm         | Zzz     |
| Vai trò chính    | Developer - Ingestion & Data Observability |
| Repository         | https://github.com/fiezen13/K4_Day10_Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-08-06          |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Crossref ingestion | src/ingestion/crossref.py : fetch_source_records, parse_crossref_payload, load_raw_records | Crossref REST API response (JSON) | data/raw/crossref_response.json (raw API response), data/raw/crossref_records.json (parsed records) | Hoàn thành |

Chỉ nhận ownership cho phần bạn trực tiếp thực hiện. Liên hệ rõ phần việc của bạn với đầu vào, đầu ra và các thành viên phụ thuộc vào phần đó.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Debug, test & integration | Team - sử dụng core.config và paths | Đảm bảo files được lưu ở data/raw và hàm load_raw_records có thể nạp lại records |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Triển khai Crossref fetch & parser | src/ingestion/crossref.py | data/raw/crossref_response.json, data/raw/crossref_records.json | Gọi fetch_source_records(settings) và kiểm tra file, ví dụ script smoke test (đã chạy) |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

- Artifact: data/raw/crossref_records.json — chứa 24 records (mỗi record theo PaperRecord schema). File data/raw/crossref_response.json chứa message.items trả về từ Crossref API (24 items cho request hiện tại).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

- Cần lấy metadata bài báo từ Crossref (DOI, tiêu đề, abstract, tác giả, subject, ngày xuất bản, URL, link PDF) và chuẩn hóa về một schema nội bộ để các bước tiếp theo của pipeline tiêu thụ (embeddings, indexing, QA).
- Cần lưu snapshot raw API response để audit/ghi nhận provenance và lưu bản parsed records để tái sử dụng, debug và làm reproducibility.

### Cách triển khai

- Viết hàm fetch_source_records(settings: Settings) để gọi endpoint Crossref REST API (https://api.crossref.org/works) với params:
  - query = settings.source_query
  - filter = settings.source_filter
  - rows = settings.max_results
- Kịch bản gọi thực hiện retry cho trạng thái 429/503 với exponential backoff (start=1s, tăng gấp đôi, tối đa 5 attempt).
- Lưu nguyên gốc JSON response vào settings.paths.raw_api_response (mặc định data/raw/crossref_response.json).
- Gọi parse_crossref_payload(payload) để biến message.items thành list[PaperRecord]. Parsing bao gồm:
  - paper_id: DOI (DOI field)
  - title: first element của title list
  - summary: abstract hoặc subtitle — strip HTML/XML tags (đã xử lý các thẻ <jats:...>) và normalize whitespace
  - authors: kết hợp given + family nếu có, thu thành list[str]
  - categories: từ trường subject (nếu có)
  - primary_category: categories[0] nếu có
  - published/updated: format từ date-parts (ví dụ "2026-6-15")
  - abs_url: trường URL
  - pdf_url: tìm trong item["link"] các entry có content-type chứa "pdf"
  - comment: note hoặc short-container-title (strip HTML)
- Lưu parsed records dưới dạng list of dict vào settings.paths.raw_records_json (mặc định data/raw/crossref_records.json) với json.dump(..., ensure_ascii=False) để giữ nguyên Unicode.
- Viết load_raw_records(path: Path) để đọc file parsed JSON và map thành list[PaperRecord].

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | Crossref API JSON: {"message": {"items": [ ... ]}} |
| Output                         | Parsed list of PaperRecord; Files: data/raw/crossref_response.json, data/raw/crossref_records.json |
| Module phụ thuộc             | core.config.Settings (paths, source_query, source_filter, max_results) |
| Module sử dụng output        | Các bước tiếp theo: embedding generation (src/embeddings), indexing (chroma dir), QA/eval modules |
| Điều kiện lỗi cần xử lý | HTTP errors (429/503), malformed items (missing title/DOI), HTML in abstract, list-types in fields |

### Cách xác minh

```bash
# Run a small smoke test (script used during development)
python - <<'PY'
from core.config import load_settings
from ingestion.crossref import fetch_source_records, load_raw_records
s = load_settings()
recs = fetch_source_records(s)
print('fetched', len(recs))
recs2 = load_raw_records(s.paths.raw_records_json)
print('loaded', len(recs2))
PY
```

- **Kết quả mong đợi:** fetched == loaded, files created at data/raw/*.json, parsed records non-empty.
- **Kết quả thực tế:** fetched=24, loaded=24 (với request mặc định trong settings hiện tại).
- **Artifact/log:** data/raw/crossref_response.json, data/raw/crossref_records.json

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Khi lấy dữ liệu external, phải cân bằng giữa số lượng trả về (rows), reproducibility và chi phí gọi API; đồng thời cần lưu raw response để audit.
- **Các phương án đã cân nhắc:**
  1. Không lưu raw API response (tiết kiệm disk) — nhưng sẽ mất khả năng audit và reproduce khi nguồn thay đổi.
  2. Lưu cả raw response và parsed records — tốn thêm dung lượng nhưng đảm bảo provenance và debug.
- **Phương án đã chọn:** Lưu cả raw API response và parsed records.
- **Lý do:** Cho phép tái xử lý (re-parse) khi schema thay đổi hoặc phát hiện lỗi, phục hồi trạng thái pipeline từ snapshot, và thu thập bằng chứng cho observability.
- **Bằng chứng quyết định phù hợp:** Files tồn tại trong data/raw sau khi chạy fetch_source_records; parsing đã được test bằng smoke test.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  - TypeError: expected string or bytes-like object, got 'list' khi gọi re.sub trên trường note/short-container-title nếu API trả về list.
  - UnicodeEncodeError khi in trực tiếp record chứa ký tự Unicode vào console trên Windows CP1252.
- **Lệnh hoặc bước tái hiện:** Chạy script smoke test -> exception trace trong logs (đã gặp khi parse một item cụ thể).
- **Nguyên nhân gốc:** API đôi lúc trả về field dưới dạng list thay vì string; hàm _clean_html ban đầu giả sử nhận được str và gọi re.sub trực tiếp. Ngoài ra, console encoding mặc định (cp1252) gây lỗi khi in trực tiếp chuỗi Unicode.
- **Cách xử lý:**
  - Cập nhật _clean_html để:
    - chấp nhận list: join các phần tử thành string trước khi strip tags;
    - đảm bảo tất cả input được cast sang str trước khi xử lý.
  - Khi in debug ra console dùng encoding-safe repr hoặc encode/decode (lưu files JSON với ensure_ascii=False để giữ Unicode).
- **Cách xác minh sau khi sửa:** Chạy lại smoke test — fetch thành công, no TypeError, files được tạo; xem sample output đã được ghi.
- **Điều học được:** Luôn kiểm tra loại dữ liệu trả về từ nguồn ngoài, và dùng json dump với ensure_ascii=False để lưu Unicode; tránh in trực tiếp Unicode non-ASCII lên console với encoding mặc định không hỗ trợ.

Nếu chưa xử lý xong:

- **Phạm vi bị ảnh hưởng:** parsing của Crossref items
- **Những gì đã loại trừ:** không phải lỗi network hay thiếu permission
- **Bước tiếp theo:** thêm unit test cho parse_crossref_payload với các edge-case (list fields, missing fields, HTML tags)

## 7. Hiểu biết về luồng end-to-end

Giải thích ngắn gọn bằng lời của bạn:

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
   - Crossref ingestion: gọi API -> lưu raw response -> parse thành PaperRecord -> export/clean -> tính embeddings (embedding model: sentence-transformers/all-MiniLM-L6-v2 theo core.config) -> lưu embeddings vào data/embeddings/papers_embeddings.json -> index vào Chroma (chroma_dir trong paths).
2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
   - Evaluation set (eval/test_set.json) chứa queries và expected document IDs hoặc passages. Khi thực hiện retrieval, đo retrieval_hit_rate dựa trên việc ground-truth IDs có xuất hiện trong top-K retrieved IDs.
3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
   - Freshness monitoring: tập trung vào timestamp / publication date / deposited date so sánh với freshness_threshold_days để báo tài liệu cũ hay mới.
   - Quality checks: gồm schema validation, missing abstract, corrupted text (HTML not stripped), duplicate DOIs, embedding validity. Freshness là một loại signal; quality checks rộng hơn và gồm nhiều loại signal khác.
4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
   - Để so sánh trực tiếp sự biến đổi của metrics khi dữ liệu bị nhiễm và khi được repair. Cùng test set đảm bảo fairness — khác biệt chỉ đến từ corruption/repair actions.
5. Repair được xem là thành công dựa trên artifact và metric nào?
   - Artifact: repaired_clean.json / repaired_embeddings.json được tạo và dùng để re-index.
   - Metrics: recovery of retrieval_hit_rate (tăng trở lại), tăng mean_judge_score / judge_accuracy, giảm mean_token_f1 regression. Thành công khi metrics về mức tương đương hoặc tốt hơn baseline tùy mục tiêu.

**Câu trả lời:**

Đã mô tả ở trên (tóm tắt quá trình ingestion → embedding → indexing → eval; dùng cùng test set để so sánh; repair đánh giá bằng recovery của retrieval/agent metrics).

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét |
| --- | --: | --: | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.9444 | 1.0000 | -0.0556 | +0.0556 (100%) | Nhiễu trong `text_for_embedding` (noise + truncate title) làm giảm nhẹ độ chính xác semantic search |
| `mean_token_f1` | 1.0000 | 0.7627 | 1.0000 | -0.2373 | +0.2373 (100%) | Bị ảnh hưởng nặng nhất — blank summary và title bị cắt khiến agent không trích được câu trả lời đúng |
| `judge_accuracy` | 0.9722 | 0.7500 | 0.9722 | -0.2222 | +0.2222 (100%) | LLM judge (`gpt-4o-mini`) đánh giá thêm ~22% câu trả lời sai lệch khi dữ liệu nguồn bị hỏng |
| `mean_judge_score` | 4.8889 | 4.1667 | 4.8889 | -0.7222 | +0.7222 (100%) | Giảm gần 1 điểm trên thang 5 điểm |
| Quality checks| PASS (7/7) | FAIL (5/7) | PASS (7/7) | 2 check FAIL (`paper_id_unique`, `summary_min_length`) | Phục hồi hoàn toàn | Duplicate rows và blank summary là nguyên nhân trực tiếp gây FAIL |
| Freshness status | Fresh (0% stale) | Fresh (20.83% stale, dưới ngưỡng 50%) | Fresh (0% stale) | Stale rate tăng nhưng chưa vượt ngưỡng cảnh báo | Phục hồi hoàn toàn | Stale date corruption làm tăng stale rate rõ rệt dù chưa đủ để đổi trạng thái tổng thể |

### Kết luận từ số liệu

Hoàn thành hai chuỗi nguyên nhân–bằng chứng sau:

1. Crossref items có HTML trong abstract (ví dụ <jats:p>) → parsing ban đầu lỗi TypeError hoặc giữ nguyên tag → giảm quality (downstream embedding chất lượng kém) → retrieval/agent metrics giảm.
2. Thực hiện cleaning (strip HTML, normalize) và lưu parsed records → embeddings tính trên văn bản sạch → retrieval_hit_rate/mean_judge_score có khả năng phục hồi.

Corruption nào ảnh hưởng rõ nhất và vì sao?

- HTML/XML tags trong abstract và trường list/string không nhất quán gây parsing errors hoặc văn bản không sạch, ảnh hưởng trực tiếp tới embedding quality.

Kết quả nào khác với kỳ vọng ban đầu?

- API response trong trường hợp này trả 24 items vì code request rows=24 (settings.max_results default). Một người dùng xem trực tiếp https://api.crossref.org/works (không có params) sẽ thấy 20 items — khác biệt do rows default của API vs tham số rows gửi từ code.

Hai kết luận nhân quả được hỗ trợ bởi artifact:

1. **Blank summary + noise injection** (`data/results/corruption_log.json`, tác động 6 record) → `summary_min_length` check chuyển PASS→FAIL và `text_for_embedding` bị nhiễu (`data/quality/corrupted_quality.json`) → `mean_token_f1` giảm mạnh nhất trong 4 metrics (1.0 → 0.7627, `data/results/corrupted_metrics.json`), vì agent trích câu trả lời trực tiếp từ `summary` trong metadata retrieval.
2. **Repair action** (`build_clean_dataframe` chạy lại trên `data/raw/crossref_records.json`) → toàn bộ 7/7 quality checks trở lại PASS và freshness trở lại 0% stale (`data/quality/repaired_quality.json`, `freshness_report_repaired.json`) → cả 4 agent metrics phục hồi chính xác về giá trị baseline (delta = 0.0000 trên `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`), chứng minh repair từ raw snapshot khôi phục hoàn toàn chất lượng hệ thống.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Tính nhất quán của schema external không được đảm bảo — cần defensive parsing (kiểm tra kiểu, join list, strip HTML).
2. Lưu raw API snapshot là quan trọng cho observability và reproducibility (provenance).
3. Việc log, retry/backoff và lưu artifacts (raw + parsed) giúp phát hiện nhanh issues liên quan đến data quality.

### Nếu có thêm thời gian

- Thêm unit tests cho parse_crossref_payload để cover edge-case: list fields, missing fields, HTML tags, missing DOI/title.
- Thêm một CLI flag hoặc parameter cho fetch_source_records để override rows/filter mà không cần thay đổi core.config.
- Thêm basic schema validation (pydantic/dataclass validation) trước khi export sang embeddings.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Trần Văn Toàn
**Ngày xác nhận:** 2026-08-06
