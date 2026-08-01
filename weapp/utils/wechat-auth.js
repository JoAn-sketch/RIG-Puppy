const { request } = require("./request");
const {
  getWechatOpenid,
  saveWechatOpenid,
  saveChildProfile,
  clearChildProfile,
  clearLocalOnboardingState,
  getInitializationState,
  saveInitializationState,
  saveStartupState,
  updateWechatAccountProfile
} = require("./storage");

const INTEREST_LABELS = {
  animals: "🐶 小动物",
  dinosaurs: "🦖 恐龙",
  space: "🚀 太空",
  vehicles: "🚗 汽车和交通工具",
  nature: "🌳 大自然",
  sports: "⚽ 运动",
  art_and_crafts: "🎨 画画和手工",
  music_and_dance: "🎵 音乐和跳舞",
  stories_and_picture_books: "📚 故事和绘本",
  riddles_and_games: "🧩 猜谜和小游戏"
};

function wxLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(res) {
        if (res.code) {
          resolve(res.code);
          return;
        }
        reject(new Error("wx.login 未返回 code"));
      },
      fail(err) {
        reject(err);
      }
    });
  });
}

async function bindWechatAccount(options = {}) {
  const { forceRefresh = false } = options;
  const cachedOpenid = getWechatOpenid();
  if (cachedOpenid && !forceRefresh) {
    return cachedOpenid;
  }

  const code = await wxLogin();
  const loginData = await request({
    url: "/wechat-mini/login",
    method: "POST",
    data: { code },
    timeout: 20000,
    timeoutMessage: "微信登录超时，请稍后重试"
  });
  const openid = loginData && loginData.openid;

  if (!openid) {
    throw new Error("后端未返回 openid");
  }

  if (loginData.newAccount) {
    clearLocalOnboardingState(openid);
  }
  saveWechatOpenid(openid);
  saveStartupState({
    accessToken: loginData.accessToken || loginData.token || "",
    refreshToken: loginData.refreshToken || ""
  });
  return openid;
}

async function initializeWechatProfile(payload) {
  const openid = payload && payload.openid;
  return request({
    url: "/profile/init",
    method: "POST",
    data: payload || {},
    header: buildWechatIdentityHeaders(openid),
    timeout: 20000,
    timeoutMessage: "微信资料初始化超时，请稍后重试"
  });
}

function normalizeServerProfile(serverProfile, openid) {
  const interests = Array.isArray(serverProfile && serverProfile.interests)
    ? serverProfile.interests
    : [];
  return {
    profileCompleted: !!(serverProfile && serverProfile.profileCompleted),
    nickname: (serverProfile && serverProfile.nickname) || "",
    robotName: (serverProfile && serverProfile.robotNamePreference) || "",
    favoriteThings: interests.map((item) => INTEREST_LABELS[item] || item),
    age: serverProfile && serverProfile.age ? Number(serverProfile.age) : null,
    ageGroup: (serverProfile && serverProfile.ageGroup) || "",
    deviceId: (serverProfile && serverProfile.deviceId) || "",
    deviceBound: !!(serverProfile && serverProfile.bound),
    openid,
    avatarUrl: ""
  };
}

function buildWechatIdentityHeaders(openid) {
  const normalizedOpenid = String(openid || "").trim();
  if (!normalizedOpenid) {
    return {};
  }
  return {
    "x-wechat-openid": normalizedOpenid,
    "x-openid": normalizedOpenid
  };
}

async function syncWechatProfileFromServer(openid) {
  const normalizedOpenid = String(openid || "").trim();
  if (!normalizedOpenid) {
    return null;
  }
  const serverProfile = await request({
    url: "/child-profile/account",
    method: "GET",
    data: {
      openid: normalizedOpenid
    },
    timeout: 15000,
    timeoutMessage: "账号档案同步超时，请稍后重试"
  });
  const profile = normalizeServerProfile(serverProfile, normalizedOpenid);
  if (profile.profileCompleted) {
    saveChildProfile(profile);
  } else {
    clearChildProfile();
    const existingState = getInitializationState() || {};
    const nextState = {
      ...existingState,
      openid: normalizedOpenid,
      deviceId: profile.deviceId || existingState.deviceId || "",
      status: existingState.status || (profile.deviceBound ? "BOUND" : ""),
      updatedAt: Date.now()
    };
    if (nextState.deviceId || nextState.status) {
      saveInitializationState(nextState);
    }
    updateWechatAccountProfile({
      openid: normalizedOpenid,
      deviceId: nextState.deviceId,
      deviceBound: profile.deviceBound || !!nextState.deviceId,
      initializationStatus: nextState.status || ""
    });
  }
  return profile;
}

async function registerRobotDevice(payload) {
  const openid = payload && (payload.openid || payload.userId || payload.ownerOpenid);
  return request({
    url: "/robot-initialization/device/register",
    method: "POST",
    data: payload || {},
    header: buildWechatIdentityHeaders(openid),
    timeout: 20000,
    timeoutMessage: "设备注册超时，请稍后重试"
  });
}

async function authenticateRobotDevice(payload) {
  const openid = payload && (payload.openid || payload.userId || payload.ownerOpenid);
  return request({
    url: "/robot-initialization/device/auth",
    method: "POST",
    data: payload || {},
    header: buildWechatIdentityHeaders(openid),
    timeout: 20000,
    timeoutMessage: "设备认证超时，请稍后重试"
  });
}

async function bindRobotDevice(payload) {
  const openid = payload && (payload.openid || payload.userId || payload.ownerOpenid);
  return request({
    url: "/robot-initialization/device/bind",
    method: "POST",
    data: payload || {},
    header: buildWechatIdentityHeaders(openid),
    timeout: 20000,
    timeoutMessage: "设备绑定超时，请稍后重试"
  });
}

async function createHousehold(payload) {
  const openid = payload && (payload.openid || payload.userId || payload.ownerOpenid);
  return request({
    url: "/robot-initialization/household/create",
    method: "POST",
    data: payload || {},
    header: buildWechatIdentityHeaders(openid),
    timeout: 20000,
    timeoutMessage: "创建家庭超时，请稍后重试"
  });
}

async function initializeRobotProfile(payload) {
  const openid = payload && (payload.openid || payload.userId || payload.ownerOpenid);
  return request({
    url: "/robot-initialization/profile/initialize",
    method: "POST",
    data: payload || {},
    header: buildWechatIdentityHeaders(openid),
    timeout: 20000,
    timeoutMessage: "初始化 Profile 超时，请稍后重试"
  });
}

async function applyInitialRobotConfiguration(payload) {
  const openid = payload && (payload.openid || payload.userId || payload.ownerOpenid);
  return request({
    url: "/robot-initialization/profile/apply",
    method: "POST",
    data: payload || {},
    header: buildWechatIdentityHeaders(openid),
    timeout: 20000,
    timeoutMessage: "保存初始化配置超时，请稍后重试"
  });
}

async function notifyRobotSync(payload) {
  const openid = payload && (payload.openid || payload.userId || payload.ownerOpenid);
  return request({
    url: "/robot-initialization/robot/sync-notify",
    method: "POST",
    data: payload || {},
    header: buildWechatIdentityHeaders(openid),
    timeout: 20000,
    timeoutMessage: "通知机器人同步超时，请稍后重试"
  });
}

function saveLocalFile(tempFilePath) {
  return new Promise((resolve) => {
    if (!tempFilePath || !wx.saveFile) {
      resolve(tempFilePath || "");
      return;
    }

    wx.saveFile({
      tempFilePath,
      success(res) {
        resolve(res.savedFilePath || tempFilePath);
      },
      fail() {
        resolve(tempFilePath);
      }
    });
  });
}

async function saveWechatAvatar(tempFilePath) {
  const avatarUrl = await saveLocalFile(String(tempFilePath || "").trim());
  if (!avatarUrl) {
    throw new Error("微信未返回头像");
  }

  updateWechatAccountProfile({ avatarUrl });
  return avatarUrl;
}

function maskOpenid(openid) {
  const value = String(openid || "").trim();
  if (!value) {
    return "";
  }
  if (value.length <= 10) {
    return value;
  }
  return `${value.slice(0, 6)}...${value.slice(-4)}`;
}

module.exports = {
  bindWechatAccount,
  initializeWechatProfile,
  syncWechatProfileFromServer,
  saveWechatAvatar,
  maskOpenid,
  registerRobotDevice,
  authenticateRobotDevice,
  bindRobotDevice,
  createHousehold,
  initializeRobotProfile,
  applyInitialRobotConfiguration,
  notifyRobotSync
};
