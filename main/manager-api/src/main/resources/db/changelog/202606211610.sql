ALTER TABLE child_profile
    ADD COLUMN nickname VARCHAR(32) NOT NULL DEFAULT '' AFTER openid;
