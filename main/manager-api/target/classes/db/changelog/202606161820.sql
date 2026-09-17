DELETE FROM sys_params WHERE id IN (620, 621);

INSERT INTO sys_params
(id, param_code, param_value, value_type, param_type, remark, creator, create_date, updater, update_date)
VALUES
(620, 'wechat.mini.appid', '', 'string', 1, '微信小程序 appid', NULL, NULL, NULL, NULL),
(621, 'wechat.mini.secret', '', 'string', 1, '微信小程序 secret', NULL, NULL, NULL, NULL);
