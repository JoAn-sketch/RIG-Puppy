-- Standardize runtime speech stack on FunASR streaming ASR + Kokoro local TTS.

DELETE FROM `ai_model_provider` WHERE id = 'SYSTEM_TTS_KokoroHttpTTS';
INSERT INTO `ai_model_provider`
(`id`, `model_type`, `provider_code`, `name`, `fields`, `sort`, `creator`, `create_date`, `updater`, `update_date`)
VALUES
('SYSTEM_TTS_KokoroHttpTTS', 'TTS', 'kokoro_http', 'Kokoro本地语音合成',
'[
  {"key":"api_url","label":"服务地址","type":"string"},
  {"key":"model","label":"模型名称","type":"string"},
  {"key":"voice","label":"默认音色","type":"string"},
  {"key":"response_format","label":"音频格式","type":"string"},
  {"key":"stream_format","label":"流格式","type":"string"},
  {"key":"speed","label":"语速","type":"number"},
  {"key":"connect_timeout","label":"连接超时秒数","type":"number"},
  {"key":"read_timeout","label":"读取超时秒数","type":"number"},
  {"key":"request_timeout","label":"请求超时秒数","type":"number"},
  {"key":"first_audio_timeout_ms","label":"首包超时毫秒","type":"number"},
  {"key":"max_retry_attempts","label":"最大重试次数","type":"number"},
  {"key":"output_dir","label":"输出目录","type":"string"}
]', 1, 1, NOW(), 1, NOW());

UPDATE `ai_model_config`
SET is_default = 0, is_enabled = 0, update_date = NOW()
WHERE id IN (
  'ASR_FunASR',
  'ASR_AliyunASR',
  'ASR_AliyunStreamASR',
  'ASR_AliyunBLStream',
  'TTS_EdgeTTS'
);

UPDATE `ai_model_config`
SET is_default = 1, is_enabled = 1, sort = 1, update_date = NOW()
WHERE id = 'ASR_FunASRServer';

UPDATE `ai_model_config`
SET
  is_default = 1,
  is_enabled = 1,
  sort = 1,
  config_json = '{\"type\": \"kokoro_http\", \"api_url\": \"http://127.0.0.1:8880/v1/audio/speech\", \"model\": \"kokoro\", \"voice\": \"zf_xiaoxiao\", \"response_format\": \"wav\", \"stream_format\": \"audio\", \"speed\": 1.0, \"output_dir\": \"tmp/\", \"connect_timeout\": 3, \"read_timeout\": 20, \"request_timeout\": 20, \"first_audio_timeout_ms\": 5000, \"max_retry_attempts\": 2, \"first_segment_min_chars\": 6, \"min_segment_chars\": 14, \"first_segment_max_chars\": 8, \"max_segment_chars\": 48}',
  update_date = NOW()
WHERE id = 'TTS_KokoroHttpTTS';

DELETE FROM `ai_tts_voice` WHERE tts_model_id IN ('TTS_EdgeTTS', 'TTS_KokoroHttpTTS');
INSERT INTO `ai_tts_voice`
(`id`, `tts_model_id`, `name`, `tts_voice`, `languages`, `voice_demo`, `remark`, `sort`, `creator`, `create_date`, `updater`, `update_date`)
VALUES
('TTS_Kokoro0001', 'TTS_KokoroHttpTTS', 'Kokoro女声-晓晓', 'zf_xiaoxiao', '普通话', NULL, 'Kokoro原生音色', 1, 1, NOW(), 1, NOW()),
('TTS_Kokoro0002', 'TTS_KokoroHttpTTS', 'Kokoro男声-云扬', 'zm_yunyang', '普通话', NULL, 'Kokoro原生音色', 2, 1, NOW(), 1, NOW()),
('TTS_Kokoro0003', 'TTS_KokoroHttpTTS', 'Kokoro女声-晓伊', 'zf_xiaoyi', '普通话', NULL, 'Kokoro原生音色', 3, 1, NOW(), 1, NOW()),
('TTS_Kokoro0004', 'TTS_KokoroHttpTTS', 'Kokoro男声-云健', 'zm_yunjian', '普通话', NULL, 'Kokoro原生音色', 4, 1, NOW(), 1, NOW()),
('TTS_Kokoro0005', 'TTS_KokoroHttpTTS', 'Kokoro男声-云希', 'zm_yunxi', '普通话', NULL, 'Kokoro原生音色', 5, 1, NOW(), 1, NOW()),
('TTS_Kokoro0006', 'TTS_KokoroHttpTTS', 'Kokoro男声-云夏', 'zm_yunxia', '普通话', NULL, 'Kokoro原生音色', 6, 1, NOW(), 1, NOW()),
('TTS_Kokoro0007', 'TTS_KokoroHttpTTS', 'Kokoro女声-小贝', 'zf_xiaobei', '普通话', NULL, 'Kokoro原生音色', 7, 1, NOW(), 1, NOW()),
('TTS_Kokoro0008', 'TTS_KokoroHttpTTS', 'Kokoro女声-小妮', 'zf_xiaoni', '普通话', NULL, 'Kokoro原生音色', 8, 1, NOW(), 1, NOW());

UPDATE `ai_agent`
SET asr_model_id = 'ASR_FunASRServer', updated_at = NOW()
WHERE asr_model_id IN ('ASR_FunASR', 'ASR_AliyunASR', 'ASR_AliyunStreamASR', 'ASR_AliyunBLStream');

UPDATE `ai_agent`
SET tts_model_id = 'TTS_KokoroHttpTTS', tts_voice_id = 'TTS_Kokoro0001', updated_at = NOW()
WHERE tts_model_id = 'TTS_EdgeTTS';

UPDATE `ai_agent_template`
SET asr_model_id = 'ASR_FunASRServer', updated_at = NOW()
WHERE asr_model_id IN ('ASR_FunASR', 'ASR_AliyunASR', 'ASR_AliyunStreamASR', 'ASR_AliyunBLStream');

UPDATE `ai_agent_template`
SET tts_model_id = 'TTS_KokoroHttpTTS', tts_voice_id = 'TTS_Kokoro0001', updated_at = NOW()
WHERE tts_model_id = 'TTS_EdgeTTS';
