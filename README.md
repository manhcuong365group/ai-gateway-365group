# AI Gateway & SEO Automation — 365Group / Auto365.vn

Lớp giữ quyền + audit + gate cho quy trình tự động hoá SEO 3M. **Đọc `CLAUDE.md` trước.**

## Trạng thái
- Phase 0 — DB state machine: **DONE** (`migrations/0001_init_state_machine.sql`, 4 luật bất biến pass trên PG 16).
- Phase 2 — Gate engine: **PARTIAL** (4 gate structural chạy được: G5b, G6, G7, G9. Còn G1–G4, G5, G7b, G8).
- Phase 1/3/4/5: NOT STARTED. Phase 3–4 BLOCKED (#1 CMS staging, #2 SSOT, #3 approver — xem CLAUDE.md §7).

## Cấu trúc
```
CLAUDE.md              # hợp đồng vận hành [đọc trước]
migrations/            # 0001 state machine (7 bảng + 4 trigger/constraint bất biến)
app/gates/             # gate engine — pure functions, không phụ thuộc framework
  base.py              # registry + run_all
  html_utils.py        # dọn span CKEditor trước eval
  rules/               # G5b, G6, G7, G9 (mẫu TDD nhân rộng)
app/routers/           # FastAPI endpoints (chưa build)
tests/                 # pytest per-rule bad/good fixture
n8n/                   # workflow WF-01 Sheet→DB, WF-02 DB→Dashboard (spec)
docs/
```

## Chạy test
```bash
pip install -r requirements.txt
PYTHONPATH=. pytest -q
```

## Apply migration (chỉ khi được duyệt — KHÔNG tự migrate)
```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/0001_init_state_machine.sql
```
