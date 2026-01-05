-- ========================================================
-- EVE SDE 终极业务视图脚本 (v2.6 修正版)
-- 修复：ti.name_zh 路径错误
-- ========================================================

-- 确保后续操作在 public 架构中
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

-- 3. 蓝图与制造视图 (v_blueprints) - 已修复 ti.name_zh 错误
CREATE OR REPLACE VIEW v_blueprints AS
SELECT 
    b.id::int AS blueprint_id,
    ti.data->'name'->>'zh' AS blueprint_name_zh, -- 修正：从 data 字段提取
    (b.data->'activities'->'manufacturing'->'products'->0->>'typeID')::int AS product_id,
    (SELECT data->'name'->>'zh' FROM raw.types WHERE id = b.data->'activities'->'manufacturing'->'products'->0->>'typeID') AS product_name_zh,
    (b.data->'activities'->'manufacturing'->'products'->0->>'quantity')::int AS product_quantity,
    (b.data->'activities'->'manufacturing'->>'time')::int AS prod_time_seconds,
    b.data->'activities'->'manufacturing'->'materials' AS materials_json
FROM raw.blueprints b
LEFT JOIN raw.types ti ON b.id = ti.id;

-- 4. 装备属性视图 (v_item_attributes)
CREATE OR REPLACE VIEW v_item_attributes AS
SELECT 
    t.id::int AS item_id,
    t.data->'name'->>'zh' AS item_name_zh,
    da.data->'name'->>'en' AS attr_name_en,
    da.data->'name'->>'zh' AS attr_name_zh,
    (attr->>'value')::float AS attr_value
FROM raw.types t,
LATERAL jsonb_array_elements(t.data->'dogmaAttributes') AS attr
LEFT JOIN raw.dogma_attributes da ON (attr->>'attributeID')::int = da.id::int;

-- 5. 市场分类视图 (v_market_structure)
CREATE OR REPLACE VIEW v_market_structure AS
SELECT 
    m.id::int AS market_group_id,
    m.data->'name'->>'zh' AS name_zh,
    m.data->'name'->>'en' AS name_en,
    (m.data->>'parentGroupID')::int AS parent_id
FROM raw.market_groups m;

-- ========================================================
-- 性能优化
-- ========================================================
CREATE INDEX IF NOT EXISTS idx_raw_types_name_zh ON raw.types ((data->'name'->>'zh'));
CREATE INDEX IF NOT EXISTS idx_raw_types_name_en ON raw.types ((data->'name'->>'en'));
CREATE INDEX IF NOT EXISTS idx_raw_systems_name_zh ON raw.map_solar_systems ((data->'name'->>'zh'));
CREATE INDEX IF NOT EXISTS idx_raw_systems_name_en ON raw.map_solar_systems ((data->'name'->>'en'));
CREATE INDEX IF NOT EXISTS idx_raw_types_group_id ON raw.types (((data->>'groupID')::int));