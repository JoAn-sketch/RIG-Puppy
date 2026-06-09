(function () {
  const NAV_ITEMS = [
    { href: "/", label: "📚 后端" },
    { href: "/contacts", label: "👥 联系人" },
    { href: "/templates", label: "📨 消息模板" },
    { href: "/message-log", label: "📋 发送日志" },
    { href: "/reminders", label: "⏰ 提醒计划" },
    { href: "/monitor", label: "📊 系统监控" },
    { href: "/prompt", label: "📝 Prompt" },
    { href: "/portrait", label: "🧑 画像" },
    { href: "/mood", label: "😊 情绪" },
    { href: "/actions", label: "🐕 动作" },
    { href: "/memo", label: "📝 备忘录" },
    { href: "/llm-logs", label: "🔍 LLM日志" },
    { href: "/debug", label: "🔧 调试" },
    { href: "/settings", label: "⚙️ 设置" },
    { href: "/iot", label: "🏠 家居" },
    { href: "/health", label: "🏥 健康" },
    { href: "/voiceprint", label: "🎤 声纹" },
    { href: "/kid", label: "🧒 儿童" },
    { href: "/scene-router", label: "🧭 Scene Router" },
    { href: "/dingyi-models", label: "🤖 模型切换" },
    { href: "/dingyi-chat", label: "💬 对话模拟" },
    { href: "http://122.51.155.114:8002", label: "🖥 主控台", external: true },
  ];

  function normalizePath(pathname) {
    if (!pathname) return "/";
    if (pathname !== "/" && pathname.endsWith("/")) {
      return pathname.slice(0, -1);
    }
    return pathname;
  }

  function isActive(itemHref, currentPath) {
    if (!itemHref.startsWith("/")) {
      return false;
    }
    return normalizePath(itemHref) === currentPath;
  }

  function renderNav() {
    const header = document.querySelector("header");
    if (!header) return;

    const navContainer = header.querySelector("div:last-child");
    if (!navContainer) return;

    const currentPath = normalizePath(window.location.pathname);
    navContainer.innerHTML = NAV_ITEMS.map((item) => {
      const active = isActive(item.href, currentPath);
      const style = active
        ? "color:#ffffff;font-weight:600;"
        : "";
      const target = item.external ? ' target="_blank" rel="noreferrer"' : "";
      return `<a href="${item.href}"${target} style="${style}">${item.label}</a>`;
    }).join("");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderNav);
  } else {
    renderNav();
  }
})();
