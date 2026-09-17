CREATE TABLE IF NOT EXISTS robot_household (
    id VARCHAR(32) NOT NULL COMMENT 'Household ID',
    owner_openid VARCHAR(128) NOT NULL COMMENT 'Owner WeChat openid',
    household_name VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'Household display name',
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE' COMMENT 'Household lifecycle status',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_robot_household_owner_openid (owner_openid),
    KEY idx_robot_household_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Robot household';
