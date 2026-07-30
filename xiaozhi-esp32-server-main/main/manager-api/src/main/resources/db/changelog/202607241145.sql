CREATE TABLE IF NOT EXISTS wechat_mini_account (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  account_no VARCHAR(64) NOT NULL COMMENT 'Puppy account identifier',
  openid VARCHAR(128) NOT NULL COMMENT 'WeChat mini program openid',
  unionid VARCHAR(128) NULL COMMENT 'WeChat unionid',
  session_key VARCHAR(128) NULL COMMENT 'Latest WeChat session key',
  phone_number VARCHAR(32) NULL COMMENT 'WeChat verified phone number',
  phone_number_masked VARCHAR(32) NULL COMMENT 'Masked phone number for display',
  country_code VARCHAR(16) NULL COMMENT 'Phone country code',
  phone_bound TINYINT NOT NULL DEFAULT 0 COMMENT 'Whether phone number is bound',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  last_login_at DATETIME NULL,
  UNIQUE KEY uk_wechat_mini_account_no (account_no),
  UNIQUE KEY uk_wechat_mini_openid (openid),
  KEY idx_wechat_mini_phone (phone_number)
) COMMENT='WeChat mini program account binding';
