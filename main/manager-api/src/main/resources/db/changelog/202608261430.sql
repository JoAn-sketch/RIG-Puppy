-- Smooth Kokoro playback by avoiding overly short TTS segments.
UPDATE `ai_model_config`
SET
  config_json = JSON_SET(
    config_json,
    '$.first_segment_min_chars', 6,
    '$.min_segment_chars', 14,
    '$.first_segment_max_chars', 8,
    '$.max_segment_chars', 48
  ),
  update_date = NOW()
WHERE id = 'TTS_KokoroHttpTTS';
