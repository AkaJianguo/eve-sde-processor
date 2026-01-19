-- ========================================================
-- EVE SDE 业务视图脚本 (v3.5 物理对齐版)
-- ========================================================

CREATE SCHEMA IF NOT EXISTS public;
SET search_path TO public;

-- 1. 彻底删除旧视图（防止字段类型变更锁定）
DROP VIEW IF EXISTS public.v_items CASCADE;
DROP VIEW IF EXISTS public.v_solar_systems CASCADE;
DROP VIEW IF EXISTS public.v_blueprints CASCADE;
DROP MATERIALIZED VIEW IF EXISTS public.market_menu_tree CASCADE;

-- 2. 物品核心视图 (v_items)
CREATE VIEW v_items AS
SELECT 
    t.id::int AS item_id, -- 物理层 text -> 逻辑层 int
    t.data->'name'->>'zh' AS name_zh,
    t.data->'name'->>'en' AS name_en,
    g.data->'name'->>'zh' AS group_name_zh,
    c.data->'name'->>'zh' AS category_name_zh,
    (t.data->>'mass')::float AS mass,
    (t.data->>'volume')::float AS volume,
    (t.data->>'published')::boolean AS is_published
FROM raw.types t
LEFT JOIN raw.groups g ON (t.data->>'groupID')::int = g.id::int
LEFT JOIN raw.categories c ON (g.data->>'categoryID')::int = c.id::int;

-- 3. 蓝图与制造视图 (v_blueprints) - 【彻底解决类型对齐】
CREATE VIEW v_blueprints AS
SELECT 
    b.id::int AS blueprint_id,
    ti.data->'name'->>'zh' AS blueprint_name_zh,
    -- 提取产品 ID 并转为 int
    (b.data#>>'{activities,manufacturing,products,0,typeID}')::int AS product_id,
    -- 子查询：左侧 id 强制转 int，右侧提取路径强制转 int
    (SELECT data->'name'->>'zh' FROM raw.types 
     WHERE id::int = (b.data#>>'{activities,manufacturing,products,0,typeID}')::int) AS product_name_zh,
    (b.data#>>'{activities,manufacturing,products,0,quantity}')::int AS product_quantity,
    (b.data#>>'{activities,manufacturing,time}')::int AS prod_time_seconds,
    b.data#>'{activities,manufacturing,materials}' AS materials_json
FROM raw.blueprints b
LEFT JOIN raw.types ti ON b.id::int = ti.id::int;

-- 4. 市场分类树物化视图 (market_menu_tree)
CREATE MATERIALIZED VIEW public.market_menu_tree AS
SELECT 
    id::int AS id,
    (data->>'parentGroupID')::int AS parent_id,
    data->'name'->>'zh' AS name_zh,
    (data->>'iconID')::int AS icon_id,
    (data->>'hasTypes')::boolean AS has_types
FROM raw.market_groups
ORDER BY id;

CREATE UNIQUE INDEX idx_market_menu_id ON public.market_menu_tree(id);
CREATE INDEX idx_market_menu_parent ON public.market_menu_tree(parent_id);

-- 5. 辅助分类物化视图
CREATE MATERIALIZED VIEW public.view_item_categories AS
SELECT id::int AS id, data->'name'->>'zh' AS name_zh FROM raw.categories;

CREATE MATERIALIZED VIEW public.view_item_groups AS
SELECT id::int AS id, (data->>'categoryID')::int AS category_id, data->'name'->>'zh' AS name_zh FROM raw.groups;

-- 6. 刷新数据
REFRESH MATERIALIZED VIEW public.market_menu_tree;
REFRESH MATERIALIZED VIEW public.view_item_categories;
REFRESH MATERIALIZED VIEW public.view_item_groups;