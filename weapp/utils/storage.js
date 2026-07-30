const CHILD_PROFILE_STORAGE_KEY = "puppy_child_profile";
const WECHAT_OPENID_STORAGE_KEY = "puppy_wechat_openid";
const WECHAT_ACCOUNT_STORAGE_KEY = "puppy_wechat_account";
const INITIALIZATION_STATE_STORAGE_KEY = "puppy_initialization_state";

function buildChildProfileStorageKey(openid) {
  const normalizedOpenid = String(openid || "").trim();
  return normalizedOpenid ? `${CHILD_PROFILE_STORAGE_KEY}_${normalizedOpenid}` : CHILD_PROFILE_STORAGE_KEY;
}

function saveChildProfile(profile) {
  const account = getWechatAccount();
  const openid = (profile && profile.openid) || (account && account.openid) || "";
  const nextProfile = {
    ...(profile || {}),
    openid
  };
  wx.setStorageSync(buildChildProfileStorageKey(openid), nextProfile);
  wx.setStorageSync(CHILD_PROFILE_STORAGE_KEY, nextProfile);
}

function clearChildProfile() {
  const account = getWechatAccount();
  const openid = account && account.openid ? account.openid : "";
  wx.removeStorageSync(buildChildProfileStorageKey(openid));
  if (!openid) {
    wx.removeStorageSync(CHILD_PROFILE_STORAGE_KEY);
  }
}

function saveInitializationState(state) {
  const nextState = {
    ...(state || {}),
    updatedAt: Date.now()
  };
  wx.setStorageSync(INITIALIZATION_STATE_STORAGE_KEY, nextState);
}

function getInitializationState() {
  const state = wx.getStorageSync(INITIALIZATION_STATE_STORAGE_KEY) || null;
  return state && typeof state === "object" ? state : null;
}

function clearInitializationState() {
  wx.removeStorageSync(INITIALIZATION_STATE_STORAGE_KEY);
}

function isInitializationCompleted() {
  const state = getInitializationState();
  return !!(state && state.status === "READY");
}

function hasLegacyRequiredProfileFields(profile) {
  if (!profile || typeof profile !== "object") {
    return false;
  }

  const hasNickname = typeof profile.nickname === "string" && profile.nickname.trim().length > 0;
  const hasAge = Number.isInteger(profile.age) && profile.age >= 3 && profile.age <= 11;

  return hasNickname && hasAge;
}

function getChildProfile() {
  const account = getWechatAccount();
  const openid = account && account.openid ? account.openid : "";
  let profile = wx.getStorageSync(buildChildProfileStorageKey(openid)) || null;
  if (!profile && openid) {
    const legacyProfile = wx.getStorageSync(CHILD_PROFILE_STORAGE_KEY) || null;
    if (legacyProfile && typeof legacyProfile === "object" && legacyProfile.openid === openid) {
      profile = legacyProfile;
      wx.setStorageSync(buildChildProfileStorageKey(openid), legacyProfile);
    }
  }
  if (!profile || typeof profile !== "object") {
    return null;
  }
  if (openid && profile.openid && profile.openid !== openid) {
    return null;
  }

  if (profile.profileCompleted === true) {
    return profile;
  }

  if (!hasLegacyRequiredProfileFields(profile)) {
    return profile;
  }

  const migratedProfile = {
    ...profile,
    profileCompleted: true
  };
  saveChildProfile(migratedProfile);
  return migratedProfile;
}

function isChildProfileCompleted(profile) {
  if (!profile || typeof profile !== "object") {
    return false;
  }

  if (profile.profileCompleted === true) {
    return true;
  }

  return hasLegacyRequiredProfileFields(profile);
}

function hasCompletedChildProfile() {
  const profile = getChildProfile();
  if (!isChildProfileCompleted(profile)) {
    return false;
  }

  const account = getWechatAccount();
  if (account && account.openid && profile.openid && account.openid !== profile.openid) {
    return false;
  }

  return true;
}

function saveWechatOpenid(openid) {
  const normalizedOpenid = String(openid || "").trim();
  wx.setStorageSync(WECHAT_OPENID_STORAGE_KEY, normalizedOpenid);
  if (normalizedOpenid) {
    const existingAccount = wx.getStorageSync(WECHAT_ACCOUNT_STORAGE_KEY) || {};
    const shouldMergeExisting = !existingAccount.openid || existingAccount.openid === normalizedOpenid;
    wx.setStorageSync(WECHAT_ACCOUNT_STORAGE_KEY, {
      ...(shouldMergeExisting ? existingAccount : {}),
      openid: normalizedOpenid,
      wechatBound: true,
      boundAt: Date.now()
    });
  }
}

function clearWechatAccount() {
  wx.removeStorageSync(WECHAT_OPENID_STORAGE_KEY);
  wx.removeStorageSync(WECHAT_ACCOUNT_STORAGE_KEY);
}

function updateWechatAccountProfile(profile) {
  const currentAccount = wx.getStorageSync(WECHAT_ACCOUNT_STORAGE_KEY) || {};
  const nextOpenid = (profile && profile.openid) || currentAccount.openid || "";

  wx.setStorageSync(WECHAT_ACCOUNT_STORAGE_KEY, {
    ...currentAccount,
    ...(profile || {}),
    openid: nextOpenid,
    wechatBound: !!nextOpenid,
    updatedAt: Date.now()
  });
}

function getWechatOpenid() {
  return wx.getStorageSync(WECHAT_OPENID_STORAGE_KEY) || "";
}

function getWechatAccount() {
  const account = wx.getStorageSync(WECHAT_ACCOUNT_STORAGE_KEY) || null;
  if (account && typeof account === "object" && (account.openid || account.avatarUrl)) {
    return account;
  }

  const openid = getWechatOpenid();
  if (!openid) {
    return null;
  }

  return {
    openid,
    wechatBound: true,
    boundAt: 0
  };
}

function hasBoundWechatAccount() {
  const account = getWechatAccount();
  return !!(account && account.openid && account.avatarUrl);
}

module.exports = {
  saveChildProfile,
  clearChildProfile,
  getChildProfile,
  isChildProfileCompleted,
  hasCompletedChildProfile,
  saveInitializationState,
  getInitializationState,
  clearInitializationState,
  isInitializationCompleted,
  saveWechatOpenid,
  clearWechatAccount,
  updateWechatAccountProfile,
  getWechatOpenid,
  getWechatAccount,
  hasBoundWechatAccount
};
