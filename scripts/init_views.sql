-- ========================================================
-- EVE SDE 终极业务视图脚本 (v3.0 统一架构版)
-- 适用范围：FastAPI 后端高效读取 & 自动化刷新
-- ========================================================

CREATE SCHEMA IF NOT EXISTS public;
SET search_path TO public;

-- 1. 物品核心视图 (v_items)
CREATE OR REPLACE VIEW v_items AS
SELECT 
    t.id::int AS item_id,
    t.data->'name'->>'zh' AS name_zh,
    t.data->'name'->>'en' AS name_en,
    g.data->'name'->>'zh' AS group_name_zh,
    c.data->'name'->>'zh' AS category_name_zh,
    (t.data->>'mass')::float AS mass,
    (t.data->>'volume')::float AS volume,
    (t.data->>'packagedVolume')::float AS packaged_volume,
    (t.data->>'capacity')::float AS capacity,
    (t.data->>'published')::boolean AS is_published
FROM raw.types t
LEFT JOIN raw.groups g ON (t.data->>'groupID')::int = g.id::int
LEFT JOIN raw.categories c ON (g.data->>'categoryID')::int = c.id::int;

-- 2. 宇宙地理视图 (v_solar_systems)
CREATE OR REPLACE VIEW v_solar_systems AS
SELECT 
    s.id::int AS system_id,
    s.data->'name'->>'zh' AS name_zh,
    s.data->'name'->>'en' AS name_en,
    (s.data->>'securityStatus')::numeric(10,2) AS security,
    r.data->'name'->>'zh' AS region_name_zh,
    r.data->'name'->>'en' AS region_name_en,
    cn.data->'name'->>'zh' AS constellation_name_zh
FROM raw.map_solar_systems s
LEFT JOIN raw.map_regions r ON (s.data->>'regionID')::int = r.id::int
LEFT JOIN raw.map_constellations cn ON (s.data->>'constellationID')::int = cn.id::int;

-- 3. 蓝图与制造视图 (v_blueprints)
CREATE OR REPLACE VIEW v_blueprints AS
SELECT 
    b.id::int AS blueprint_id,
    ti.data->'name'->>'zh' AS blueprint_name_zh,
    (b.data->'activities'->'manufacturing'->'products'->0->>'typeID')::int AS product_id,
    (SELECT data->'name'->>'zh' FROM raw.types WHERE id = (b.data->'activities'->'manufacturing'->'products'->0->>'typeID')::int) AS product_name_zh,
    (b.data->'activities'->'manufacturing'->'products'->0->>'quantity')::int AS product_quantity,
    (b.data->'activities'->'manufacturing'->>'time')::int AS prod_time_seconds,
    b.data->'activities'->'manufacturing'->'materials' AS materials_json
FROM raw.blueprints b
LEFT JOIN raw.types ti ON b.id = ti.id;

-- 4. 市场分类树物化视图 (market_menu_tree)
-- [重要]：改为物化视图以支撑 FastAPI 高频递归查询
DROP MATERIALIZED VIEW IF EXISTS public.market_menu_tree;
CREATE MATERIALIZED VIEW public.market_menu_tree AS
SELECT 
    id::int AS id,
    (data->>'parentGroupID')::int AS parent_id,
    data->'name'->>'zh' AS name_zh,
    (data->>'iconID')::int AS icon_id,
    (data->>'hasTypes')::boolean AS has_types
FROM raw.market_groups
ORDER BY id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_market_menu_id ON public.market_menu_tree(id);
CREATE INDEX IF NOT EXISTS idx_market_menu_parent ON public.market_menu_tree(parent_id);

-- 5. 物品组与大类物化视图 (用于属性过滤与搜索)
CREATE MATERIALIZED VIEW IF NOT EXISTS public.view_item_categories AS
SELECT id::int AS id, data->'name'->>'zh' AS name_zh FROM raw.categories;

CREATE MATERIALIZED VIEW IF NOT EXISTS public.view_item_groups AS
SELECT id::int AS id, (data->>'categoryID')::int AS category_id, data->'name'->>'zh' AS name_zh FROM raw.groups;

CREATE UNIQUE INDEX IF NOT EXISTS idx_v_cat_id ON public.view_item_categories(id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_v_grp_id ON public.view_item_groups(id);

-- ========================================================
-- 自动化刷新逻辑与性能优化
-- ========================================================

-- 刷新物化视图数据 (确保 main.py 调用此脚本后数据是最新的)
REFRESH MATERIALIZED VIEW public.market_menu_tree;
REFRESH MATERIALIZED VIEW public.view_item_categories;
REFRESH MATERIALIZED VIEW public.view_item_groups;

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_raw_types_name_zh ON raw.types ((data->'name'->>'zh'));
CREATE INDEX IF NOT EXISTS idx_raw_types_group_id ON raw.types (((data->>'groupID')::int));