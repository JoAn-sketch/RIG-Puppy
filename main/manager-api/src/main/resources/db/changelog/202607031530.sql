CREATE TABLE IF NOT EXISTS child_long_term_memory (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    openid VARCHAR(128) NOT NULL COMMENT '微信openid',
    nickname_preference VARCHAR(64) DEFAULT NULL COMMENT '孩子喜欢被怎么称呼',
    age INT DEFAULT NULL COMMENT '年龄',
    age_group VARCHAR(16) DEFAULT NULL COMMENT '年龄分档',
    profile_version INT NOT NULL DEFAULT 1 COMMENT '长期记忆结构版本',
    profile_json LONGTEXT DEFAULT NULL COMMENT '长期记忆扩展JSON',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_child_long_term_memory_openid (openid),
    KEY idx_child_long_term_memory_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='儿童长期记忆';
