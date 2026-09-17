DELETE FROM `ai_model_config` WHERE id = 'TTS_KokoroHttpTTS';
INSERT INTO `ai_model_config` VALUES (
  'TTS_KokoroHttpTTS',
  'TTS',
  'KokoroHttpTTS',
  'Kokoro本地语音合成',
  0,
  1,
  '{\"type\": \"kokoro_http\", \"api_url\": \"http://127.0.0.1:8880/v1/audio/speech\", \"model\": \"kokoro\", \"voice\": \"zf_xiaoxiao\", \"response_format\": \"wav\", \"stream_format\": \"audio\", \"speed\": 1.0, \"output_dir\": \"tmp/\", \"connect_timeout\": 3, \"read_timeout\": 20, \"request_timeout\": 20, \"first_audio_timeout_ms\": 5000, \"max_retry_attempts\": 2}',
  'https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh',
  '本地Kokoro HTTP/OpenAI-compatible TTS，仅供单设备灰度测试。',
  2,
  NULL,
  NULL,
  NULL,
  NULL
);
