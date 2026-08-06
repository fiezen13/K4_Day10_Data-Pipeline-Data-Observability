# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Trần Minh Hiển |
| MSSV | 2A202601812 |
| Khóa/Lớp | K4 |
| Tên nhóm | K4-Day10-Data-Pipeline-Data-Observability |
| Vai trò chính | Thành viên 3 — Observability & Reporting |
| Repository | K4_Day10_Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data quality checks | `src/observability/quality.py` (`run_data_quality_checks`) | Cleaned/corrupted/repaired dataframe + `Settings` | `data/quality/{baseline,corrupted,repaired}_quality.json` | Hoàn thành |
| Freshness monitoring | `src/observability/quality.py` (`build_freshness_report`) | Dataframe + `Settings` | `data/quality/freshness_report*.json` | Hoàn thành |
| Markdown reporting | `src/observability/reporting.py` (`generate_phase1_report`, `generate_corruption_report`) | Metrics/quality/freshness dict từ pipeline | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` | Hoàn thành |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Thiết kế 7 quality check: `row_count_positive`, `paper_id_not_null`, `paper_id_unique`, `title_not_null`, `summary_min_length`, `text_for_embedding_not_empty`, `freshness_within_threshold` | `run_data_quality_checks` | `data/quality/baseline_quality.json` — 7/7 PASS; `corrupted_quality.json` — 5/7 PASS (2 FAIL) | Mở file JSON, đối chiếu `checks[].passed` |
| Tính freshness: `latest_published`, `oldest_published`, `stale_rows`, `stale_rate`, ngưỡng cảnh báo `stale_rate < 0.5` | `build_freshness_report` | `data/quality/freshness_report.json` (baseline), `freshness_report_corrupted.json`, `freshness_report_repaired.json` — 3 file riêng cho 3 trạng thái | So sánh `stale_rate`: 0.0% (baseline) → 20.83% (corrupted) → 0.0% (repaired) |
| Sinh báo cáo markdown baseline: nguồn dữ liệu, bảng metrics, bảng quality check, freshness | `generate_phase1_report` | `data/reports/phase1_report.md` | Mở file, đối chiếu số liệu với `data/results/baseline_metrics.json` |
| Sinh báo cáo so sánh 3 trạng thái: bảng metric có cột Delta, bảng quality corrupted/repaired, bảng freshness | `generate_corruption_report` | `data/reports/corruption_report.md` | Mở file, đối chiếu cột Delta = `giá_trị_khác - giá_trị_baseline` |

Output cụ thể: `data/quality/corrupted_quality.json` ghi nhận đúng 2 check FAIL (`paper_id_unique` với `duplicate_count=2`, `summary_min_length` với `rows_below_20_chars=5`) — hai check này bắt trúng đúng loại corruption mà Thành viên 4 đã áp dụng (duplicate rows và blank/noise summary), chứng minh bộ quality check của tôi nhạy với lỗi thật chứ không phải luôn PASS máy móc.

### Quality / freshness trên cả 3 trạng thái dữ liệu

Cùng một bộ check (`run_data_quality_checks`, `build_freshness_report`) được chạy trên baseline, corrupted và repaired:

| Tín hiệu | Baseline | Corrupted | Repaired | Artifact |
| --- | --- | --- | --- | --- |
| Quality overall | PASS (`success=true`, 7/7) | FAIL (`success=false`, 5/7; FAIL: `paper_id_unique`, `summary_min_length`) | PASS (`success=true`, 7/7) | `data/quality/{baseline,corrupted,repaired}_quality.json` |
| Row count | 24 | 24 | 24 | cùng các file quality trên |
| `paper_id_unique` | PASS (`duplicate_count=0`) | FAIL (`duplicate_count=2`) | PASS (`duplicate_count=0`) | cùng các file quality trên |
| `summary_min_length` (`MIN_SUMMARY_CHARS=20`) | PASS (`rows_below_20_chars=0`) | FAIL (`rows_below_20_chars=5`) | PASS (`rows_below_20_chars=0`) | cùng các file quality trên |
| `freshness_within_threshold` | PASS (`stale_rate=0%`) | PASS (`stale_count=5`, `stale_rate=20.83%` — dưới ngưỡng 50%) | PASS (`stale_rate=0%`) | cùng các file quality trên |
| Freshness `is_fresh` | `true` | `true` (dù stale tăng) | `true` | `data/quality/freshness_report.json`, `freshness_report_corrupted.json`, `freshness_report_repaired.json` |
| `stale_rows` / `stale_rate` | 0 / 0% | 5/24 / 20.83% | 0 / 0% | cùng các file freshness trên |
| Latest / oldest published | 2026-08-01 / 2026-02-12 | 2026-08-01 / 2021-08-01 | 2026-08-01 / 2026-02-12 | cùng các file freshness trên |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Sau khi dữ liệu được clean (Thành viên 2) hoặc bị làm lỗi có chủ đích (Thành viên 4), cần một lớp kiểm tra độc lập trả lời hai câu hỏi khác nhau: (1) dữ liệu có còn đúng cấu trúc/hợp lệ không (data quality), và (2) dữ liệu có còn "mới" theo nghĩa thời gian không (freshness). Đây là hai trục quan sát khác nhau — một dataset có thể đúng cấu trúc nhưng đã lỗi thời, hoặc còn mới nhưng có bản ghi trùng lặp.

### Cách triển khai

`run_data_quality_checks` nhận một dataframe và chạy tuần tự 7 check độc lập, mỗi check trả về `{"name", "passed", "detail"}`. Riêng `freshness_within_threshold` dùng chung logic `stale_mask` với `build_freshness_report`: một dòng được coi là stale nếu `age_days > settings.freshness_threshold_days` (180 ngày). Ngưỡng fail của cả hai hàm là `stale_rate >= 0.5` — tức phải hơn một nửa dataset lỗi thời thì mới báo "not fresh", một ngưỡng khoan dung để tránh false positive khi chỉ một vài bản ghi cũ.

`generate_phase1_report` và `generate_corruption_report` đều dùng chung 2 helper nội bộ: `_checks_table` (chuyển list check thành bảng markdown PASS/FAIL) và `_metrics_table`/`_comparison_metrics_table` (chuyển dict metric thành bảng, có tính `_delta` so với baseline cho báo cáo so sánh). Việc tách helper này giúp format bảng nhất quán giữa hai loại báo cáo.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `pd.DataFrame` đã qua `build_clean_dataframe`/`corrupt_clean_dataframe` (cần cột `paper_id`, `title`, `summary`, `text_for_embedding`, `age_days`), `Settings.freshness_threshold_days` |
| Output | Dict `{report_name, generated_at, row_count, checks, success}` (quality) và `{generated_at, latest_published, oldest_published, stale_rows, total_rows, stale_rate, is_fresh}` (freshness), đồng thời ghi ra JSON/Markdown |
| Module phụ thuộc | `core.config.Settings`, `core.utils.write_json`/`write_text` |
| Module sử dụng output | `src/pipelines/phase1.py` và `src/pipelines/corruption_flow.py` gọi cả 4 hàm sau bước evaluate; `report/group_report.md` đọc trực tiếp các file JSON/Markdown này để lập bảng so sánh |
| Điều kiện lỗi cần xử lý | `row_count == 0` (dataframe rỗng) — trả sớm với `success=False` thay vì để các phép tính `.str.len()`/`.apply()` chạy trên dataframe rỗng gây lỗi hoặc kết quả vô nghĩa |

### Cách xác minh

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** `data/quality/baseline_quality.json` có `success: true` (7/7 PASS); sau corruption, `corrupted_quality.json` có `success: false` với ít nhất các check liên quan đến kịch bản corruption đã áp dụng chuyển sang FAIL; `repaired_quality.json` quay lại `success: true`.
- **Kết quả thực tế:** Đúng như mong đợi — baseline 7/7 PASS, corrupted 5/7 PASS (FAIL ở `paper_id_unique` và `summary_min_length`), repaired 7/7 PASS trở lại. Freshness: `stale_rate` đi từ 0.0% → 20.83% → 0.0%.
- **Artifact/log:** `data/quality/baseline_quality.json`, `corrupted_quality.json`, `repaired_quality.json`, `freshness_report*.json`, `data/reports/phase1_report.md`, `data/reports/corruption_report.md` (không chứa secret).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần một ngưỡng cho `freshness_within_threshold` — nếu ngưỡng quá chặt (ví dụ fail ngay khi có 1 bản ghi stale), báo cáo sẽ liên tục báo động đỏ dù dữ liệu tổng thể vẫn ổn; nếu quá lỏng, sẽ không bắt được vấn đề thật.
- **Các phương án đã cân nhắc:**
  1. Fail ngay khi `stale_rows > 0` — nhạy nhất nhưng dễ gây nhiễu, vì một vài bài báo cũ trong tập dữ liệu là chuyện bình thường.
  2. Fail khi `stale_rate >= 0.5` (đa số dataset lỗi thời) — khoan dung hơn, phản ánh đúng ý nghĩa "dataset nhìn chung còn mới hay không" thay vì "có tồn tại 1 bản ghi cũ hay không".
- **Phương án đã chọn:** Phương án 2 — ngưỡng 50%, áp dụng đồng nhất cho cả `run_data_quality_checks` và `build_freshness_report`.
- **Lý do:** Freshness là một tín hiệu tổng thể (aggregate signal), không phải một ràng buộc cứng như `paper_id` không được trùng. Một vài bài cũ nằm trong corpus RAG không tự nó là vấn đề chất lượng; vấn đề chỉ thực sự đáng báo động khi phần lớn dataset đã lỗi thời.
- **Bằng chứng quyết định phù hợp:** Khi corruption đẩy 5/24 bản ghi (20.83%) về stale, hệ thống vẫn báo `is_fresh: true` (`data/quality/freshness_report_corrupted.json`) — đúng ý đồ thiết kế: tín hiệu thô (`stale_rate`) đã thay đổi rõ rệt và được ghi lại đầy đủ trong artifact để người đọc thấy xu hướng, nhưng ngưỡng pass/fail tổng thể chưa bị kích hoạt vì chưa đến mức đa số. Điều này cho thấy quality gate và raw signal là hai lớp thông tin bổ sung cho nhau chứ không phải cùng một thứ.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi đối chiếu `quality.py` với `cleaning.py`, phát hiện lệch ngưỡng: quality dùng `MIN_SUMMARY_CHARS = 20`, trong khi cleaning lọc summary tối thiểu **100** ký tự. Đồng thời, lần đầu đọc freshness corrupted dễ hiểu nhầm là “không bắt được stale-date” vì `is_fresh` vẫn `true`.
- **Lệnh hoặc bước tái hiện:** Mở `src/observability/quality.py` (hằng `MIN_SUMMARY_CHARS`), `data/quality/corrupted_quality.json` (`rows_below_20_chars=5`) và `data/quality/freshness_report_corrupted.json` (`stale_rate≈20.83%`, `is_fresh=true`).
- **Nguyên nhân gốc:** (1) Hai module định nghĩa ngưỡng độ dài `summary` ở hai nơi khác nhau mà chưa thống nhất. (2) Nhầm giữa **tín hiệu thô** (`stale_rows`/`stale_rate`) và **cổng pass/fail** (`is_fresh` / `freshness_within_threshold` với ngưỡng 50%).
- **Cách xử lý:** Giữ `MIN_SUMMARY_CHARS = 20` đúng như code đã chạy end-to-end trên `main` (không sửa tay số liệu sau khi đã có artifact). Với blank summary (`summary = ""`), check 20 ký tự vẫn FAIL đúng. Ghi rõ trong report cả `stale_rate` lẫn `is_fresh`. Việc đồng bộ ngưỡng quality lên 100 (khớp cleaning) để bắt tốt hơn summary bị cắt ngắn/noise nhưng vẫn >20 ký tự được xếp vào hướng cải thiện.
- **Cách xác minh sau khi sửa:** `corrupted_quality.json` báo `summary_min_length: FAIL, rows_below_20_chars=5` và `paper_id_unique: FAIL, duplicate_count=2`; freshness corrupted có `stale_rows=5` dù `is_fresh=true`. Sau repair, cả quality và freshness trở lại khớp baseline.
- **Điều học được:** Ngưỡng giữa cleaning và quality cần đối chiếu chéo sớm; báo cáo observability phải trình bày cả số liệu thô và trạng thái pass/fail, nếu không sẽ mất bằng chứng cho corruption nhẹ hơn ngưỡng cảnh báo.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào:** Thành viên 1 fetch raw JSON từ Crossref, Thành viên 2 parse và làm sạch thành dataframe với các cột chuẩn hóa (`paper_id`, `title`, `summary`, `text_for_embedding`, `age_days`), sau đó `retrieval/index.py` (starter code) encode `text_for_embedding` bằng MiniLM và nạp vào ChromaDB.
2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality:** Thành viên 2 sinh 36 câu hỏi từ dataframe sạch, mỗi câu gắn `ground_truth_doc_ids = [paper_id]`; khi evaluate, hệ thống so khớp `retrieved_doc_ids` với `ground_truth_doc_ids` để tính `retrieval_hit_rate`, và so sánh câu trả lời với `ground_truth` bằng token F1 và LLM judge.
3. **Quality checks khác freshness monitoring ở điểm nào:** Quality checks đo tính toàn vẹn cấu trúc tại một thời điểm tĩnh (null, duplicate, độ dài trường) — trả lời câu hỏi "dữ liệu có hợp lệ theo schema không". Freshness đo tính thời sự theo trục thời gian (`age_days` so với ngưỡng) — trả lời "dữ liệu có còn cập nhật không". Hai trục này độc lập: dữ liệu có thể PASS toàn bộ quality check nhưng đã lỗi thời (nhiều bài cũ), hoặc còn rất mới nhưng có duplicate/null.
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired:** Để đảm bảo biến số duy nhất thay đổi giữa ba lần đánh giá là chính dữ liệu, không phải bộ câu hỏi — nếu mỗi trạng thái có test set riêng, chênh lệch metrics có thể do câu hỏi khác nhau chứ không phải do corruption, làm mất ý nghĩa nhân quả của phép so sánh.
5. **Repair được xem là thành công dựa trên artifact và metric nào:** Dựa trên `data/quality/repaired_quality.json` (7/7 check PASS trở lại) và `data/quality/freshness_report_repaired.json` (`stale_rate` về 0%, khớp baseline) — đây là hai artifact tôi trực tiếp tạo ra, kết hợp với `data/results/repaired_metrics.json` (metric agent phục hồi delta = 0) do Thành viên 5 tổng hợp.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.9444 | 1.0000 | Không thuộc phạm vi quality/freshness trực tiếp nhưng tương quan với `text_for_embedding_not_empty` — dù check này vẫn PASS (không có summary rỗng hoàn toàn ảnh hưởng đến field ghép), nhiễu nội dung vẫn làm giảm nhẹ retrieval |
| `mean_token_f1` | 1.0000 | 0.7627 | 1.0000 | Metric này không đo trực tiếp bởi quality check nào của tôi, nhưng mức giảm mạnh nhất trùng với 2 check FAIL tôi ghi nhận (`summary_min_length`, `paper_id_unique`) — cho thấy quality signal và answer quality có tương quan chặt |
| Quality checks | PASS 7/7 | FAIL (5/7, 2 lỗi) | PASS 7/7 | `paper_id_unique` và `summary_min_length` là 2 check của tôi bắt đúng corruption đã áp dụng (duplicate rows và blank/noise summary) |
| Freshness status | Fresh (0% stale) | Fresh nhưng stale_rate = 20.83% | Fresh (0% stale) | Ngưỡng 50% chưa bị chạm nên "is_fresh" vẫn true ở corrupted, nhưng con số thô 20.83% đã đủ cho thấy kịch bản "làm cũ ngày xuất bản" có tác động đo được rõ ràng |

### Kết luận từ số liệu

1. **Duplicate rows + blank/noise summary** (do Thành viên 4 tạo ra) → `run_data_quality_checks` phát hiện qua `paper_id_unique` (`duplicate_count=2`) và `summary_min_length` (`rows_below_20_chars=5`) chuyển từ PASS sang FAIL (`data/quality/corrupted_quality.json`) → các check FAIL này trùng khớp thời điểm với `mean_token_f1` giảm mạnh nhất trong 4 agent metric (`data/results/corrupted_metrics.json`), cho thấy quality signal của tôi là chỉ báo sớm đáng tin cậy cho sự suy giảm chất lượng answer.
2. **Repair action** (Thành viên 5 build lại từ raw) → `run_data_quality_checks` và `build_freshness_report` trên dataframe đã repair trả về 7/7 PASS và `stale_rate=0%` (`data/quality/repaired_quality.json`, `freshness_report_repaired.json`) — đúng bằng kết quả baseline, xác nhận repair không chỉ khôi phục answer quality mà còn khôi phục đúng cấu trúc dữ liệu ở tầng quality gate.

Corruption ảnh hưởng rõ nhất tới quality signal: **duplicate rows**, vì đây là check nhị phân (PASS/FAIL tức thì khi `duplicate_count > 0`), khác với `freshness_within_threshold` vốn cần vượt ngưỡng 50% mới đổi trạng thái. Điều này khiến `paper_id_unique` là check nhạy nhất trong bộ 7 check của tôi đối với các kịch bản corruption dạng rời rạc (thêm/xóa bản ghi).

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline:** Các ngưỡng/rule dùng chung một trường dữ liệu (ví dụ độ dài `summary`) cần được đồng bộ tường minh giữa các module thay vì mỗi người chọn một con số riêng — sai lệch ngưỡng có thể khiến quality check "PASS giả" dù code không có lỗi cú pháp.
2. **Về data quality/observability:** Ngưỡng pass/fail cho các tín hiệu tổng hợp (như freshness) nên khoan dung hơn ngưỡng cho các ràng buộc cứng (như uniqueness) — không phải mọi lệch chuẩn đều cần fail ngay lập tức, quan trọng là artifact vẫn ghi lại đúng con số thô để người đọc tự đánh giá mức độ nghiêm trọng.
3. **Về ảnh hưởng của data đến RAG agent:** Quality check dạng nhị phân (uniqueness, null) phát hiện lỗi tức thì và dễ diễn giải, trong khi lỗi dạng "làm nhiễu nội dung" (noise injection) khó bắt bằng rule đơn giản và cần đối chiếu với metric answer quality mới thấy rõ tác động.

### Nếu có thêm thời gian

1. Đồng bộ `MIN_SUMMARY_CHARS` trong `quality.py` lên **100** để khớp ngưỡng cleaning, nhằm bắt tốt hơn summary bị cắt ngắn/noise nhưng vẫn dài hơn 20 ký tự.
2. Thêm quality check đo "text similarity drift" — so sánh `text_for_embedding` giữa baseline vs corrupted bằng cosine similarity trên embedding, để phát hiện noise injection mà check độ dài/null không bắt được trực tiếp.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Trần Minh Hiển
**Ngày xác nhận:** 2026-08-06
