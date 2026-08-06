# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Trương Minh Tâm |
| MSSV | 2A202602005 |
| Khóa/Lớp | K4 |
| Tên nhóm | K4-Day10-Data-Pipeline-Data-Observability |
| Vai trò chính | Thành viên 5 — Integration & Comparison |
| Repository | K4_Day10_Data-Pipeline-Data-Observability|
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Baseline pipeline orchestration | `src/pipelines/phase1.py` (`main`) | `Settings` từ `core.config.load_settings` | `data/clean/`, `data/embeddings/`, `data/eval/`, `data/results/baseline_*`, `data/quality/baseline_*`, `data/reports/phase1_report.md` | Hoàn thành |
| Corruption–repair pipeline orchestration | `src/pipelines/corruption_flow.py` (`main`) | Baseline clean dataset (`data/clean/papers_clean.json`) + raw snapshot (`data/raw/crossref_records.json`) | `data/clean/papers_corrupted.*`, `data/clean/papers_clean_repaired.*`, `data/results/corrupted_*`, `data/results/repaired_*`, `data/reports/corruption_report.md` | Hoàn thành |
| Path/collection contract cho 3 trạng thái | `src/core/config.py` (`Paths`) | — | Thêm `corrupted_freshness_report`, `repaired_freshness_report` để tránh 3 trạng thái ghi đè lẫn nhau lên cùng một file freshness | Hoàn thành |

Ngoài phạm vi tích hợp chính thức, tôi đã hoàn thiện các stub còn lại (`crossref.py`, `cleaning.py`, `testset.py`, `quality.py`, `reporting.py`, `corruption.py`) để có dữ liệu thật chạy qua toàn bộ pipeline, phục vụ việc kiểm thử tích hợp và tạo artifact cho báo cáo chung.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Hoàn thiện `src/ingestion/crossref.py` (fetch + parse + retry/backoff) | Hỗ trợ vai trò Thành viên 1 (Trần Văn Toàn) | 24 raw records fetch thành công, lưu tại `data/raw/` |
| Hoàn thiện `src/ingestion/cleaning.py`, `src/evaluation/testset.py` | Hỗ trợ vai trò Thành viên 2 (Trần Hoàng Khôi) | 24 clean rows, 36 câu hỏi test set đóng băng tại `data/eval/test_set.json` |
| Hoàn thiện `src/observability/quality.py`, `src/observability/reporting.py` | Hỗ trợ vai trò Thành viên 3 (Trần Minh Hiển) | 7 quality checks + freshness report cho cả 3 trạng thái, 2 báo cáo markdown |
| Hoàn thiện `src/ingestion/corruption.py`, sửa bug đảm bảo corruption nhắm trúng test set | Hỗ trợ vai trò Thành viên 4 (Phạm Hải Yến) | 6 kịch bản corruption có kiểm soát, 6/12 tài liệu mục tiêu trong test set bị tác động trực tiếp |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Ghép baseline pipeline: fetch/load → clean → index → test set → evaluate → quality → freshness → report | `src/pipelines/phase1.py` | `data/results/baseline_metrics.json` (`retrieval_hit_rate=1.0`, `judge_accuracy=0.9722`) | `uv run python script/run_phase1.py` |
| Ghép corruption flow: đọc baseline → corrupt → re-index → evaluate → quality/freshness → repair từ raw → re-evaluate → comparison report | `src/pipelines/corruption_flow.py` | `data/results/corrupted_metrics.json`, `repaired_metrics.json`, `data/reports/corruption_report.md` | `uv run python script/run_corruption_flow.py` |
| Đảm bảo baseline chạy trước và có đủ artifact trước khi cho phép corruption flow chạy | `corruption_flow.py` — kiểm tra `paths.clean_json.exists()` và `paths.baseline_metrics.exists()` trước khi tiếp tục | Corruption flow raise `RuntimeError` rõ ràng nếu baseline chưa chạy | Chạy `run_corruption_flow.py` khi chưa có baseline → lỗi đúng như thiết kế |
| Tách path/collection riêng cho baseline/corrupted/repaired, không ghi đè | `src/core/config.py` (`Paths`), `src/retrieval/index.py` (`_derive_collection_name`) | 3 ChromaDB collection riêng: `papers-baseline`, `papers-corrupted`, `papers-repaired`; 3 file freshness riêng | Kiểm tra `data/chroma/` có nhiều collection, `data/quality/freshness_report*.json` có 3 file riêng biệt |

Output cụ thể: `data/reports/corruption_report.md` — báo cáo so sánh 3 cột (Baseline/Corrupted/Repaired) với bảng metrics đầy đủ, do `corruption_flow.py` gọi `generate_corruption_report` với đúng 3 bộ số liệu đã evaluate.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần Integration & Comparison chịu trách nhiệm biến các module rời rạc (ingestion, cleaning, embedding, evaluation, observability, corruption) thành hai pipeline chạy được từ đầu đến cuối, đúng thứ tự phụ thuộc, và tạo ra bằng chứng định lượng cho thấy dữ liệu lỗi làm giảm chất lượng RAG agent còn repair thì khôi phục lại được.

### Cách triển khai

`phase1.py` gọi tuần tự: `fetch_source_records`/`load_raw_records` (tùy `settings.refresh_source`) → `build_clean_dataframe` → ghi CSV/JSON → `LocalEmbeddingIndex.build` (build Chroma collection `papers-baseline`) → `build_test_set`/đọc test set có sẵn (tùy `settings.refresh_test_set`) → `evaluate_pipeline` → `run_data_quality_checks` + `build_freshness_report` → `generate_phase1_report`.

`corruption_flow.py` chặn sớm nếu chưa có baseline artifact, sau đó: đọc lại `clean_json` của baseline (không đọc raw) → đọc `ground_truth_doc_ids` từ test set đã đóng băng để tính `target_paper_ids` → gọi `corrupt_clean_dataframe` với `target_paper_ids` để đảm bảo corruption có tác động đo được → build index/collection `papers-corrupted` → evaluate trên **cùng** test set → quality/freshness → repair bằng cách gọi lại `build_clean_dataframe` trên `raw_records_json` (không phải trên bản đã corrupt) → build index/collection `papers-repaired` → evaluate lại → `generate_corruption_report`.

Quyết định kỹ thuật quan trọng: thêm tham số `target_paper_ids` vào `corrupt_clean_dataframe` để corruption chủ động nhắm vào các tài liệu mà test set thực sự hỏi tới, thay vì chọn ngẫu nhiên toàn bộ dataset (chi tiết ở mục 5).

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `Settings` (từ `.env` qua `core.config.load_settings`), raw/clean artifact đã lưu trên đĩa |
| Output | File JSON/CSV/Markdown theo đúng `Paths` trong `core/config.py`; không trả về giá trị cho caller (chạy như script) |
| Module phụ thuộc | `ingestion.crossref`, `ingestion.cleaning`, `ingestion.corruption`, `evaluation.testset`, `evaluation.metrics`, `observability.quality`, `observability.reporting`, `retrieval.index` |
| Module sử dụng output | `script/run_phase1.py`, `script/run_corruption_flow.py` (entrypoint), báo cáo nhóm đọc trực tiếp từ `data/results/`, `data/quality/`, `data/reports/` |
| Điều kiện lỗi cần xử lý | Thiếu `GOOGLE_API_KEY`/API key tương ứng provider (`require_llm_credentials` raise `RuntimeError`); chạy corruption flow trước khi có baseline (raise `RuntimeError` tường minh) |

### Cách xác minh

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Cả hai lệnh chạy hết không lỗi (exit code 0), sinh đủ artifact ở `data/raw/`, `data/clean/`, `data/embeddings/`, `data/eval/`, `data/results/`, `data/quality/`, `data/reports/`.
- **Kết quả thực tế:** Cả hai lệnh chạy thành công. Baseline: `retrieval_hit_rate=1.0`, `judge_accuracy=0.9722`, 7/7 quality checks PASS. Corrupted: `retrieval_hit_rate=0.9444`, `judge_accuracy=0.75`, 5/7 quality checks PASS (2 FAIL). Repaired: quay lại đúng bằng baseline trên mọi metric (`retrieval_hit_rate=1.0`, `judge_accuracy=0.9722`).
- **Artifact/log:** `data/results/baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `data/reports/corruption_report.md` (không chứa secret).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lần chạy `corruption_flow.py` đầu tiên chọn ngẫu nhiên (không có mục tiêu) các dòng để corrupt trên toàn bộ 24 record. Kết quả: `retrieval_hit_rate` không đổi so với baseline dù đã áp dụng đủ 6 kịch bản corruption, vì corruption vô tình chỉ rơi vào các tài liệu không nằm trong `ground_truth_doc_ids` của bất kỳ câu hỏi nào trong test set.
- **Các phương án đã cân nhắc:**
  1. Tăng tỷ lệ corruption (fraction) lên rất cao để gần như chắc chắn corruption trúng test set bằng xác suất — dễ làm nhưng không đảm bảo, và corrupt quá nhiều dữ liệu không phản ánh kịch bản lỗi thực tế (thường chỉ một phần nhỏ dữ liệu bị lỗi).
  2. Bổ sung tham số `target_paper_ids` để chủ động ưu tiên các dòng nằm trong test set khi chọn nạn nhân corruption.
- **Phương án đã chọn:** Phương án 2 — thêm `target_paper_ids` vào `corrupt_clean_dataframe`, tính từ `ground_truth_doc_ids` của `test_set.json` trong `corruption_flow.py`, ưu tiên các paper_id này trước khi chọn ngẫu nhiên phần còn lại.
- **Lý do:** Đảm bảo tác động của corruption luôn đo được trên metrics bằng thiết kế, không phụ thuộc may rủi của random seed; đồng thời vẫn giữ tỷ lệ corruption thực tế (10–15% mỗi loại) thay vì phải làm hỏng gần như toàn bộ dataset.
- **Bằng chứng quyết định phù hợp:** Sau khi sửa, 6/12 paper_id trong test set bị tác động trực tiếp (đối chiếu `data/results/corruption_log.json` với `ground_truth_doc_ids` trong `data/eval/test_set.json`), và `retrieval_hit_rate` giảm rõ rệt từ 1.0 xuống 0.9444, `judge_accuracy` giảm từ 0.9722 xuống 0.75.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Chuỗi lỗi liên tiếp khi thử chạy LLM judge qua OpenRouter free tier: `402 Payment Required` (tài khoản chưa đủ credit) → `404 Not Found` trên nhiều model `:free` khác nhau (`meta-llama/llama-3.1-8b-instruct:free`, `deepseek/deepseek-chat-v3.1:free`, `x-ai/grok-4-fast:free` — đều deprecated hoặc đã chuyển phí) → sau khi tìm được `openai/gpt-oss-20b:free` hoạt động, cuối cùng gặp `429 Rate limit exceeded: free-models-per-day` — `'Add 10 credits to unlock 1000 free model requests per day'`, tức tài khoản free tier chỉ được 50 request/ngày dùng chung cho mọi model `:free`, không phải theo từng model.
- **Lệnh hoặc bước tái hiện:** `uv run python script/run_phase1.py` / `run_corruption_flow.py` với `LLM_PROVIDER=openrouter` và các `LLM_MODEL` kể trên.
- **Nguyên nhân gốc:** Hai lớp vấn đề chồng lên nhau: (1) danh sách model miễn phí trên OpenRouter thay đổi thường xuyên, nhiều model từng free đã deprecated; (2) ngay cả model free còn hoạt động cũng bị giới hạn cứng 50 request/ngày/tài khoản — giới hạn dễ bị chạm khi thử nghiệm nhiều lần (baseline 36 câu × 1 lần fetch + judge, cộng corruption flow 72 câu, vượt xa 50 request chỉ sau 1-2 lần chạy).
- **Cách xử lý:** Gọi trực tiếp `GET https://openrouter.ai/api/v1/models` để xác nhận model `:free` đang thực sự active trước khi dùng. Khi vẫn liên tục chạm giới hạn 50 request/ngày dù đã có model đúng, chuyển hẳn sang `LLM_PROVIDER=openai` với `LLM_MODEL=gpt-4o-mini` (tài khoản có credit trả phí, không giới hạn theo ngày) — xác nhận hoạt động qua lệnh gọi thử `llm.invoke("Say OK...")` trước khi chạy cả pipeline.
- **Cách xác minh sau khi sửa:** `run_phase1.py` và `run_corruption_flow.py` chạy hết không lỗi với OpenAI, toàn bộ 36 (baseline) + 72 (corrupted + repaired) câu đều có `judge.reasoning` là văn bản do LLM thật sinh ra (ví dụ "The model answer is identical to the reference answer..."), 0 câu rơi vào chuỗi cố định của fallback heuristic trong `evaluation/metrics.py` (`"Fallback heuristic judge used because..."`) — kiểm tra bằng cách đếm số answer chứa chuỗi đó, kết quả 0/36 và 0/72.
- **Điều học được:** Với các dịch vụ LLM router có gói free tier (OpenRouter), giới hạn không chỉ nằm ở việc model có tồn tại hay không mà còn ở quota theo tài khoản/ngày dùng chung cho mọi model free — dễ bị đánh giá nhầm là "model lỗi" khi thực ra là hết hạn ngạch. Khi cần chạy lại nhiều lần trong một phiên làm việc ngắn (debug, thử nghiệm), một provider trả phí ổn định (không rate-limit theo ngày) đáng tin cậy hơn free tier, dù tốn chi phí nhỏ.

## 7. Hiểu biết về luồng end-to-end

1. **Crossref → vector index:** `crossref.py` gọi `GET https://api.crossref.org/works` với `query`/`filter`/`rows` từ `Settings`, lưu response thô vào `data/raw/crossref_response.json`, parse thành `PaperRecord` (DOI làm `paper_id`) lưu vào `data/raw/crossref_records.json`. `cleaning.py` lọc record không hợp lệ, chuẩn hóa text, tính `age_days`, dựng `text_for_embedding`, lưu `data/clean/papers_clean.*`. `retrieval/index.py` dùng `MiniLMEmbeddings` (`all-MiniLM-L6-v2`) encode `text_for_embedding` thành vector 384 chiều, nạp vào ChromaDB collection cùng metadata (`paper_id`, `title`, `published`, `authors_joined`,...).
2. **Test set và ground-truth doc IDs:** `testset.py` duyệt cleaned dataframe, sinh câu hỏi factual (summary/authors/date) gắn `ground_truth_doc_ids = [paper_id]`. Khi evaluate, `metrics.py` so khớp `retrieved_doc_ids` (từ kết quả `index.search`) với `ground_truth_doc_ids` để tính `retrieval_hit_rate`, đồng thời so sánh câu trả lời của agent với `ground_truth` bằng token F1 và LLM judge.
3. **Quality checks khác freshness monitoring:** Quality checks (`run_data_quality_checks`) đánh giá tính toàn vẹn cấu trúc dữ liệu tại một thời điểm (null, duplicate, độ dài trường) — trả lời "dữ liệu có đúng schema/hợp lệ không". Freshness monitoring (`build_freshness_report`) đánh giá tính thời sự của dữ liệu theo `age_days` so với ngưỡng — trả lời "dữ liệu có còn mới không". Một dataset có thể pass toàn bộ quality checks nhưng vẫn stale, hoặc ngược lại.
4. **Vì sao dùng chung test set cho cả 3 trạng thái:** Để cô lập biến số — thay đổi duy nhất giữa 3 lần evaluate là chính dữ liệu (baseline/corrupted/repaired), không phải bộ câu hỏi. Nếu test set thay đổi theo từng trạng thái, chênh lệch metrics có thể đến từ câu hỏi khác nhau chứ không phải từ corruption, làm mất tính nhân quả của so sánh.
5. **Repair được xem là thành công dựa trên artifact/metric nào:** Dựa trên (a) `data/quality/repaired_quality.json` — toàn bộ 7/7 check PASS trở lại giống baseline; (b) `data/results/repaired_metrics.json` — cả 4 metric (`retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`) bằng chính xác giá trị baseline (delta = 0); (c) `data/quality/freshness_report_repaired.json` — stale rate quay về 0%, khớp baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.9444 | 1.0000 | Giảm ít nhất trong 4 metric — semantic search vẫn khá bền với nhiễu nhỏ trong text vì MiniLM encode toàn bộ ngữ cảnh, không chỉ 1 trường |
| `mean_token_f1` | 1.0000 | 0.7627 | 1.0000 | Giảm nhiều nhất — vì agent trích câu trả lời trực tiếp từ `summary`, nên blank/noise summary ảnh hưởng trực diện đến độ khớp từ vựng |
| `judge_accuracy` | 0.9722 | 0.7500 | 0.9722 | Giảm ~22 điểm phần trăm — ngay cả baseline cũng không tuyệt đối 100% vì LLM judge (`gpt-4o-mini`) đôi khi chấm khắt khe hơn heuristic token F1 |
| `mean_judge_score` | 4.8889 | 4.1667 | 4.8889 | Giảm gần 1 điểm trên thang 5 |
| Quality checks | PASS 7/7 | FAIL (5/7, 2 lỗi) | PASS 7/7 | `paper_id_unique` và `summary_min_length` là 2 check bắt đúng corruption đã áp dụng (duplicate + blank summary) |
| Freshness status | Fresh (0% stale) | Fresh nhưng stale_rate tăng lên 20.83% | Fresh (0% stale) | Dù vẫn dưới ngưỡng cảnh báo 50%, con số 20.83% đã đủ cho thấy stale-date corruption có tác động đo được |

### Kết luận từ số liệu

1. Blank summary + noise injection (`data/results/corruption_log.json`) → `summary_min_length` check FAIL, `text_for_embedding` bị nhiễu (`data/quality/corrupted_quality.json`) → `mean_token_f1` giảm mạnh nhất (1.0 → 0.7627, `data/results/corrupted_metrics.json`).
2. Repair chạy lại `build_clean_dataframe` từ `data/raw/crossref_records.json` → toàn bộ quality checks PASS trở lại và freshness về 0% stale (`data/quality/repaired_quality.json`) → cả 4 agent metric phục hồi chính xác về baseline.

Corruption ảnh hưởng rõ nhất: **blank summary** và **noise injection** vào summary — vì agent (`retrieval/qa.py::_extract_answer`) trả lời hầu hết câu hỏi dạng "what is this paper about" bằng cách trích trực tiếp câu đầu tiên của `summary`; khi summary rỗng hoặc lẫn ký tự rác, câu trả lời sai hẳn về nội dung dù retrieval vẫn tìm đúng tài liệu.

Kết quả không khác kỳ vọng ban đầu đáng kể sau khi sửa bug overlap — trước khi sửa (corruption chọn ngẫu nhiên không nhắm mục tiêu), `retrieval_hit_rate` không đổi so với baseline dù đã corrupt 6 kịch bản, điều này ban đầu gây nghi ngờ code corruption không hoạt động. Đã kiểm tra bằng cách đối chiếu `corruption_log.json` với `ground_truth_doc_ids` trong test set và phát hiện 0% overlap ở lần chạy đó — xác nhận nguyên nhân là do thiết kế lựa chọn ngẫu nhiên, không phải lỗi logic corrupt từng trường.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline:** Một pipeline "chạy được" (exit code 0) không đồng nghĩa với "chứng minh được điều cần chứng minh" — corruption chạy thành công nhưng chọn ngẫu nhiên có thể tạo ra kết quả vô nghĩa nếu không giao với vùng dữ liệu thực sự được đánh giá.
2. **Về data quality/observability:** Quality checks (structural) và freshness (temporal) là hai trục độc lập cần đo riêng — một dataset có thể pass hết check cấu trúc nhưng đã lỗi thời, và ngược lại.
3. **Về ảnh hưởng của data đến RAG agent:** Các trường dữ liệu không đóng vai trò như nhau — corruption vào `summary` (trường agent dùng để sinh câu trả lời) có tác động lớn hơn nhiều so với corruption vào `published` (chỉ ảnh hưởng freshness, không ảnh hưởng answer quality trực tiếp).

### Nếu có thêm thời gian

Sẽ bật `RUN_RAGAS=1` để có thêm bộ chỉ số `answer_relevancy`, `context_precision`, `context_recall`, `faithfulness` từ Ragas, đối chiếu xem các chỉ số này có nhạy với corruption theo cùng xu hướng như `judge_accuracy`/`mean_token_f1` hay không — đo bằng cách so sánh độ lớn tương đối (%) sụt giảm giữa các bộ metric.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Trương Minh Tâm
**Ngày xác nhận:** 2026-08-06
