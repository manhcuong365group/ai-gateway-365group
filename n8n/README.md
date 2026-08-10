# n8n workflows (spec — chưa build)

Nguyên tắc: n8n điều phối, KHÔNG giữ credential ghi CMS, KHÔNG tự ghi production.
Credential chỉ trong n8n credential store. Mọi workflow dry_run mặc định.

## WF-01 — Sheet → DB (Schedule 5–15')
Đọc tab WORK ITEMS → upsert `work_items` (idempotent bằng task_id + row_hash).
Đảo chiều SSOT: Sheet thành view, DB thành nguồn thật. Điều kiện thoát Phase 0.

## WF-02 — DB → Dashboard (Schedule)
Đọc DB → ghi lại view read-only vào tab Dashboard. Không nhập trạng thái trên Sheet.

## WF-03 — Crawl+audit (Phase 1, read-only)
Gọi Gateway POST /audit/crawl. Không ghi CMS.

## WF-05 — Gate eval (Phase 2)
work_item → READY_AI ⇒ gọi POST /gates/evaluate. Fail ⇒ set GATE_FAILED, dừng.

## WF-ERR — Error Trigger toàn cục → Slack alert.
