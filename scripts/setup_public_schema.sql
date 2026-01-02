-- 确保在 public 架构操作
SET search_path TO public;

-- 1. 物品视图 (整合分类名)
CREATE OR REPLACE VIEW v_items AS
SELECT 
    t.id::int AS item_id,
    t.data->'name'->>'zh' AS name_zh,
    g.data->'name'->>'zh' AS group_name,
    c.data->'name'->>'zh' AS category_name,
    (t.data->>'volume')::float AS volume
FROM raw.types t
LEFT JOIN raw.inv_groups g ON (t.data->>'groupID')::int = g.id::int
LEFT JOIN raw.inv_categories c ON (g.data->>'categoryID')::int = c.id::int
WHERE t.data->>'published' = 'true';

-- 2. 星系视图 (整合星域、星座名)
CREATE OR REPLACE VIEW v_solar_systems AS
SELECT 
    s.id::int AS system_id,
    s.data->'name'->>'zh' AS system_name,
    (s.data->>'securityStatus')::numeric(10,2) AS security,
    r.data->'name'->>'zh' AS region_name
FROM raw.map_solar_systems s
LEFT JOIN raw.map_regions r ON (s.data->>'regionID')::int = r.id::int;

-- 3. 性能索引 (建立在 raw 表上，让视图查询变快)
CREATE INDEX IF NOT EXISTS idx_raw_types_name_zh ON raw.types ((data->'name'->>'zh'));
CREATE INDEX IF NOT EXISTS idx_raw_systems_region ON raw.map_solar_systems (((data->>'regionID')::int));