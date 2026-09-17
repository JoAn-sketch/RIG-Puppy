package xiaozhi.modules.childprofile.support;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import org.apache.commons.lang3.StringUtils;

public final class InterestKeyNormalizer {

    private static final Map<String, String> INTEREST_ALIASES = buildAliases();

    private InterestKeyNormalizer() {
    }

    public static String normalizeInterest(String value) {
        String raw = StringUtils.trimToEmpty(value);
        if (StringUtils.isBlank(raw)) {
            return "";
        }

        String normalized = normalizeAliasKey(raw);
        String mapped = INTEREST_ALIASES.get(normalized);
        return mapped != null ? mapped : raw;
    }

    public static List<String> normalizeInterestList(List<String> values) {
        if (values == null || values.isEmpty()) {
            return new ArrayList<>();
        }
        Set<String> deduped = new LinkedHashSet<>();
        for (String value : values) {
            String normalized = normalizeInterest(value);
            if (StringUtils.isNotBlank(normalized)) {
                deduped.add(normalized);
            }
        }
        return new ArrayList<>(deduped);
    }

    private static Map<String, String> buildAliases() {
        Map<String, String> aliases = new LinkedHashMap<>();

        register(aliases, "animals",
                "animals", "animal", "🐶小动物", "小动物", "动物", "动物们", "小动物们");
        register(aliases, "dinosaurs",
                "dinosaurs", "dinosaur", "🦖恐龙", "恐龙");
        register(aliases, "space",
                "space", "🚀太空", "太空", "宇宙", "星空");
        register(aliases, "vehicles",
                "vehicles", "vehicle", "🚗汽车和交通工具", "汽车和交通工具", "交通工具", "汽车", "车", "车车");
        register(aliases, "nature",
                "nature", "🌳大自然", "大自然", "自然", "户外自然");
        register(aliases, "sports",
                "sports", "sport", "⚽运动", "运动", "体育");
        register(aliases, "art_and_crafts",
                "art_and_crafts", "artandcrafts", "🎨画画和手工", "画画和手工", "画画", "手工", "美术");
        register(aliases, "music_and_dance",
                "music_and_dance", "musicanddance", "🎵音乐和跳舞", "音乐和跳舞", "音乐", "跳舞", "唱歌跳舞");
        register(aliases, "stories_and_picture_books",
                "stories_and_picture_books", "storiesandpicturebooks", "stories", "📚故事和绘本", "故事和绘本", "故事", "绘本", "图画书");
        register(aliases, "riddles_and_games",
                "riddles_and_games", "riddlesandgames", "games", "🧩猜谜和小游戏", "猜谜和小游戏", "猜谜", "小游戏", "游戏", "谜语");

        return aliases;
    }

    private static void register(Map<String, String> aliases, String key, String... values) {
        for (String value : values) {
            String normalized = normalizeAliasKey(value);
            if (StringUtils.isNotBlank(normalized)) {
                aliases.put(normalized, key);
            }
        }
    }

    private static String normalizeAliasKey(String value) {
        String normalized = StringUtils.trimToEmpty(value).toLowerCase(Locale.ROOT);
        normalized = normalized.replace("\uFE0F", "");
        normalized = normalized.replaceAll("[\\s_\\-]+", "");
        return normalized;
    }
}
