ALTER TABLE child_profile
  ADD COLUMN interests_json TEXT NULL COMMENT '兴趣内容JSON' AFTER age_group;
