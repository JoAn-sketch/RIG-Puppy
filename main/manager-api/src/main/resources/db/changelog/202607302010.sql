UPDATE ai_device d
LEFT JOIN device_child_binding b
    ON LOWER(b.device_id) = LOWER(d.id)
    AND b.is_active = 1
SET d.lifecycle_status = 'UNBOUND',
    d.user_id = NULL,
    d.bound_at = NULL,
    d.profile_initialized_at = NULL,
    d.ready_at = NULL,
    d.update_date = NOW()
WHERE UPPER(COALESCE(d.lifecycle_status, '')) IN ('BOUND', 'PROFILE_INITIALIZED', 'READY')
  AND b.id IS NULL;
