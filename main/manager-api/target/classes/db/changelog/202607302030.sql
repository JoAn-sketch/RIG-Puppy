UPDATE ai_device d
JOIN device_child_binding b
    ON b.is_active = 1
    AND LOWER(b.device_id) IN (
        LOWER(d.id),
        LOWER(REPLACE(REPLACE(d.id, ':', ''), '-', '')),
        RIGHT(LOWER(REPLACE(REPLACE(d.id, ':', ''), '-', '')), 6)
    )
SET d.lifecycle_status = 'BOUND',
    d.bound_at = COALESCE(d.bound_at, NOW()),
    d.update_date = NOW()
WHERE UPPER(COALESCE(d.lifecycle_status, '')) IN ('UNBOUND', 'REGISTERED', 'BOUND');
