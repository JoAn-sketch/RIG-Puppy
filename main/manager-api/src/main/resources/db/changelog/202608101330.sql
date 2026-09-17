-- liquibase formatted sql

-- changeset codex:202608101330
CREATE TABLE IF NOT EXISTS `ai_device_ota_job` (
    `id` VARCHAR(32) NOT NULL COMMENT 'OTA作业ID',
    `device_id` VARCHAR(64) NOT NULL COMMENT '设备ID',
    `from_version` VARCHAR(50) DEFAULT NULL COMMENT '发起升级时的实际版本',
    `target_version` VARCHAR(50) NOT NULL COMMENT '目标版本',
    `firmware_url` VARCHAR(512) DEFAULT NULL COMMENT '固件下载地址',
    `status` VARCHAR(20) NOT NULL COMMENT 'upgrading/success/failed',
    `requested_at` DATETIME NOT NULL COMMENT '命令确认时间',
    `acknowledged_at` DATETIME DEFAULT NULL COMMENT '设备确认命令时间',
    `completed_at` DATETIME DEFAULT NULL COMMENT '升级完成或失败时间',
    `last_reported_version` VARCHAR(50) DEFAULT NULL COMMENT '设备最近一次上报的实际版本',
    `failure_reason` VARCHAR(500) DEFAULT NULL COMMENT '失败原因',
    `creator` BIGINT DEFAULT NULL,
    `create_date` DATETIME DEFAULT NULL,
    `updater` BIGINT DEFAULT NULL,
    `update_date` DATETIME DEFAULT NULL,
    PRIMARY KEY (`id`),
    INDEX `idx_device_ota_job_device_requested` (`device_id`, `requested_at`),
    INDEX `idx_device_ota_job_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备OTA升级作业';
