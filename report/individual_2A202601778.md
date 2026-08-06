# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Trần Hoàng Khôi |
| MSSV | 2A202601778 |
| Khóa/Lớp | K4 |
| Tên nhóm | K4-Day10-Data-Pipeline-Data-Observability |
| Vai trò chính | Thành viên 2 — Cleaning & Test Set |
| Repository | K4_Day10_Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Cleaning & data modeling | `src/ingestion/cleaning.py` (`build_clean_dataframe`) | `list[PaperRecord]` từ Thành viên 1 + `run_date` | `data/clean/papers_clean.csv`, `.json` | Hoàn thành |
| Frozen evaluation test set | `src/evaluation/testset.py` (`build_test_set`) | Cleaned dataframe | `data/eval/test_set.json` | Hoàn thành |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Lọc record không hợp lệ: thiếu `paper_id`, `title` < 3 ký tự, `summary` < 100 ký tự | `build_clean_dataframe` (`MIN_TITLE_LENGTH=3`, `MIN_SUMMARY_LENGTH=100`) | 24 raw records → 24 clean rows (không record nào bị loại ở lần fetch này) | `data/clean/papers_clean.csv` — đếm số dòng |
| Chuẩn hóa `authors_joined`, `categories_joined` (nối bằng dấu phẩy qua `compact_join`), chuẩn hóa whitespace qua `normalize_whitespace` | `build_clean_dataframe` | Cột `authors_joined`, `categories_joined` sạch, không khoảng trắng thừa | Mở `data/clean/papers_clean.json`, kiểm tra định dạng chuỗi |
| Tính `age_days = (run_date - published_date).days` | `build_clean_dataframe` | Cột `age_days` dùng cho quality/freshness check của Thành viên 3 | `data/quality/freshness_report.json` — `stale_rate=0.0%` với `age_days` hợp lý |
| Dựng `text_for_embedding` theo format `Title: {title} \| Authors: {authors_joined} \| Summary: {summary}` | `build_clean_dataframe` | Trường dùng để encode vector, xuất hiện trong `data/embeddings/papers_embeddings.json` | Mở `papers_clean.json`, đối chiếu format |
| Sinh 36 câu hỏi factual (3 loại: `summary`, `authors`, `date`) gắn `ground_truth_doc_ids = [paper_id]` | `build_test_set` | `data/eval/test_set.json` — đóng băng, dùng chung cho baseline/corrupted/repaired | Đếm `question_type` trong test set: 12/12/12 |

Output cụ thể: `data/eval/test_set.json` — mỗi câu hỏi có `ground_truth_doc_ids = [paper_id]` lấy trực tiếp từ `paper_id` đã chuẩn hóa trong bước cleaning, đảm bảo tham chiếu luôn đúng dù dữ liệu sau này bị corrupt hay repair, vì `paper_id` không bao giờ bị thay đổi qua các bước xử lý.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Dữ liệu Crossref thô (`PaperRecord`) chứa nhiều vấn đề cần xử lý trước khi dùng cho RAG: thẻ JATS-XML còn sót trong abstract, danh sách tác giả/category ở dạng list cần nối thành chuỗi, ngày tháng ở nhiều định dạng khác nhau, và có thể có record trùng lặp hoặc thiếu trường bắt buộc. Song song đó, cần một bộ câu hỏi đánh giá "đóng băng" — sinh một lần duy nhất và dùng lại y nguyên cho cả ba trạng thái baseline/corrupted/repaired, để phép so sánh giữa ba trạng thái chỉ phản ánh thay đổi dữ liệu chứ không lẫn thay đổi bộ câu hỏi.

### Cách triển khai

`build_clean_dataframe` duyệt từng `PaperRecord`, chuẩn hóa `paper_id`/`title`/`summary` bằng `normalize_whitespace`, loại bỏ record có `paper_id` rỗng hoặc `title` dưới 3 ký tự ngay trong vòng lặp. Sau khi build xong toàn bộ dataframe, áp thêm bộ lọc `summary_chars >= MIN_SUMMARY_LENGTH` (100 ký tự) và `drop_duplicates(subset=["paper_id"])` để loại record trùng, rồi sort theo `published` giảm dần. `age_days` được tính bằng cách trừ `published_ts` từ `run_ts` (đã ép về không timezone để tránh lỗi so sánh aware/naive).

`build_test_set` duyệt tối đa `MAX_SAMPLE_PAPERS=12` bài đầu tiên (đã sort theo ngày mới nhất từ bước cleaning), với mỗi bài thử sinh 4 loại câu hỏi (`summary`, `authors`, `date`, `categories`) qua hàm `_make_question`. Hàm này trả về `None` nếu trường tương ứng rỗng (ví dụ không sinh câu hỏi `categories` nếu `categories_joined` rỗng) — đây là lý do tập câu hỏi thực tế chỉ có 3 loại (36 câu, 12 mỗi loại) thay vì đủ 4 loại, vì Crossref không trả về trường `subject` cho toàn bộ 24 bài trong lần fetch này.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `list[PaperRecord]` (từ `ingestion.crossref`), `datetime` làm mốc tính `age_days`; với test set là `pd.DataFrame` đã clean |
| Output | `pd.DataFrame` với schema cố định (`paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`, `age_days`, `text_for_embedding`,...); với test set là `list[dict]` schema `{id, question_type, question, ground_truth, ground_truth_doc_ids}` |
| Module phụ thuộc | `core.utils.normalize_whitespace`, `compact_join`, `first_sentence` |
| Module sử dụng output | `src/retrieval/index.py` (encode `text_for_embedding`), `src/observability/quality.py` (check trên `summary`, `age_days`), `src/evaluation/metrics.py` (đọc `test_set.json` để evaluate), `src/ingestion/corruption.py` (nhận `target_paper_ids` từ `ground_truth_doc_ids` của test set) |
| Điều kiện lỗi cần xử lý | Dataframe rỗng sau lọc → `build_clean_dataframe` trả về dataframe rỗng thay vì lỗi; dataframe có ít hơn `MIN_DOCUMENTS_REQUIRED=3` dòng → `build_test_set` raise `ValueError` tường minh |

### Cách xác minh

```bash
uv run python script/run_phase1.py
```

- **Kết quả mong đợi:** `data/clean/papers_clean.csv`/`.json` có 24 dòng, không có `paper_id` rỗng/trùng; `data/eval/test_set.json` có ít nhất 12 câu hỏi (thực tế 36) với `ground_truth_doc_ids` là `paper_id` hợp lệ.
- **Kết quả thực tế:** Đúng như mong đợi — 24 clean rows, `data/quality/baseline_quality.json` xác nhận `paper_id_not_null`/`paper_id_unique`/`summary_min_length` đều PASS; test set có đúng 36 câu (12 mỗi loại `summary`/`authors`/`date`).
- **Artifact/log:** `data/clean/papers_clean.csv`, `.json`, `data/eval/test_set.json` (không chứa secret).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Checkpoint yêu cầu loại record có `summary` "quá ngắn (dưới 100 ký tự)". Ban đầu ngưỡng trong code là 20 ký tự — một con số tùy ý không khớp yêu cầu, khiến gần như mọi abstract Crossref (thường vài trăm ký tự) đều lọt qua dù về mặt hình thức có thể quá ngắn để dùng làm ground truth có ý nghĩa.
- **Các phương án đã cân nhắc:**
  1. Giữ ngưỡng 20 ký tự — dễ code hơn nhưng không đúng chuẩn checkpoint, và cho phép các summary quá ngắn (như "N/A" hoặc một câu cụt) lọt vào làm hỏng chất lượng câu hỏi sinh ra sau này.
  2. Nâng ngưỡng lên đúng 100 ký tự theo yêu cầu checkpoint.
- **Phương án đã chọn:** Phương án 2 — `MIN_SUMMARY_LENGTH = 100`.
- **Lý do:** Ground truth cho câu hỏi dạng "tóm tắt bài báo về gì" cần đủ nội dung để `first_sentence()` (dùng trong `testset.py`) trích ra một câu có ý nghĩa; summary quá ngắn dễ sinh ra ground truth vô nghĩa hoặc rỗng, ảnh hưởng trực tiếp đến chất lượng đánh giá của cả nhóm.
- **Bằng chứng quyết định phù hợp:** Sau khi nâng ngưỡng, số record clean vẫn giữ nguyên 24/24 (không mất record nào vì toàn bộ abstract Crossref trong tập dữ liệu này đều đủ dài) — nghĩa là ngưỡng đúng chuẩn không đánh đổi bằng việc mất dữ liệu, đồng thời `data/quality/baseline_quality.json` xác nhận `summary_min_length: PASS`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Test set ban đầu chỉ có 3 loại câu hỏi (`summary`, `authors`, `date`) thay vì đủ 4 loại như thiết kế (`categories` bị thiếu hoàn toàn) — không phải lỗi runtime, nhưng là một khoảng trống so với kỳ vọng ban đầu khi review lại `data/eval/test_set.json`.
- **Lệnh hoặc bước tái hiện:** Chạy `run_phase1.py`, sau đó đếm `Counter(item['question_type'] for item in test_set)` trên `data/eval/test_set.json`.
- **Nguyên nhân gốc:** `_make_question` trả về `None` cho loại `categories` khi `row["categories_joined"]` rỗng; kiểm tra `data/clean/papers_clean.json` cho thấy toàn bộ 24/24 record có `categories_joined = ""`, vì Crossref API không trả về trường `subject` cho các bài báo khớp với query/filter đang dùng.
- **Cách xử lý:** Xác nhận đây không phải lỗi logic trong `_make_question` (hàm hoạt động đúng thiết kế — bỏ qua loại câu hỏi khi thiếu dữ liệu nguồn thay vì tạo câu hỏi rỗng/sai) mà là giới hạn của nguồn dữ liệu. Không sửa code để "ép" tạo câu hỏi categories giả, vì điều đó sẽ vi phạm nguyên tắc test set phải phản ánh dữ liệu thật. Ghi nhận đây là giới hạn đã biết trong báo cáo nhóm thay vì che giấu.
- **Cách xác minh sau khi sửa:** `data/eval/test_set.json` có đúng 36 câu hỏi (12 summary + 12 authors + 12 date), không có câu hỏi categories rỗng hoặc sai lệch — kiểm tra bằng cách duyệt toàn bộ test set và xác nhận không có `ground_truth` rỗng.
- **Điều học được:** Khi một trường dữ liệu phụ thuộc vào nguồn bên ngoài (ở đây là `subject` từ Crossref), code sinh câu hỏi cần graceful-skip thay vì cố tạo dữ liệu giả để "đủ chỉ tiêu" — một bộ test set nhỏ hơn nhưng toàn bộ ground truth đều thật vẫn tốt hơn một bộ đủ số lượng nhưng có phần bịa đặt.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào:** Thành viên 1 fetch và parse raw JSON thành `PaperRecord`; tôi nhận list này, lọc record không hợp lệ, chuẩn hóa text, tính `age_days`, dựng `text_for_embedding` theo format cố định, xuất ra `data/clean/papers_clean.*`; sau đó `retrieval/index.py` encode `text_for_embedding` bằng MiniLM (384 chiều) và nạp vào ChromaDB cùng metadata (`paper_id`, `title`, `published`, `authors_joined`,...).
2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao:** Tôi sinh câu hỏi từ dataframe sạch, mỗi câu gắn đúng một `paper_id` làm `ground_truth_doc_ids`. Khi evaluate, hệ thống retrieval trả về top-k `retrieved_doc_ids`; nếu `ground_truth_doc_ids` giao với `retrieved_doc_ids` thì tính là hit (dùng cho `retrieval_hit_rate`); câu trả lời của agent được so với `ground_truth` bằng token F1 và LLM judge.
3. **Quality checks khác freshness monitoring ở điểm nào:** Quality checks (Thành viên 3) đo tính hợp lệ cấu trúc tại một thời điểm (null, duplicate, độ dài) dựa trên các cột tôi tạo ra (`summary`, `paper_id`). Freshness monitoring đo tính thời sự dựa trên `age_days` — cột tôi cũng chính là người tính toán trong bước cleaning. Hai trục độc lập nhưng đều bắt nguồn từ cùng dataframe do tôi build.
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired:** Vì `test_set.json` được tôi sinh một lần duy nhất ở bước baseline và các pipeline sau chỉ đọc lại, không tái tạo — điều này cô lập biến số duy nhất thay đổi giữa ba lần đánh giá là chính dữ liệu bị corrupt/repair, không phải câu hỏi. Nếu mỗi trạng thái có bộ câu hỏi riêng, sự khác biệt về ground truth sẽ trộn lẫn với tác động của corruption.
5. **Repair được xem là thành công dựa trên artifact và metric nào:** Repair chạy lại chính hàm `build_clean_dataframe` mà tôi viết, trên raw snapshot gốc — nên nếu raw snapshot không đổi, kết quả repair phải giống hệt clean dataframe gốc. Bằng chứng: `data/clean/papers_clean_repaired.json` có cùng 24 dòng, cùng `text_for_embedding`, và `data/results/repaired_metrics.json` cho thấy agent metric quay lại đúng baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.9444 | 1.0000 | Câu hỏi tôi sinh ra đều tham chiếu đúng 1 tài liệu nguồn duy nhất, nên khi tài liệu đó không bị hỏng, retrieval luôn tìm đúng — sự sụt giảm hoàn toàn đến từ corruption chứ không phải chất lượng câu hỏi |
| `mean_token_f1` | 1.0000 | 0.7627 | 1.0000 | Ground truth của tôi lấy trực tiếp từ `summary`/`authors_joined`/`published` gốc, nên khi các trường này bị corrupt, agent trả lời sai và F1 giảm rõ — đúng ý đồ thiết kế câu hỏi bám sát dữ liệu thật |
| Số câu hỏi mỗi loại | 12/12/12 (summary/authors/date) | không đổi (dùng chung test set) | không đổi | Test set đóng băng đúng như thiết kế — không loại nào bị regenerate giữa 3 lần chạy |

### Kết luận từ số liệu

1. **Blank summary + noise injection** (do Thành viên 4 tạo, nhắm vào `ground_truth_doc_ids` mà tôi cung cấp) → câu hỏi loại `summary` trong test set của tôi không còn tìm được ground truth đúng trong `summary` đã bị hỏng → `mean_token_f1` giảm mạnh nhất trong 4 metric (`data/results/corrupted_metrics.json`) — xác nhận thiết kế câu hỏi bám sát trường dữ liệu thực sự nhạy với corruption.
2. **Repair action** (chạy lại đúng hàm `build_clean_dataframe` của tôi trên raw) → dataframe repaired giống hệt baseline → agent trả lời đúng như cũ trên chính bộ câu hỏi tôi đã sinh, không cần thay đổi gì ở `test_set.json`.

Test set của tôi phát huy đúng vai trò làm "công cụ đo" nhất quán: vì `ground_truth_doc_ids` không đổi qua 3 trạng thái, mọi chênh lệch metric quan sát được đều có thể quy về đúng nguyên nhân là thay đổi dữ liệu, không phải nhiễu từ việc thay đổi câu hỏi.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline:** Ngưỡng lọc dữ liệu (như độ dài summary tối thiểu) không nên chọn tùy ý — cần bám đúng yêu cầu nghiệp vụ/checkpoint, vì ngưỡng sai có thể khiến dữ liệu "sạch" nhưng không đạt chất lượng cần thiết cho downstream task.
2. **Về data quality/observability:** Một trường dữ liệu do tôi tạo ra (`age_days`, `text_for_embedding`) sẽ được nhiều module khác dùng làm input cho quality/freshness check — lỗi ở bước cleaning sẽ lan ra thành lỗi khó chẩn đoán ở các bước sau nếu không thống nhất schema rõ ràng ngay từ đầu.
3. **Về ảnh hưởng của data đến RAG agent:** Chất lượng của evaluation set quan trọng không kém chất lượng của corpus — câu hỏi bám sát đúng trường dữ liệu (thay vì câu hỏi chung chung) mới thực sự đo được tác động khi dữ liệu bị hỏng.

### Nếu có thêm thời gian

Sẽ bổ sung fallback lấy `categories_joined` từ trường `container-title` hoặc `subject` ở các endpoint khác của Crossref (ví dụ tra cứu theo `type` của publication) để có đủ dữ liệu sinh câu hỏi loại `categories`, đo hiệu quả bằng cách so sánh số bài có `categories_joined` khác rỗng trước/sau khi bổ sung fallback.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Trần Hoàng Khôi
**Ngày xác nhận:** 2026-08-06
