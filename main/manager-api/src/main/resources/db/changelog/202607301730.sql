ALTER TABLE ai_device
    ADD COLUMN registered_at DATETIME NULL COMMENT 'Device registered timestamp' AFTER lifecycle_status,
    ADD COLUMN bound_at DATETIME NULL COMMENT 'Device bound timestamp' AFTER registered_at,
    ADD COLUMN profile_initialized_at DATETIME NULL COMMENT 'Profile initialized timestamp' AFTER bound_at,
    ADD COLUMN ready_at DATETIME NULL COMMENT 'Device ready timestamp' AFTER profile_initialized_at,
    ADD COLUMN suspended_at DATETIME NULL COMMENT 'Device suspended timestamp' AFTER ready_at,
    ADD COLUMN resetting_at DATETIME NULL COMMENT 'Factory reset started timestamp' AFTER suspended_at,
    ADD COLUMN retired_at DATETIME NULL COMMENT 'Device retired timestamp' AFTER resetting_at;

UPDATE ai_device
SET lifecycle_status = CASE
        WHEN lifecycle_status IS NULL OR lifecycle_status = '' THEN
            CASE WHEN user_id IS NULL THEN 'UNBOUND' ELSE 'BOUND' END
        WHEN UPPER(lifecycle_status) = 'DISABLED' THEN 'SUSPENDED'
        ELSE UPPER(lifecycle_status)
    END,
    registered_at = COALESCE(registered_at, create_date),
    bound_at = CASE
        WHEN user_id IS NOT NULL OR UPPER(lifecycle_status) IN ('BOUND', 'PROFILE_INITIALIZED', 'READY') THEN COALESCE(bound_at, create_date)
        ELSE bound_at
    END,
    profile_initialized_at = CASE
        WHEN UPPER(lifecycle_status) IN ('PROFILE_INITIALIZED', 'READY') THEN COALESCE(profile_initialized_at, update_date)
        ELSE profile_initialized_at
    END,
    ready_at = CASE
        WHEN UPPER(lifecycle_status) = 'READY' THEN COALESCE(ready_at, update_date)
        ELSE ready_at
    END;
