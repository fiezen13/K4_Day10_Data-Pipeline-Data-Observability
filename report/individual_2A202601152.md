# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Phạm Hải Yến |
| MSSV | 2A202601152 |
| Khóa/Lớp | K4 |
| Tên nhóm | K4-Day10-Data-Pipeline-Data-Observability |
| Vai trò chính | Thành viên 4 — Corruption & Repair |
| Repository | K4_Day10_Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Controlled data corruption | `src/ingestion/corruption.py` (`corrupt_clean_dataframe`) | Baseline clean dataframe (bản copy) + `target_paper_ids` (từ Thành viên 5) | `data/clean/papers_corrupted.csv`, `.json` | Hoàn thành |
| Corruption manifest | `corrupt_clean_dataframe` (ghi log nội bộ) | — | `data/results/corruption_log.json` | Hoàn thành |
| Repair (thực thi bởi pipeline, dùng logic cleaning gốc) | Không sở hữu file riêng — repair tái sử dụng `build_clean_dataframe` của Thành viên 2, gọi từ `corruption_flow.py` trên raw snapshot | `data/raw/crossref_records.json` | `data/clean/papers_clean_repaired.csv`, `.json` | Hoàn thành (thiết kế đảm bảo repairability) |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Thiết kế 6 kịch bản corruption có kiểm soát: drop latest, blank summary, noise injection, truncate title, stale date, duplicate rows | `corrupt_clean_dataframe` với 6 hằng số `*_FRACTION` (10–15% mỗi loại) | `data/clean/papers_corrupted.csv`/`.json` — 24 dòng (2 drop + 2 duplicate bù lại = giữ nguyên tổng) | Đối chiếu `data/results/corruption_log.json` với dataframe corrupted |
| Đảm bảo corruption nhắm trúng `ground_truth_doc_ids` của test set thay vì random thuần túy | `prioritized_indices` (target trước, non-target sau) trong `corrupt_clean_dataframe` | 6/12 tài liệu mục tiêu trong test set bị tác động trực tiếp | So khớp `corruption_log.json` với `data/eval/test_set.json` |
| Ghi log chi tiết từng loại corruption tác động vào `paper_id` nào | `manifest` dict, `write_json(output_log_path, manifest)` | `data/results/corruption_log.json` — 6 danh sách `paper_id` theo loại + `original_row_count`/`corrupted_row_count` | Mở file JSON, đếm số phần tử mỗi danh sách |
| Rebuild `text_for_embedding` sau mọi thay đổi để index phản ánh đúng dữ liệu đã hỏng | `_rebuild_text_for_embedding`, `df.apply(...)` ở bước cuối | `text_for_embedding` trong `papers_corrupted.json` khớp với `title`/`summary` đã bị corrupt | So sánh `text_for_embedding` trước/sau với `summary` đã bị blank/noise |

Output cụ thể: `data/results/corruption_log.json` không chỉ ghi "đã corrupt bao nhiêu dòng" mà liệt kê chính xác `paper_id` nào bị loại nào tác động — đây là bằng chứng bắt buộc để Thành viên 5 và Thành viên 3 có thể đối chiếu corruption với sự thay đổi của `data/quality/corrupted_quality.json` và `data/results/corrupted_metrics.json`, chứng minh corruption thật sự gây ra hậu quả đo được chứ không phải chỉ chạy cho có.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Cần một cách làm hỏng dữ liệu sạch một cách **có kiểm soát và có thể đo lường được** — không phải phá hủy ngẫu nhiên toàn bộ dataset (không thực tế, không so sánh được), mà phải mô phỏng các lỗi dữ liệu thường gặp trong thực tế (thiếu trường, dữ liệu cũ, trùng lặp, nhiễu nội dung) với tỷ lệ nhỏ và có bằng chứng ghi lại đầy đủ, đồng thời đảm bảo có thể phục hồi hoàn toàn từ nguồn gốc đáng tin cậy.

### Cách triển khai

`corrupt_clean_dataframe` nhận dataframe baseline (bản copy, không sửa trực tiếp bản gốc — điều này được đảm bảo bởi caller `corruption_flow.py` truyền `baseline_df.copy(deep=True)`) và áp dụng tuần tự 6 bước biến đổi, mỗi bước dùng một `random.Random(RANDOM_SEED=42)` chung để kết quả tái lập được:

1. **Drop latest**: loại bỏ 10% bản ghi xuất bản gần nhất nhất, nhưng **loại trừ** các `paper_id` nằm trong `target_paper_ids` — vì nếu drop hẳn một tài liệu mà test set đang hỏi, mọi câu hỏi về nó sẽ miss retrieval tuyệt đối, một cách chứng minh tác động quá thô thiển và không đo được mức độ suy giảm dần.
2. **Blank summary** (15%), **noise injection** (15%), **truncate title** (15%), **stale date** (15%): mỗi bước dùng hàm nội bộ `_take(fraction)` lấy từ `prioritized_indices` — danh sách đã được sắp xếp ưu tiên các dòng có `paper_id` nằm trong `target_paper_ids` lên đầu.
3. **Duplicate rows** (10%): nhân đôi dòng bằng `pd.concat`, giữ nguyên `paper_id` — đây là kịch bản duy nhất **làm tăng** số dòng, cân bằng lại phần đã drop ở bước 1.

Sau toàn bộ 6 bước, `text_for_embedding` được rebuild lại từ `title`/`authors_joined`/`summary` **đã bị corrupt** (không phải bản gốc) để đảm bảo bước embedding/index downstream phản ánh đúng dữ liệu hỏng, tránh trường hợp field hiển thị (summary) đã hỏng nhưng field dùng để retrieval (text_for_embedding) vẫn còn dữ liệu sạch — một lỗi ẩn khó phát hiện nếu quên bước rebuild này.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `pd.DataFrame` (bản copy của baseline clean dataframe), `output_log_path`, `target_paper_ids: set[str] \| None` |
| Output | `pd.DataFrame` đã bị corrupt (số dòng có thể khác baseline do drop/duplicate), đồng thời ghi `manifest` JSON ra `output_log_path` |
| Module phụ thuộc | `core.utils.normalize_whitespace`, `now_utc`, `write_json`; nhận `target_paper_ids` được Thành viên 5 tính từ `ground_truth_doc_ids` trong `test_set.json` |
| Module sử dụng output | `src/pipelines/corruption_flow.py` gọi hàm này, ghi kết quả ra `data/clean/papers_corrupted.*`, dùng để build lại ChromaDB collection `papers-corrupted` và evaluate |
| Điều kiện lỗi cần xử lý | `target_paper_ids` rỗng/`None` → corruption vẫn chạy nhưng chọn nạn nhân hoàn toàn ngẫu nhiên (tương thích ngược, không raise lỗi) |

### Cách xác minh

```bash
uv run python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** `data/clean/papers_corrupted.csv`/`.json` được tạo, khác với `papers_clean.csv` gốc; `data/results/corruption_log.json` liệt kê đầy đủ `paper_id` bị tác động theo từng loại; sau đó `data/clean/papers_clean_repaired.*` phải khôi phục giống hệt baseline.
- **Kết quả thực tế:** Đúng như mong đợi. `corruption_log.json` ghi nhận: 2 dropped, 3 blanked, 3 noisy, 3 truncated, 3 stale-dated, 2 duplicated (`original_row_count=24`, `corrupted_row_count=24` — cân bằng vì 2 drop bù lại bởi 2 duplicate). Sau repair, `data/quality/repaired_quality.json` báo 7/7 PASS và `data/results/repaired_metrics.json` khớp chính xác baseline.
- **Artifact/log:** `data/clean/papers_corrupted.csv`, `.json`, `data/results/corruption_log.json`, `data/clean/papers_clean_repaired.csv`, `.json` (không chứa secret).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Ở thiết kế đầu tiên, hàm `corrupt_clean_dataframe` chọn dòng để corrupt bằng `rng.shuffle` trên toàn bộ dataframe rồi lấy `fraction` đầu tiên — hoàn toàn ngẫu nhiên, không biết gì về việc câu hỏi trong test set đang hỏi về tài liệu nào. Kết quả lần chạy đầu: `retrieval_hit_rate` không đổi so với baseline dù đã áp dụng đủ 6 kịch bản, vì corruption tình cờ chỉ rơi vào các tài liệu không tài liệu nào được hỏi tới.
- **Các phương án đã cân nhắc:**
  1. Tăng mạnh tỷ lệ corruption (ví dụ 50–70% mỗi loại) để gần như chắc chắn trúng test set bằng xác suất thuần túy — không đảm bảo 100%, và corrupt quá nhiều dữ liệu không phản ánh đúng kịch bản lỗi thực tế (thường chỉ một phần nhỏ dữ liệu production bị lỗi tại một thời điểm).
  2. Chủ động ưu tiên các dòng nằm trong `target_paper_ids` (là `ground_truth_doc_ids` của test set) khi chọn nạn nhân, giữ nguyên tỷ lệ corrupt nhỏ (10–15%) như ban đầu.
- **Phương án đã chọn:** Phương án 2 — thêm tham số `target_paper_ids`, dùng `prioritized_indices = target_indices + non_target_indices` thay cho `remaining_indices` thuần random.
- **Lý do:** Đảm bảo tác động của corruption luôn đo được trên metrics **bằng thiết kế**, không phụ thuộc may rủi của random seed hay kích thước fraction; đồng thời tỷ lệ corrupt nhỏ vẫn phản ánh đúng thực tế là lỗi dữ liệu thường chỉ ảnh hưởng một phần dataset.
- **Bằng chứng quyết định phù hợp:** Sau khi sửa, `data/results/corruption_log.json` cho thấy 6/12 `paper_id` trong test set bị tác động trực tiếp (đối chiếu với `ground_truth_doc_ids` trong `test_set.json`), và `retrieval_hit_rate` giảm rõ rệt từ 1.0 xuống 0.9444, `mean_token_f1` giảm từ 1.0 xuống 0.7627 — chứng minh corruption giờ đây luôn tạo ra tác động quan sát được.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Sau khi thêm logic ưu tiên `target_paper_ids`, trường `original_row_count` trong `corruption_log.json` báo giá trị `12` thay vì giá trị đúng phải là 24 (số dòng baseline trước khi corrupt) — một con số vô lý vì không khớp với `corrupted_row_count=24` cùng file.
- **Lệnh hoặc bước tái hiện:** Chạy `run_corruption_flow.py`, mở `data/results/corruption_log.json`, so sánh `original_row_count` với số dòng thật của `data/clean/papers_clean.csv`.
- **Nguyên nhân gốc:** Dòng code `manifest["original_row_count"] = len(sorted_by_recency)` tính nhầm — biến `sorted_by_recency` tại thời điểm đó đã được gán lại thành `droppable.sort_values(...)`, tức là dataframe **đã lọc bỏ** các `target_paper_ids` trước khi tính "drop latest" (để tránh drop nhầm tài liệu mục tiêu), nên độ dài của nó chỉ còn 24 trừ đi 12 tài liệu target = 12, chứ không phải tổng số dòng gốc.
- **Cách xử lý:** Lưu số dòng gốc vào một biến riêng `original_row_count = len(df)` ngay từ đầu hàm, trước khi bất kỳ phép lọc nào diễn ra, và dùng biến này khi ghi vào manifest thay vì tái sử dụng `sorted_by_recency` (biến này chỉ nên dùng cho mục đích tính "drop latest", không đại diện cho toàn bộ dataset).
- **Cách xác minh sau khi sửa:** Chạy lại `run_corruption_flow.py`, `corruption_log.json` báo `original_row_count=24`, khớp đúng số dòng của `data/clean/papers_clean.csv`.
- **Điều học được:** Khi một biến trung gian bị tái sử dụng (reassign) nhiều lần trong cùng một hàm cho các mục đích lọc khác nhau, cần đặt tên biến rõ ràng theo đúng ý nghĩa tại thời điểm dùng, hoặc tách biến riêng cho từng mục đích — tránh dùng lại một biến đã bị thu hẹp phạm vi cho việc tính toán tổng thể (ở đây là đếm tổng số dòng).

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào:** Raw records từ Crossref (Thành viên 1) được clean thành dataframe chuẩn (Thành viên 2), sau đó vừa được index trực tiếp cho baseline, vừa được tôi đọc lại (`data/clean/papers_clean.json`) để tạo bản corrupted — corruption luôn xuất phát từ dataframe đã clean, không phải từ raw, vì corruption mô phỏng lỗi xảy ra *sau* khi dữ liệu đã vào hệ thống (ví dụ do lỗi ETL, thao tác sai của người vận hành), không phải lỗi từ nguồn.
2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao:** `ground_truth_doc_ids` từ `test_set.json` (Thành viên 2) chính là danh sách `target_paper_ids` mà tôi dùng để quyết định corrupt tài liệu nào — đây là điểm nối trực tiếp giữa module của tôi và module evaluation, đảm bảo mọi corruption đều "hỏi được" qua ít nhất một câu trong test set.
3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab:** Corruption của tôi tác động lên cả hai trục: một số kịch bản (duplicate, blank summary) làm hỏng cấu trúc (bắt bởi quality checks của Thành viên 3), kịch bản khác (stale date) làm hỏng tính thời sự (bắt bởi freshness monitoring) — hai trục độc lập nhưng cùng bị corruption của tôi "đánh" vào.
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired:** Vì corruption của tôi được thiết kế để nhắm chính xác vào `ground_truth_doc_ids` của **một** test set cố định — nếu test set đổi giữa các lần chạy, `target_paper_ids` cũng đổi theo, và không còn cách nào đảm bảo corruption "trúng" đúng những gì đang được đánh giá.
5. **Repair được xem là thành công dựa trên artifact và metric nào:** Repair không phải là "sửa" dataframe đã corrupt, mà là chạy lại `build_clean_dataframe` (hàm của Thành viên 2) trên `data/raw/crossref_records.json` — tức bỏ hoàn toàn dataframe corrupted đi và dựng lại từ đầu. Thành công được đo bằng `data/quality/repaired_quality.json` (7/7 PASS) và `data/results/repaired_metrics.json` (khớp chính xác baseline, delta = 0) — chứng minh mọi dấu vết corruption đã biến mất hoàn toàn, không phải chỉ được "che" đi.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.9444 | 1.0000 | Giảm nhẹ nhất — 2 kịch bản của tôi ảnh hưởng trực tiếp semantic search (noise injection, truncate title) chỉ tác động 6/24 dòng, và MiniLM vẫn giữ được phần lớn ngữ nghĩa dù `text_for_embedding` bị nhiễu một phần |
| `mean_token_f1` | 1.0000 | 0.7627 | 1.0000 | Giảm mạnh nhất — kịch bản blank summary của tôi xóa trắng hoàn toàn nguồn thông tin mà agent dùng để trả lời, không còn gì để "đoán đúng" dù retrieval vẫn tìm ra tài liệu |
| Quality checks | PASS 7/7 | FAIL (5/7, 2 lỗi) | PASS 7/7 | `paper_id_unique` (từ kịch bản duplicate rows của tôi) và `summary_min_length` (từ blank summary) là 2 check tôi trực tiếp gây FAIL — đúng như thiết kế |
| Freshness status | Fresh (0% stale) | Fresh nhưng stale_rate=20.83% | Fresh (0% stale) | Kịch bản stale date của tôi đẩy 5 bản ghi (bao gồm cả các bản ghi bị corrupt khác) vượt ngưỡng 180 ngày, tạo tín hiệu đo được rõ ràng dù chưa đủ để lật trạng thái tổng thể |

### Kết luận từ số liệu

1. **Blank summary + noise injection** (2 kịch bản của tôi tác động 6 record, trong đó có overlap với target test set) → `data/quality/corrupted_quality.json` báo `summary_min_length: FAIL` → `mean_token_f1` giảm mạnh nhất trong 4 metric (`data/results/corrupted_metrics.json`) — chuỗi nhân quả trực tiếp từ corruption tôi tạo ra đến metric suy giảm.
2. **Repair bằng cách build lại từ raw** (không sửa tay dataframe corrupted) → toàn bộ 6 loại corruption biến mất hoàn toàn, `data/results/repaired_metrics.json` khớp baseline tuyệt đối — chứng minh repair đúng nguyên tắc "phục hồi từ nguồn tin cậy" chứ không phải patch tạm thời.

Kịch bản ảnh hưởng nghiêm trọng nhất đến retrieval: **noise injection** và **truncate title**, vì cả hai đều làm nhiễu trực tiếp `text_for_embedding` — trường duy nhất được dùng để tính vector embedding cho semantic search. Ngược lại, **stale date** hầu như không ảnh hưởng retrieval/answer quality (không nằm trong `text_for_embedding`), chỉ ảnh hưởng tín hiệu freshness — một minh chứng rằng không phải mọi loại corruption đều tác động đều lên mọi tầng của hệ thống, mà phụ thuộc vào trường dữ liệu nào bị hỏng và trường đó được dùng ở đâu trong pipeline.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline:** Corruption "chạy được" không đồng nghĩa với corruption "chứng minh được điều cần chứng minh" — nếu không chủ động nhắm vào vùng dữ liệu đang được đánh giá, kết quả có thể hoàn toàn vô nghĩa dù code không có lỗi.
2. **Về data quality/observability:** Các loại corruption khác nhau kích hoạt các tầng quan sát khác nhau (structural vs temporal) — thiết kế corruption cần đa dạng loại để bao phủ được nhiều lớp quality signal, không nên chỉ tập trung một loại.
3. **Về ảnh hưởng của data đến RAG agent:** Trường dữ liệu càng gần với đường đi trực tiếp tới câu trả lời của agent (như `summary`) thì corruption vào trường đó càng gây tác động lớn; trường chỉ phục vụ observability phụ (như `published`) có tác động gián tiếp và nhỏ hơn nhiều.

### Nếu có thêm thời gian

Sẽ thêm một kịch bản corruption "swap fields" — hoán đổi `summary` giữa hai bài báo khác nhau (thay vì xóa trắng hoặc thêm nhiễu) để mô phỏng lỗi ETL thực tế dạng "gán nhầm dữ liệu", đo tác động bằng cách kiểm tra xem `retrieval_hit_rate` có giảm mạnh hơn kịch bản blank summary hay không — vì swap tạo ra nội dung nhìn có vẻ hợp lệ (không rỗng, không có ký tự rác) nhưng sai hoàn toàn về ngữ nghĩa, có thể là dạng lỗi khó phát hiện nhất bằng quality check dạng structural.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Phạm Hải Yến
**Ngày xác nhận:** 2026-08-06
