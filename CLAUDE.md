# CLAUDE.md — AI Gateway & SEO Automation (365Group / Auto365.vn)

> File này là hợp đồng vận hành cho mọi agent (Claude/Codex) làm việc trong repo.
> Đọc hết trước khi viết dòng code đầu tiên. Không override các mục [BẤT BIẾN].

---

## 1. DỰ ÁN LÀ GÌ / KHÔNG LÀ GÌ

**Là:** lớp tự động hoá quy trình SEO 3M cho Auto365.vn. Google Sheet điều hành → n8n điều phối → OpenAI phân tích/soạn → **AI Gateway (repo này)** giữ quyền + audit → CMS staging → người duyệt → production.

**KHÔNG là:**
- Không phải CMS. Repo CMS Auto365 là hệ thống ngoài, kết nối qua API (xem §7 Blocker #1).
- Không phải nơi chứa nội dung bài viết. Chỉ chứa Gateway + gate engine + state machine.
- Gateway **KHÔNG** có tài khoản admin CMS, **KHÔNG** có quyền database CMS.

**Mức tự động mục tiêu: ~70–80%.** GPT KHÔNG tự quyết publish, 301, canonical, noindex, hay thay đổi thông số sản phẩm. Ranh giới này được mã hoá ở DB (`automation_level`) + Gateway, không phải quy ước.

---

## 2. KIẾN TRÚC ĐÃ CHỐT [BẤT BIẾN]

```
Google Sheet (control plane — KHÔNG phải SSOT trạng thái)
   ↕ sync 2 chiều
DB STATE MACHINE (Postgres/Supabase) — SSOT TRẠNG THÁI
   work_items · runs · releases · approvals · claims · gates · audit_log
   ↓
n8n (điều phối + lịch + retry · dry_run mặc định)
   ↓
AI GATEWAY (repo này) — ĐIỂM GHI DUY NHẤT · xác thực · scope · audit · cost/rate guard
   ├── OpenAI Responses API (function calling strict:true)
   ├── Google Sheets / Drive API
   ├── GSC + GA4 API
   ├── Crawler
   ├── SSOT giá/TDS/bảo hành (versioned)      ← Blocker #2
   └── CMS write path                          ← Blocker #1
   ↓
GATE ENGINE (eval tự động, chặn cứng) → fail = không được request-approval
   ↓ pass
Cổng phê duyệt (người · danh tính đã xác minh)  ← Blocker #3
   ↓
CMS Production (chỉ allow-list release · drift-guard trước ghi)
   ↓
QA hậu triển khai (D+1/3/7/14/28) + audit_log append-only
```

Nguyên tắc kết nối:
- **REST + webhook**: cổng chính cho n8n.
- **Function calling (strict:true)**: cổng để model gọi từng chức năng được phép, output theo JSON Schema.
- **MCP**: chỉ bổ sung cho nhân sự vận hành ra lệnh bằng ngôn ngữ tự nhiên. Không thay REST production.
- **Browser automation**: chỉ kiểm tra render/CTA/schema. Không dùng cập nhật CMS.

---

## 3. TECH STACK & RUNTIME

- Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 (khớp 365crm-mkt — không học stack mới).
- PostgreSQL 16 / Supabase cho state machine.
- Gate engine: pure functions, không phụ thuộc web framework, test bằng pytest.
- **KHÔNG** chạy n8n/Gateway cùng box aaPanel production PHP. Deploy Docker trên VPS riêng hoặc n8n Cloud.

---

## 4. MỨC PHÂN QUYỀN [BẤT BIẾN — KHÔNG NỚI]

Ánh xạ vào cột `work_items.automation_level` và `releases.automation_level`.

| Mức (`automation_level`) | Công việc | Cần duyệt |
|---|---|---|
| `AUTO` | Crawl URL; kiểm status/canonical/robots/title/schema/sitemap; kéo GSC/GA4; phát hiện cannibalization; phát hiện claim thiếu nguồn; cập nhật dashboard; cảnh báo; theo dõi D+1/3/7/14/28 | 0 người |
| `ONE_APPROVER` | Content brief, outline, nháp, title/meta, FAQ+schema, internal link, hợp nhất nội dung, sửa bài staging, đề xuất URL owner + redirect | 1 người |
| `TWO_APPROVER` | 301, canonical, noindex, 410; đổi URL owner; publish pillar/money page; cập nhật giá/TDS/bảo hành; xử lý chéo 3 domain; rollback | SEO Owner + Dev |
| `FORBIDDEN` | Xoá URL; GSC Removals; sửa DB trực tiếp; thay config server; dùng thông số không có SSOT; quyết định CR BLK Pro GO/MERGE | Không giao AI |

---

## 5. ĐIỀU KIỆN AN TOÀN BẮT BUỘC [BẤT BIẾN]

Trạng thái enforce: ✅ = đã enforce ở DB (`migrations/0001`), ⏳ = enforce ở Gateway/n8n (chưa build).

1. ✅ `dry_run: true` mặc định mọi workflow. Apply = hành động tường minh có `Release_ID`.
2. ⏳ Tách token staging/production. Credential chỉ trong secret manager / n8n credentials — **không** trong prompt, không trong Sheet.
3. ✅/⏳ Mọi thay đổi có `Task_ID`, `Run_ID`, `Release_ID`, approver đã xác minh, snapshot before/after.
4. ✅ Idempotency key mọi lệnh ghi (`runs.idempotency_key` unique).
5. ⏳ Chỉ sửa URL trong `releases.allow_list` của release đó.
6. ⏳ **Drift guard**: lưu `content_hash` production lúc tạo draft; lúc apply hash khác ⇒ từ chối, re-base. Không đè.
7. ⏳ Pin `model_id` + `prompt_version` + `schema_version` mỗi run. Cấm alias "latest".
8. ⏳ Webhook: verify chữ ký + timestamp tolerance + lưu `event_id` (chống replay). Trả 2xx nhanh, xử lý async.
9. ⏳ Cost/rate guard: budget theo run + ngày. Quota GSC ngày, Sheets API 60 req/phút. Đụng ngưỡng ⇒ dừng + báo, không degrade âm thầm.
10. ✅/⏳ Rollback áp `snapshot_before` — **không** tái sinh nội dung bằng AI.
11. ✅ "Approved" trong Sheet KHÔNG phải quyền xuất bản. Gateway tự xác minh danh tính approver (`approvals.verified_via`).

Ngoài ra, 4 luật bất biến đã enforce ở DB (test pass, xem `migrations/0001`):
- **Audit append-only** — trigger chặn UPDATE/DELETE trên `audit_log`.
- **No self-approval** — approver ≠ DRI của work_item (constraint + trigger).
- **Claim LOCKED phải đủ nguồn** — không LOCKED khi thiếu source/effective_date/reviewer.
- **Idempotency** — `runs.idempotency_key` unique.

---

## 6. GATE ENGINE — RULE [BẤT BIẾN]

Ngữ nghĩa severity: **blocking-gate (`is_blocking=true`) fail = không được request-approval**; **advisory-gate (`is_blocking=false`) fail = cảnh báo, không chặn**; **`blocked` = cần người** (thiếu nguồn ngoài, gate không phán xét). `is_blocking` là NGUỒN severity, khớp cột `gates.is_blocking` trong DB (`migrations/0001`, DEFAULT true) — status chỉ nói *có vi phạm hay không*, việc chặn do consumer tính = `status=="fail" AND is_blocking`.

Mỗi gate là pure function: `in {body_html, jsonld, meta}` → `out {rule_id, status: pass|fail|blocked, violations[]}`. Dọn span lồng nhau do CKEditor sinh **trước** khi diff/eval (không tính vi phạm). Chữ ký ổn định để `POST /gates/evaluate` gọi lại.

| rule_id | Nội dung | Loại |
|---|---|---|
| G1_superlatives | Cấm tuyệt đối/so-sánh-nhất ("toàn diện nhất","tối ưu hoá","số 1","duy nhất") | linguistic |
| G2_claim_provenance | Số liệu giá/thông số/bảo hành phải có `claim_id`→SSOT. **SSOT chưa có (Blocker #2) ⇒ chạy dạng DETECTOR, không tính FP** | detector |
| G3_product_version | Không gộp thông số/giá giữa phiên bản năm (2023≠2026) | heuristic/warn |
| G4_faq_1to1 | FAQ HTML khớp 1:1 `acceptedAnswer` JSON-LD | schema-dependent |
| G5_schema_entity | @graph khớp DOM/URL thật; dual-typing khi cần; không bịa entity | structural |
| G5b_no_speakable | Cấm `speakable` (không hỗ trợ tiếng Việt) | structural |
| G6_table_a11y | Bảng có `<thead>` + `scope="col"` | structural |
| G7_no_h1_in_body | Body KHÔNG chèn `<h1>` (H1 ở template CMS) | structural |
| G7b_inline_style | Dùng inline style, không class (CMS lột class) | warn |
| G8_eeat | Có tác giả thật + nguồn dẫn + ngày cập nhật | structural |
| G9_no_raw_script | Không `<script>` raw trong body (bắt AdSense `ca-pub-1256170089840912`) | structural |

Phase 2 (gate) phải xong **trước** Phase 3 (draft bot). Xây gate sau draft = không có chuẩn đánh giá draft.

---

## 7. BLOCKER HIỆN TẠI [CẬP NHẬT KHI ĐỔI]

Trạng thái từ audit repo CMS + audit Google Sheet "Control Room 3M".

### Blocker #1 — CMS không có staging / REST ghi → chặn Phase 3–4
FACT: đường ghi = `myadmin/index_ajax.php` (admin ajax nội bộ), auth = session cookie `PHPSESSID_ADMIN`, **không** Bearer/API-key. Không có staging tách biệt; "draft" duy nhất = `status=0` + `time_publish` tương lai.
Cần Dev chốt: build thin REST wrapper trong Gateway gọi lại DAO tạo `status=0` draft, hay tách staging thật? Endpoint ajax có check permission trước khi ghi không?

### Blocker #2 — SSOT giá/TDS/bảo hành chưa đạt chuẩn → chặn Phase 3
FACT: `stg_product_film_prices`/`stg_products` có giá nhưng **không version, không effective_date, không product_version(năm), ghi đè**. Evidence Register trong Sheet: `PRICE_2026_OWNER`, `CRBLK40_UVR` = `PENDING_SOURCE`/`CẦN GẮN`.
Hệ quả: chưa có `claim_id` bất biến ⇒ mọi draft chứa số liệu FAIL gate G2. Bảng `claims` (migrations/0001) đã sẵn schema versioned; cần **người** nhập + khoá version.

### Blocker #3 — Xác thực approver chưa chốt → cổng duyệt vô nghĩa
FACT: admin auth = `password_verify` + captcha; Google OAuth chỉ cho khách frontend. Sheet `00_CONTROL`: `PROGRAM_OWNER`, `SEO_LEAD`, `DEV_LEAD`, `MEDIA_LEAD`, `PRICE_SIGNER` = **CẦN GÁN TÊN** (4/5 role P0 trống).
Khuyến nghị: Gateway mint JWT ngắn hạn ký lúc duyệt, gắn `approver_id`, cộng Google OAuth giới hạn domain `365group.com.vn` cho mức 2-người.

---

## 8. DB STATE MACHINE

Nguồn schema = audit Google Sheet (WORK ITEMS → `work_items`, 04_GATES → `gates`, 05_EVIDENCE_REGISTER → `claims`, CHANGELOG → `audit_log`). Migration: `migrations/0001_init_state_machine.sql` (đã apply-test trên PG 16, 4 luật bất biến pass).

Sheet là **view**, DB là **SSOT**. `WF-01` sync Sheet→DB (upsert bằng `row_hash`), `WF-02` render DB→Dashboard.

---

## 9. LỘ TRÌNH [BẤT BIẾN thứ tự Phase 2 trước 3]

| Phase | Nội dung | Điều kiện thoát | Blocker |
|---|---|---|---|
| 0 | DB state machine + audit + claims schema | Sheet↔DB sync ổn định, không mất trạng thái khi song song | — ✅ migration DONE |
| 1 | Read-only bot: crawl, GSC/GA4, detect, alert | 7 ngày không false-positive nghiêm trọng | — |
| 2 | Gate engine chạy trên corpus bài cũ | Gate bắt lỗi thật; false-positive dưới ngưỡng | — |
| 3 | Draft bot → staging (chưa publish) | Tỷ lệ draft qua gate không sửa tay đạt mục tiêu | #1, #2 |
| 4 | Controlled deployment + QA + rollback | Diễn tập rollback thành công trên staging | #1, #3 |
| 5 | Mở rộng MCP cho đội vận hành | Vẫn đi qua cùng lớp quyền | — |

---

## 10. MÔI TRƯỜNG SERVER (CMS ngoài)

- aaPanel, đa PHP (80/82/84). Luôn gọi binary theo phiên bản: `/www/server/php/82/bin/php artisan ...`. Không dùng `php` mặc định CLI.
- Kiểm tra entry trùng trong `php.ini` trước khi reload FPM (entry trùng làm mọi directive sau ngưng nạp, kể cả extension).
- `APP_DEBUG=false` trên production.
- Backup site: `/www/backup/site/<project>`.

---

## 11. CÁCH LÀM VIỆC [BẤT BIẾN]

- Đọc README, config, tài liệu audit **trước** khi đề xuất. Mặc định read-only và audit trước.
- **KHÔNG** tự commit, push, merge, migrate, restart service, sửa cron production.
- Repo grep/search trước khi mở file tuần tự. Không quét lại toàn repo nếu audit đã chỉ file mục tiêu.
- Dùng Plan Mode trước implementation. Nhiều nhánh độc lập ⇒ sub-agent song song, không 2 agent sửa cùng file.
- Sửa bug theo TDD: fixture tái hiện lỗi → confirm fail → sửa tối thiểu → chạy lại đến pass.
- Mọi kết luận có evidence: file/path/line, log, raw response, hoặc output test. Phân biệt **FACT / INFERENCE / BLOCKER**.
- DB CMS: read-only tuyệt đối. `SELECT DATABASE()` verify context trước mọi query. Chỉ SELECT + information_schema.
- `web_fetch` markdown lột `<script>` — soi injection/schema phải đọc raw HTML hoặc field DB.
- Trước khi báo DONE: chạy test liên quan, `python -m py_compile` / `php -l`, shell syntax check, dry-run, git diff review. **Không DONE nếu chưa có test evidence thật.**
- Output ưu tiên: checklist, bảng before/after, phase plan, trạng thái `DONE / PARTIAL / BLOCKED / NOT STARTED`.
- Gặp blocker: hoàn thành phần không bị chặn, ghi blocker + evidence + impact + next smallest action.
- Thực thi theo lô, báo cáo một lần ở cuối. Không câu kết xã giao. Không tạo artifact lớn trừ khi yêu cầu rõ.

---

## 12. DEFINITION OF DONE

Một task chỉ DONE khi: (a) có test evidence thật (output test/dry-run/query); (b) không vi phạm mục [BẤT BIẾN] nào; (c) syntax check pass; (d) git diff đã review; (e) blocker (nếu có) đã ghi kèm impact + next action. Thiếu bất kỳ ⇒ trạng thái là PARTIAL hoặc BLOCKED, không phải DONE.
