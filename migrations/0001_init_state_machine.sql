-- =====================================================================
-- Auto365.vn — AI Gateway / SEO Automation
-- Phase 0: DB State Machine (SSOT trạng thái)
-- Target: PostgreSQL 16 / Supabase
-- Nguồn schema: audit Google Sheet "Control Room 3M"
--   WORK ITEMS -> work_items
--   04_GATES   -> gates + gate_results
--   05_EVIDENCE_REGISTER -> claims (SSOT, versioned)
--   CHANGELOG  -> audit_log (append-only)
--
-- 4 LUẬT BẤT BIẾN được enforce ở tầng DB (không chỉ policy):
--   1. audit_log APPEND-ONLY  (chặn UPDATE/DELETE bằng trigger)
--   2. NO SELF-APPROVAL       (approver != DRI của work_item)
--   3. IDEMPOTENCY            (unique key trên runs, chống chạy trùng)
--   4. DRY_RUN mặc định TRUE  (apply phải là hành động tường minh)
--
-- Ghi chú vận hành: file để REVIEW. KHÔNG tự apply lên production.
-- =====================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

-- ---------------------------------------------------------------------
-- ENUMS (khớp giá trị trong CONFIG tab của sheet)
-- ---------------------------------------------------------------------
CREATE TYPE workflow_status AS ENUM (
  'NOT_STARTED','READY','IN_PROGRESS','IN_REVIEW','READY_AI',
  'GATE_FAILED','READY_FOR_APPROVAL','BLOCKED','DEFERRED','CANCELLED','DONE'
);

CREATE TYPE qa_result AS ENUM ('NOT_TESTED','PASS','FAIL','N/A');

CREATE TYPE blocker_code AS ENUM (
  'NONE','SSOT_DATA','GSC_DATA','EVIDENCE','DEPENDENCY',
  'APPROVAL','NAMING','TECH','LEGAL','DOMAIN_CONFLICT'
);

CREATE TYPE data_lane AS ENUM ('OFFICIAL_TDS','FIELD_MEASUREMENT','PRICE_MASTER','ENTITY_LOCK');

CREATE TYPE claim_status AS ENUM ('PENDING_SOURCE','PENDING_REVIEW','LOCKED','HOLD_EVIDENCE');

CREATE TYPE release_status AS ENUM (
  'DRAFT','PENDING_APPROVAL','APPROVED','APPLIED','ROLLED_BACK','REJECTED'
);

CREATE TYPE run_status AS ENUM ('PENDING','RUNNING','SUCCEEDED','FAILED','GATE_FAILED');

CREATE TYPE approval_role AS ENUM ('CONTENT_OWNER','SEO_OWNER','DEV_LEAD','TECH_REVIEWER','MEDIA_LEAD','PRICE_SIGNER','PROGRAM_OWNER');

CREATE TYPE approval_decision AS ENUM ('APPROVE','REJECT');

-- Mức phân quyền — mã hoá ranh giới "70-80% tự động" thành dữ liệu, không phải quy ước
CREATE TYPE automation_level AS ENUM (
  'AUTO',          -- tự động hoàn toàn (crawl/audit/GSC/alert)
  'ONE_APPROVER',  -- GPT làm, 1 người duyệt (brief/draft/meta/FAQ/internal link)
  'TWO_APPROVER',  -- 2 người duyệt (301/canonical/noindex/giá/publish money page)
  'FORBIDDEN'      -- cấm giao GPT (xoá URL/Removals/sửa DB/đổi server config)
);

-- ---------------------------------------------------------------------
-- signers: nguồn danh tính approver (Blocker #3 — hiện CẦN GÁN TÊN)
-- ---------------------------------------------------------------------
CREATE TABLE signers (
  signer_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  display_name   text NOT NULL,
  email          text UNIQUE,                     -- ràng buộc domain 365group.com.vn ở tầng Gateway
  roles          approval_role[] NOT NULL DEFAULT '{}',
  is_active      boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE signers IS 'Danh tính người ký. 4/5 role đang trống trong sheet (Blocker #3).';

-- ---------------------------------------------------------------------
-- work_items  <- tab WORK ITEMS
-- ---------------------------------------------------------------------
CREATE TABLE work_items (
  task_id             text PRIMARY KEY,           -- P0-04, MP-03, SUP-05...
  phase               text NOT NULL,              -- P0/P1/P3/POST
  workstream          text,
  content_lane        text,
  task                text NOT NULL,
  url_or_asset        text,
  automation_level    automation_level NOT NULL DEFAULT 'ONE_APPROVER',
  is_critical         boolean NOT NULL DEFAULT false,
  deps                text[] NOT NULL DEFAULT '{}',
  dependencies_clear  boolean NOT NULL DEFAULT false,
  dri_id              uuid REFERENCES signers(signer_id),   -- người chịu trách nhiệm
  approver_id         uuid REFERENCES signers(signer_id),   -- người duyệt dự kiến
  due_offset          integer,                    -- ngày lệch so với LAUNCH_DATE
  due_date            date,
  workflow_status     workflow_status NOT NULL DEFAULT 'NOT_STARTED',
  qa_result           qa_result NOT NULL DEFAULT 'NOT_TESTED',
  blocker_code        blocker_code NOT NULL DEFAULT 'NONE',
  next_action         text,
  acceptance_criteria text,
  deliverable_link    text,
  evidence_link       text,
  -- sync Sheet -> DB
  sheet_row           integer,
  row_hash            text,                        -- idempotent upsert (task_id + row_hash)
  last_update         timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_selfapproval_wi CHECK (approver_id IS NULL OR dri_id IS NULL OR approver_id <> dri_id)
);
CREATE INDEX idx_work_items_status ON work_items(workflow_status);
CREATE INDEX idx_work_items_phase  ON work_items(phase);
COMMENT ON CONSTRAINT chk_selfapproval_wi ON work_items IS 'LUẬT 2: người duyệt không được là DRI của chính task đó.';

-- ---------------------------------------------------------------------
-- claims (SSOT)  <- tab 05_EVIDENCE_REGISTER  (Blocker #2)
--   versioned: mỗi claim_id có nhiều revision, phân biệt theo product_version (năm)
-- ---------------------------------------------------------------------
CREATE TABLE claims (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  claim_id          text NOT NULL,               -- CRBLK40_UVR, PRICE_2026_OWNER...
  evidence_id       text,                         -- E001..E019
  page_url          text,
  claim_text        text NOT NULL,
  claim_type        text,                         -- TDS / PRICE / ENTITY / CASE
  metric            text,
  value             text,
  unit              text,
  sku               text,
  data_lane         data_lane NOT NULL,           -- LUẬT tách làn: OFFICIAL_TDS != FIELD_MEASUREMENT
  source_title      text,
  source_ref        text,                         -- URL / File_ID nguồn khoá
  publisher         text,
  revision_version  text NOT NULL,               -- 'Rev F 08/2025'
  effective_date    date,                         -- BẮT BUỘC có trước khi LOCKED
  product_version   integer,                      -- NĂM sản phẩm: 2023 != 2026
  scope_conditions  text,
  reviewer_id       uuid REFERENCES signers(signer_id),
  review_date       date,
  status            claim_status NOT NULL DEFAULT 'PENDING_SOURCE',
  created_at        timestamptz NOT NULL DEFAULT now(),
  -- một claim_id + product_version + revision là duy nhất (chống trộn phiên bản)
  CONSTRAINT uq_claim_version UNIQUE (claim_id, product_version, revision_version),
  -- không được LOCKED nếu thiếu nguồn/ngày hiệu lực/reviewer
  CONSTRAINT chk_locked_complete CHECK (
    status <> 'LOCKED'
    OR (effective_date IS NOT NULL AND source_ref IS NOT NULL AND reviewer_id IS NOT NULL)
  )
);
CREATE INDEX idx_claims_claimid ON claims(claim_id);
CREATE INDEX idx_claims_status  ON claims(status);
COMMENT ON CONSTRAINT chk_locked_complete ON claims IS 'Claim chỉ LOCKED khi đủ nguồn + effective_date + reviewer. Chặn draft dùng số liệu chưa khoá.';

-- ---------------------------------------------------------------------
-- runs: mỗi lần GPT chạy trên 1 work_item
-- ---------------------------------------------------------------------
CREATE TABLE runs (
  run_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  work_item_id      text NOT NULL REFERENCES work_items(task_id),
  action            text NOT NULL,                -- draft / proposal / audit
  intent            text,
  dry_run           boolean NOT NULL DEFAULT true,          -- LUẬT 4
  status            run_status NOT NULL DEFAULT 'PENDING',
  -- pin version (cấm alias 'latest')
  model_id          text NOT NULL,
  prompt_version    text NOT NULL,
  schema_version    text NOT NULL,
  -- drift guard
  content_hash_before text,                       -- hash production lúc tạo draft
  idempotency_key   text NOT NULL,                -- LUẬT 3
  raw_response      jsonb,
  started_at        timestamptz NOT NULL DEFAULT now(),
  finished_at       timestamptz,
  CONSTRAINT uq_run_idempotency UNIQUE (idempotency_key)
);
CREATE INDEX idx_runs_workitem ON runs(work_item_id);
COMMENT ON CONSTRAINT uq_run_idempotency ON runs IS 'LUẬT 3: chống chạy trùng.';

-- ---------------------------------------------------------------------
-- releases: gói apply lên production, có allow-list + snapshot rollback
-- ---------------------------------------------------------------------
CREATE TABLE releases (
  release_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  work_item_id     text NOT NULL REFERENCES work_items(task_id),
  run_id           uuid REFERENCES runs(run_id),
  automation_level automation_level NOT NULL,     -- quyết định cần mấy người duyệt
  allow_list       text[] NOT NULL DEFAULT '{}',  -- chỉ được sửa URL trong đây
  status           release_status NOT NULL DEFAULT 'DRAFT',
  drift_hash       text,                          -- hash lúc apply, so với content_hash_before
  snapshot_before  jsonb,                         -- để rollback (không tái sinh bằng AI)
  snapshot_after   jsonb,
  created_at       timestamptz NOT NULL DEFAULT now(),
  applied_at       timestamptz,
  CONSTRAINT chk_applied_needs_snapshot CHECK (
    status <> 'APPLIED' OR snapshot_before IS NOT NULL
  )
);
CREATE INDEX idx_releases_status ON releases(status);

-- ---------------------------------------------------------------------
-- approvals: chữ ký đã xác minh danh tính (không phải "Approved" trong Sheet)
-- ---------------------------------------------------------------------
CREATE TABLE approvals (
  approval_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  release_id    uuid NOT NULL REFERENCES releases(release_id),
  signer_id     uuid NOT NULL REFERENCES signers(signer_id),
  role          approval_role NOT NULL,
  decision      approval_decision NOT NULL,
  verified_via  text NOT NULL,                    -- 'google_oauth' / 'jwt' — không phải sheet flag
  signed_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_one_vote_per_signer UNIQUE (release_id, signer_id)
);
CREATE INDEX idx_approvals_release ON approvals(release_id);

-- LUẬT 2 (no self-approval, mức release): approver không được là DRI của work_item
CREATE OR REPLACE FUNCTION trg_no_self_approval() RETURNS trigger AS $$
DECLARE v_dri uuid;
BEGIN
  SELECT wi.dri_id INTO v_dri
  FROM releases r JOIN work_items wi ON wi.task_id = r.work_item_id
  WHERE r.release_id = NEW.release_id;
  IF v_dri IS NOT NULL AND v_dri = NEW.signer_id THEN
    RAISE EXCEPTION 'NO_SELF_APPROVAL: signer % is the DRI of this work_item', NEW.signer_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER approvals_no_self_approval
  BEFORE INSERT OR UPDATE ON approvals
  FOR EACH ROW EXECUTE FUNCTION trg_no_self_approval();

-- ---------------------------------------------------------------------
-- gates  <- tab 04_GATES (định nghĩa) + gate_results (kết quả theo run)
-- ---------------------------------------------------------------------
CREATE TABLE gates (
  rule_id        text PRIMARY KEY,               -- G01..G31 / G1_superlatives...
  gate_type      text,                            -- STRATEGY/PRODUCT/EVIDENCE/CONTENT/TRUST/COMPLIANCE
  scope          text,
  pass_criteria  text NOT NULL,                   -- "PASS khi..." từ sheet
  is_blocking    boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE gate_results (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id        uuid NOT NULL REFERENCES runs(run_id),
  rule_id       text NOT NULL REFERENCES gates(rule_id),
  result        qa_result NOT NULL DEFAULT 'NOT_TESTED',
  violations    jsonb NOT NULL DEFAULT '[]',      -- [{locator, evidence}]
  evaluated_at  timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_gate_per_run UNIQUE (run_id, rule_id)
);
CREATE INDEX idx_gate_results_run ON gate_results(run_id);

-- ---------------------------------------------------------------------
-- audit_log  <- tab CHANGELOG  (LUẬT 1: APPEND-ONLY)
-- ---------------------------------------------------------------------
CREATE TABLE audit_log (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_time    timestamptz NOT NULL DEFAULT now(),
  actor         text NOT NULL,                    -- 'human:ngoctran' / 'agent:gpt' / 'system'
  action        text NOT NULL,
  entity_type   text NOT NULL,                    -- work_item/run/release/claim/gate
  entity_id     text,
  run_id        uuid,
  release_id    uuid,
  change_id     text,                             -- XDOMAIN-SSOT-20260809
  before        jsonb,
  after         jsonb
);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_time   ON audit_log(event_time);

-- LUẬT 1: chặn mọi UPDATE/DELETE trên audit_log
CREATE OR REPLACE FUNCTION trg_audit_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'AUDIT_LOG_APPEND_ONLY: % không được phép trên audit_log', TG_OP;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_no_update
  BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION trg_audit_append_only();

COMMIT;
