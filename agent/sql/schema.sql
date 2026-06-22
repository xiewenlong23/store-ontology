-- v2-存储 PG schema（roadmap §1）
--
-- 设计：关系列存核心查询字段（高效 CRUD），JSONB 存复杂结构（parameters/side_effects/
-- properties 列表）。pgvector 扩展启用但本轮不用（预留 embedding 列做未来 RAG）。
--
-- 与现有 ObjectType/LinkType/PropertyDef/ActionDefinition dataclass 一一对应。

-- ============ 扩展 ============

CREATE EXTENSION IF NOT EXISTS vector;
-- 注释：未来 RAG 时启用 entities.embedding vector(1536) 列 + ivfflat 索引

-- ============ 本体 schema：Object Type ============

CREATE TABLE IF NOT EXISTS object_types (
    workspace_name         text NOT NULL,
    name                   text NOT NULL,           -- PascalCase，如 NearExpiryProduct
    label                  text,                    -- 含中英："中文名 (English)"
    label_zh               text,
    comment                text,
    storage_file           text,                    -- 旧 JSON 时代的文件名；PG 后保留兼容
    status                 text NOT NULL DEFAULT 'active',
    visibility             text NOT NULL DEFAULT 'normal',
    edits_only_via_actions boolean NOT NULL DEFAULT false,
    -- v2 权限元数据（与 parser.py ObjectType dataclass 对齐）
    read_roles             text NOT NULL DEFAULT '',
    read_except            text NOT NULL DEFAULT '',
    write_roles            text NOT NULL DEFAULT '',
    write_except           text NOT NULL DEFAULT '',
    PRIMARY KEY (workspace_name, name)
);

-- Object Type 的属性（一对一关系；properties 是个 list）
CREATE TABLE IF NOT EXISTS object_type_properties (
    workspace_name     text NOT NULL,
    object_type_name   text NOT NULL,
    name               text NOT NULL,               -- snake_case 属性名
    type               text NOT NULL,               -- string/int/float/bool/date/datetime/enum/dict
    -- v2 属性级权限元数据
    read_roles         text NOT NULL DEFAULT '',
    read_except        text NOT NULL DEFAULT '',
    write_roles        text NOT NULL DEFAULT '',
    write_except       text NOT NULL DEFAULT '',
    ordinal            integer NOT NULL,            -- 属性顺序（保持 TTL 定义顺序）
    PRIMARY KEY (workspace_name, object_type_name, name),
    FOREIGN KEY (workspace_name, object_type_name)
        REFERENCES object_types (workspace_name, name)
        ON DELETE CASCADE
);

-- ============ 本体 schema：Link Type ============

CREATE TABLE IF NOT EXISTS link_types (
    workspace_name   text NOT NULL,
    name             text NOT NULL,                 -- snake_case，如 has_employee
    label            text,
    label_zh         text,
    comment          text,
    domain           text NOT NULL,                 -- 源 Object Type
    range            text NOT NULL,                 -- 目标 Object Type
    via              text NOT NULL,                 -- 外键字段名
    use_roles        text NOT NULL DEFAULT '',      -- v2 Link 级遍历权限
    use_except       text NOT NULL DEFAULT '',
    PRIMARY KEY (workspace_name, name)
);

-- ============ 本体 schema：Action Type ============

CREATE TABLE IF NOT EXISTS action_types (
    workspace_name        text NOT NULL,
    api_name              text NOT NULL,            -- snake_case，如 create_clearance_task
    display_name          text,
    description           text,
    status                text NOT NULL DEFAULT 'active',
    target_object_type    text NOT NULL,
    edits_object_types    text[] NOT NULL DEFAULT '{}',  -- PG 原生数组（provenance）
    locator_field         text,                     -- 数据驱动定位键
    -- 复杂结构用 JSONB（与 ActionDefinition dataclass 对齐）
    parameters            jsonb NOT NULL DEFAULT '[]',         -- List[dict]
    submission_criteria   jsonb NOT NULL DEFAULT '{}',         -- dict {roles, conditions}
    side_effects          jsonb NOT NULL DEFAULT '[]',         -- List[dict]
    PRIMARY KEY (workspace_name, api_name)
);

-- ============ 业务数据（generic JSONB）============

CREATE TABLE IF NOT EXISTS entities (
    workspace_name   text NOT NULL,
    object_type      text NOT NULL,                 -- 引用 object_types.name（软引用，不强约束）
    id               text NOT NULL,
    org_unit_id      text NOT NULL DEFAULT '*',     -- OrgTree 节点 id；'*' = 共享/总部
    data             jsonb NOT NULL,                -- 全字段（含 id/workspace_name/org_unit_id 冗余）
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    -- embedding      vector(1536),                -- 预留：未来 RAG（本轮注释掉）
    PRIMARY KEY (workspace_name, object_type, id)
);

-- TenantContext 过滤索引：workspace + org_unit_id 是最常见的 WHERE 组合
CREATE INDEX IF NOT EXISTS idx_entities_workspace_org
    ON entities (workspace_name, org_unit_id);

-- JSONB 内字段查询索引（GIN，支持 filters 精确匹配）
CREATE INDEX IF NOT EXISTS idx_entities_data_gin
    ON entities USING gin (data jsonb_path_ops);

-- ============ 索引：按 workspace 列举常用 ============

CREATE INDEX IF NOT EXISTS idx_object_types_workspace
    ON object_types (workspace_name);
CREATE INDEX IF NOT EXISTS idx_link_types_workspace
    ON link_types (workspace_name);
CREATE INDEX IF NOT EXISTS idx_action_types_workspace
    ON action_types (workspace_name);

-- ============ updated_at 自动更新触发器 ============

CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_entities_touch ON entities;
CREATE TRIGGER trg_entities_touch
    BEFORE UPDATE ON entities
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
