-- ============================================================
-- PostgreSQL Schema — Phase 4.2 / Phase 5
-- HITL 审批记录表 + 审计日志表
-- ============================================================
-- 用法：
--   测试环境：psql $DATABASE_URL -f scripts/migrations/001_audit_and_hitl.sql
--   生产环境：docker-compose exec postgres psql $DATABASE_URL -f /app/migrations/001_audit_and_hitl.sql
-- ============================================================

-- 1. HITL 审批记录表（hitl_approval）
-- 与 TECH 10.1 保持字段一致：task_id / task_type / approver_id / decision
CREATE TABLE IF NOT EXISTS hitl_approval (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         TEXT        NOT NULL,
    task_type       TEXT        NOT NULL,  -- discount | task | display（来自 TECH 10.1）
    approver_id     TEXT        NOT NULL,
    approver_role   TEXT        NOT NULL,  -- store_manager | headquarters
    decision        TEXT        NOT NULL,  -- approve | edit | reject
    original_params JSONB,                  -- 审批前的原始参数（如折扣率）
    final_params    JSONB,                  -- 审批后的最终参数（如修改后的折扣率）
    rejection_reason TEXT,
    payload_hash    TEXT,                   -- 防篡改 hash
    comment         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. 审计日志表（audit_log）
CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      TEXT        NOT NULL,
    user_id         TEXT        NOT NULL,
    store_id        TEXT        NOT NULL,
    action          TEXT        NOT NULL,
    payload         JSONB       NOT NULL,
    output_hash     TEXT        NOT NULL,  -- SHA256(payload || secret_key)
    duration_ms     INTEGER,
    model          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. 索引
CREATE INDEX IF NOT EXISTS idx_hitl_approval_task_id ON hitl_approval(task_id);
CREATE INDEX IF NOT EXISTS idx_hitl_approval_approver ON hitl_approval(approver_id);
CREATE INDEX IF NOT EXISTS idx_hitl_approval_created ON hitl_approval(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_session ON audit_log(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at DESC);

-- 4. RLS 策略（行级安全，多租户隔离）
ALTER TABLE hitl_approval ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log    ENABLE ROW LEVEL SECURITY;

-- 总部可见所有数据，店长只能看本店
CREATE POLICY hitl_approval_select ON hitl_approval
    FOR SELECT USING (
        current_setting('app.user_role', true) = 'headquarters'
        OR current_setting('app.store_id', true) = 'STORE_001'  -- TODO: 动态判断
    );

CREATE POLICY audit_log_select ON audit_log
    FOR SELECT USING (
        current_setting('app.user_role', true) = 'headquarters'
        OR current_setting('app.store_id', true) = 'STORE_001'  -- TODO: 动态判断
    );

COMMENT ON TABLE hitl_approval IS 'HITL人工审批记录，防止篡改';
COMMENT ON TABLE audit_log    IS 'Agent调用和工具执行审计日志';
