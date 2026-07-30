const { DEFAULT_DEVICE_ID } = require("../../utils/config");
const { request } = require("../../utils/request");
const { getChildProfile, getWechatAccount } = require("../../utils/storage");

const DAILY_REFRESH_HOUR = 20;

const ACTIVITY_CATEGORIES = [
  { key: "chat", label: "💬 聊聊天", aliases: ["chat", "聊天", "聊聊天", "conversation", "daily_chat"] },
  { key: "learning", label: "📚 学知识", aliases: ["learning", "knowledge", "学习", "学知识", "百科", "问答", "qa", "learn"] },
  { key: "story", label: "📖 听故事", aliases: ["story", "故事", "听故事", "绘本"] },
  { key: "game", label: "🎮 玩游戏", aliases: ["game", "游戏", "玩游戏", "quiz", "riddle"] },
  { key: "creative", label: "🎨 创作", aliases: ["creation", "creative", "创作", "画画", "手工"] },
  { key: "bedtime", label: "💤 睡前陪伴", aliases: ["bedtime", "sleep", "睡前", "睡前陪伴"] },
  { key: "emotional_support", label: "❤️ 情绪陪伴", aliases: ["emotion", "emotional_support", "mood", "情绪", "情绪陪伴"] },
  { key: "music", label: "🎵 音乐互动", aliases: ["music", "音乐", "唱歌", "音乐互动"] },
  { key: "other", label: "🧩 其它", aliases: ["other", "其它", "其他"] }
];

const HIGHLIGHT_BY_ACTIVITY = {
  chat: "今天一起聊了许多轻松的话题。",
  learning: "今天一起探索了好多新知识。",
  story: "今天一起完成了一次故事冒险。",
  game: "今天一起玩了几个有趣的小游戏。",
  creative: "今天一起做了有意思的创作。",
  bedtime: "今天拥有了一段安稳的睡前陪伴。",
  emotional_support: "今天一起练习了表达自己的想法。",
  music: "今天一起享受了轻松的音乐互动。",
  other: "今天一起度过了一段轻松愉快的陪伴时光。"
};

const GENERIC_HIGHLIGHT = "今天一起度过了一段轻松愉快的陪伴时光。";
const SENSITIVE_PATTERNS = [
  "隐私", "秘密", "害怕", "哭", "吵架", "冲突", "打架", "欺负", "生病",
  "家里", "爸爸", "妈妈", "老师", "同学", "学校", "难过", "焦虑"
];

function toNumber(value) {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : 0;
}

function pickNumber(source, keys) {
  if (!source || typeof source !== "object") {
    return 0;
  }
  for (const key of keys) {
    if (source[key] !== undefined && source[key] !== null) {
      return toNumber(source[key]);
    }
  }
  return 0;
}

function normalizeActivityKey(rawValue) {
  const value = String(rawValue || "").trim().toLowerCase();
  if (!value) {
    return "other";
  }

  for (const category of ACTIVITY_CATEGORIES) {
    if (category.aliases.some((alias) => value === alias.toLowerCase() || value.includes(alias.toLowerCase()))) {
      return category.key;
    }
  }

  return "other";
}

function getActivityLabel(key) {
  const normalizedKey = normalizeActivityKey(key);
  const category = ACTIVITY_CATEGORIES.find((item) => item.key === normalizedKey);
  return category ? category.label : "🧩 其它";
}

function collectActivitiesFromSummary(summary) {
  const distribution = summary.activityDistribution || summary.activity_distribution || {};
  return Object.keys(distribution)
    .filter((key) => toNumber(distribution[key]) > 0)
    .sort((a, b) => toNumber(distribution[b]) - toNumber(distribution[a]))
    .map((key) => ({
      key: normalizeActivityKey(key),
      label: getActivityLabel(key)
    }));
}

function parseDate(dateText) {
  const match = String(dateText || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return null;
  }
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

function formatDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function dateForOffset(offset) {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() - offset);
  return date;
}

function relativeDateLabel(dateText, fallbackIndex) {
  const date = parseDate(dateText) || dateForOffset(fallbackIndex);
  const today = dateForOffset(0);
  const diffDays = Math.round((today.getTime() - date.getTime()) / 86400000);
  if (diffDays === 0) {
    return "今日";
  }
  if (diffDays === 1) {
    return "昨日";
  }
  return fullDateText(date);
}

function fullDateText(date) {
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

function displayDateText(dateText, fallbackIndex) {
  const date = parseDate(dateText) || dateForOffset(fallbackIndex);
  return fullDateText(date);
}

function isSafeHighlight(text) {
  const normalized = String(text || "").trim();
  if (!normalized || normalized.length > 30) {
    return false;
  }
  return !SENSITIVE_PATTERNS.some((pattern) => normalized.includes(pattern));
}

function dayAwareHighlight(text, dateLabel) {
  const normalized = String(text || GENERIC_HIGHLIGHT).trim();
  if (dateLabel === "今日") {
    return normalized;
  }
  return normalized.replace(/^今天/, "这一天");
}

function buildHighlight(activityItems, sessionCount, dateLabel) {
  if (!sessionCount || !activityItems.length) {
    return dayAwareHighlight(GENERIC_HIGHLIGHT, dateLabel);
  }
  return dayAwareHighlight(HIGHLIGHT_BY_ACTIVITY[activityItems[0].key] || GENERIC_HIGHLIGHT, dateLabel);
}

function emptySummary(offset) {
  return {
    date: formatDate(dateForOffset(offset)),
    totalDuration: 0,
    sessionCount: 0,
    activityDistribution: {},
    highlightMetadata: {
      primary_activity: "other"
    }
  };
}

function normalizeDashboard(payload, index) {
  const data = payload && typeof payload === "object" ? payload : emptySummary(index);
  const dateText = data.date || formatDate(dateForOffset(index));
  const dateLabel = relativeDateLabel(dateText, index);
  const totalDuration = pickNumber(data, ["totalDuration", "total_duration"]);
  const sessionCount = pickNumber(data, ["sessionCount", "session_count"]);
  const companionshipMinutes = Math.max(0, Math.round(totalDuration));
  const activityItems = collectActivitiesFromSummary(data);
  const highlightMetadata = data.highlightMetadata || data.highlight_metadata || {};
  const primaryActivity = highlightMetadata.primary_activity || data.primaryActivity || data.primary_activity || "";
  const rawHighlight = data.highlightText || data.highlight_text;
  const isToday = dateLabel === "今日";

  return {
    date: dateText,
    dateLabel,
    dateText: displayDateText(dateText, index),
    isPrimary: index === 0,
    cardClass: index === 0 ? "primary-card" : "history-card",
    cardTitle: isToday ? "❤️ 今天和可可一起" : `❤️ ${dateLabel}和可可一起`,
    highlightTitle: isToday ? "🌟 今天最精彩" : "🌟 这一天最精彩",
    emptyText: isToday ? "今天还没有互动记录" : "这一天没有互动记录",
    companionshipMinutes,
    showActivitySections: companionshipMinutes > 0,
    durationText: companionshipMinutes > 0
      ? `${companionshipMinutes} 分钟`
      : (sessionCount > 0 ? "少于 1 分钟" : "0 分钟"),
    sessionCount: Math.max(0, Math.round(sessionCount)),
    activityItems,
    highlightText: isSafeHighlight(rawHighlight)
      ? dayAwareHighlight(rawHighlight, dateLabel)
      : buildHighlight(
          activityItems.length ? activityItems : (primaryActivity ? [{ key: normalizeActivityKey(primaryActivity) }] : []),
          sessionCount,
          dateLabel
        )
  };
}

function normalizeHistory(payload) {
  const source = Array.isArray(payload)
    ? payload
    : (payload && Array.isArray(payload.summaries) ? payload.summaries : []);
  if (!source.length) {
    return [normalizeDashboard(emptySummary(0), 0)];
  }
  const summaries = [];
  for (let index = 0; index < source.length; index++) {
    summaries.push(normalizeDashboard(source[index] || emptySummary(index), index));
  }
  return summaries;
}

function fallbackHistory() {
  return normalizeHistory([]);
}

Page({
  dailyRefreshTimer: null,

  data: {
    loading: false,
    summaryCards: fallbackHistory()
  },

  onShow() {
    this.loadTodayCompanion();
    this.scheduleDailyRefresh();
  },

  onHide() {
    this.clearDailyRefreshTimer();
  },

  onUnload() {
    this.clearDailyRefreshTimer();
  },

  clearDailyRefreshTimer() {
    if (this.dailyRefreshTimer) {
      clearTimeout(this.dailyRefreshTimer);
      this.dailyRefreshTimer = null;
    }
  },

  scheduleDailyRefresh() {
    this.clearDailyRefreshTimer();
    const now = new Date();
    const nextRefresh = new Date(now);
    nextRefresh.setHours(DAILY_REFRESH_HOUR, 0, 0, 0);
    if (nextRefresh <= now) {
      nextRefresh.setDate(nextRefresh.getDate() + 1);
    }
    this.dailyRefreshTimer = setTimeout(() => {
      this.loadTodayCompanion();
      this.scheduleDailyRefresh();
    }, nextRefresh.getTime() - now.getTime());
  },

  async loadTodayCompanion() {
    const profile = getChildProfile() || {};
    const account = getWechatAccount() || {};
    const deviceId = profile.deviceId || account.deviceId || DEFAULT_DEVICE_ID;

    this.setData({ loading: true });
    try {
      const history = await request({
        url: `/child-profile/today-companion/history?device_id=${encodeURIComponent(deviceId)}`,
        method: "GET",
        timeout: 8000
      });
      this.setData({
        summaryCards: normalizeHistory(history),
        loading: false
      });
    } catch (err) {
      this.setData({
        summaryCards: fallbackHistory(),
        loading: false
      });
    }
  }
});
