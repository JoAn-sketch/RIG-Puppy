from __future__ import annotations

from typing import Iterable


INTEREST_ALIASES = {
    "animals": "animals",
    "animal": "animals",
    "小动物": "animals",
    "动物": "animals",
    "小动物们": "animals",
    "动物们": "animals",
    "🐶小动物": "animals",
    "dinosaurs": "dinosaurs",
    "dinosaur": "dinosaurs",
    "恐龙": "dinosaurs",
    "🦖恐龙": "dinosaurs",
    "space": "space",
    "太空": "space",
    "宇宙": "space",
    "星空": "space",
    "🚀太空": "space",
    "vehicles": "vehicles",
    "vehicle": "vehicles",
    "交通工具": "vehicles",
    "汽车和交通工具": "vehicles",
    "汽车": "vehicles",
    "车": "vehicles",
    "车车": "vehicles",
    "🚗汽车和交通工具": "vehicles",
    "nature": "nature",
    "大自然": "nature",
    "自然": "nature",
    "户外自然": "nature",
    "🌳大自然": "nature",
    "sports": "sports",
    "sport": "sports",
    "运动": "sports",
    "体育": "sports",
    "⚽运动": "sports",
    "artandcrafts": "art_and_crafts",
    "art_and_crafts": "art_and_crafts",
    "画画和手工": "art_and_crafts",
    "画画": "art_and_crafts",
    "手工": "art_and_crafts",
    "美术": "art_and_crafts",
    "🎨画画和手工": "art_and_crafts",
    "musicanddance": "music_and_dance",
    "music_and_dance": "music_and_dance",
    "音乐和跳舞": "music_and_dance",
    "音乐": "music_and_dance",
    "跳舞": "music_and_dance",
    "唱歌跳舞": "music_and_dance",
    "🎵音乐和跳舞": "music_and_dance",
    "storiesandpicturebooks": "stories_and_picture_books",
    "stories_and_picture_books": "stories_and_picture_books",
    "stories": "stories_and_picture_books",
    "故事和绘本": "stories_and_picture_books",
    "故事": "stories_and_picture_books",
    "绘本": "stories_and_picture_books",
    "图画书": "stories_and_picture_books",
    "📚故事和绘本": "stories_and_picture_books",
    "riddlesandgames": "riddles_and_games",
    "riddles_and_games": "riddles_and_games",
    "games": "riddles_and_games",
    "猜谜和小游戏": "riddles_and_games",
    "猜谜": "riddles_and_games",
    "小游戏": "riddles_and_games",
    "游戏": "riddles_and_games",
    "谜语": "riddles_and_games",
    "🧩猜谜和小游戏": "riddles_and_games",
}


def _normalize_alias_key(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    normalized = normalized.replace("\ufe0f", "")
    for char in (" ", "_", "-"):
        normalized = normalized.replace(char, "")
    return normalized


def normalize_interest_key(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return INTEREST_ALIASES.get(_normalize_alias_key(raw), raw)


def normalize_interest_keys(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    for value in values:
        key = normalize_interest_key(value)
        if key and key not in normalized:
            normalized.append(key)
    return normalized
