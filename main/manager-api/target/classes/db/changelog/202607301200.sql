ALTER TABLE child_profile
    MODIFY COLUMN age TINYINT NULL,
    ADD COLUMN status VARCHAR(32) NULL COMMENT 'Profile lifecycle status' AFTER interests_json;

ALTER TABLE device_child_binding
    ADD COLUMN household_id VARCHAR(64) NULL COMMENT 'Household identifier' AFTER openid,
    ADD COLUMN binding_status VARCHAR(32) NULL COMMENT 'Device binding lifecycle status' AFTER household_id,
    ADD COLUMN owner_openid VARCHAR(128) NULL COMMENT 'Owner WeChat openid' AFTER binding_status,
    ADD KEY idx_device_child_binding_owner_openid (owner_openid);

ALTER TABLE ai_device
    ADD COLUMN lifecycle_status VARCHAR(32) NULL COMMENT 'Device lifecycle status' AFTER last_connected_at,
    ADD COLUMN model VARCHAR(64) NULL COMMENT 'Device model' AFTER board,
    ADD COLUMN client_id VARCHAR(160) NULL COMMENT 'Client connection identifier' AFTER app_version,
    ADD KEY idx_ai_device_lifecycle_status (lifecycle_status);
