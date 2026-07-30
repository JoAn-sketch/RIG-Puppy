const {
  bindWechatAccount,
  applyInitialRobotConfiguration,
  notifyRobotSync
} = require("../../utils/wechat-auth");
const {
  saveChildProfile,
  getChildProfile,
  hasBoundWechatAccount,
  getInitializationState,
  saveInitializationState,
  updateWechatAccountProfile
} = require("../../utils/storage");

const AGE_OPTIONS = [3, 4, 5, 6, 7, 8, 9, 10, 11];
const FAVORITE_THING_OPTIONS = [
  "🐶 小动物",
  "🦖 恐龙",
  "🚀 太空",
  "🚗 汽车和交通工具",
  "🌳 大自然",
  "⚽ 运动",
  "🎨 画画和手工",
  "🎵 音乐和跳舞",
  "📚 故事和绘本",
  "🧩 猜谜和小游戏"
];

function buildFavoriteThingOptions(selectedValues) {
  const selectedList = Array.isArray(selectedValues) ? selectedValues : [];
  return FAVORITE_THING_OPTIONS.map((value) => ({
    value,
    selected: selectedList.includes(value)
  }));
}

function mapAgeGroup(age) {
  if (age >= 3 && age <= 5) {
    return "3-5";
  }
  if (age >= 6 && age <= 8) {
    return "6-8";
  }
  if (age >= 9 && age <= 11) {
    return "9-11";
  }
  return "6-8";
}

Page({
  data: {
    nickname: "",
    robotName: "",
    ageOptions: AGE_OPTIONS,
    favoriteThingOptions: buildFavoriteThingOptions([]),
    favoriteThings: [],
    ageIndex: -1,
    avatarUrl: "",
    submitting: false,
    errorText: "",
    submitStepText: ""
  },

  onLoad() {
    if (!hasBoundWechatAccount()) {
      wx.reLaunch({
        url: "/pages/launch/index"
      });
      return;
    }

    const profile = getChildProfile();
    if (!profile) {
      return;
    }

    const ageIndex = AGE_OPTIONS.indexOf(profile.age);
    const favoriteThings = Array.isArray(profile.favoriteThings) ? profile.favoriteThings : [];
    this.setData({
      nickname: profile.nickname || "",
      robotName: profile.robotName || "",
      favoriteThings,
      favoriteThingOptions: buildFavoriteThingOptions(favoriteThings),
      ageIndex
    });
  },

  onNicknameInput(event) {
    this.setData({
      nickname: (event.detail.value || "").trimStart(),
      errorText: "",
      submitStepText: ""
    });
  },

  onRobotNameInput(event) {
    this.setData({
      robotName: (event.detail.value || "").trimStart(),
      errorText: "",
      submitStepText: ""
    });
  },

  onAgeChange(event) {
    this.setData({
      ageIndex: Number(event.detail.value),
      errorText: "",
      submitStepText: ""
    });
  },

  onFavoriteThingTap(event) {
    const value = event.currentTarget.dataset.value;
    const currentValues = Array.isArray(this.data.favoriteThings) ? this.data.favoriteThings : [];
    const exists = currentValues.includes(value);

    if (exists) {
      const nextFavoriteThings = currentValues.filter((item) => item !== value);
      this.setData({
        favoriteThings: nextFavoriteThings,
        favoriteThingOptions: buildFavoriteThingOptions(nextFavoriteThings),
        errorText: "",
        submitStepText: ""
      });
      return;
    }

    if (currentValues.length >= 3) {
      this.setData({
        errorText: "最多同时选择 3 个"
      });
      return;
    }

    const nextFavoriteThings = [...currentValues, value];
    this.setData({
      favoriteThings: nextFavoriteThings,
      favoriteThingOptions: buildFavoriteThingOptions(nextFavoriteThings),
      errorText: "",
      submitStepText: ""
    });
  },

  async ensureOpenid() {
    const openid = await bindWechatAccount();
    return openid;
  },

  async onSubmit() {
    const nickname = (this.data.nickname || "").trim();
    const robotName = (this.data.robotName || "").trim();
    const favoriteThings = Array.isArray(this.data.favoriteThings) ? this.data.favoriteThings : [];
    if (!nickname) {
      this.setData({ errorText: "请先填写称呼" });
      return;
    }
    if (!robotName) {
      this.setData({ errorText: "请先填写你怎么称呼这个机器人" });
      return;
    }
    if (!favoriteThings.length) {
      this.setData({ errorText: "请选择 1-3 个你最喜欢的东西" });
      return;
    }
    if (this.data.ageIndex < 0) {
      this.setData({ errorText: "请选择年龄" });
      return;
    }

    const age = AGE_OPTIONS[this.data.ageIndex];

    this.setData({
      submitting: true,
      errorText: "",
      submitStepText: "正在获取微信身份..."
    });

    try {
      const openid = await this.ensureOpenid();
      const initializationState = getInitializationState() || {};
      const existingProfile = getChildProfile() || {};
      const deviceId = initializationState.deviceId || existingProfile.deviceId || "";
      const householdId = initializationState.householdId || existingProfile.householdId || "";
      if (!deviceId) {
        this.setData({
          errorText: "请先完成 BLE 配网并绑定 Puppy"
        });
        setTimeout(() => {
          wx.switchTab({ url: "/pages/device-pair/index" });
        }, 800);
        return;
      }

      this.setData({
        submitStepText: "正在保存初始化配置..."
      });

      await applyInitialRobotConfiguration({
        openid,
        deviceId,
        age,
        nickname,
        robotNamePreference: robotName,
        interests: favoriteThings
      });

      this.setData({
        submitStepText: "正在通知机器人同步..."
      });
      await notifyRobotSync({ deviceId });

      saveInitializationState({
        ...initializationState,
        openid,
        deviceId,
        householdId,
        status: "READY",
        step: "COMPLETE",
        syncNotified: true
      });
      updateWechatAccountProfile({
        openid,
        deviceId,
        householdId,
        initializationStatus: "READY"
      });
      saveChildProfile({
        profileCompleted: true,
        nickname,
        robotName,
        favoriteThings,
        age,
        ageGroup: mapAgeGroup(age),
        deviceId,
        householdId,
        openid,
        avatarUrl: this.data.avatarUrl
      });

      wx.showToast({
        title: "提交成功",
        icon: "success"
      });

      wx.switchTab({
        url: "/pages/my-profile/index"
      });
    } catch (err) {
      this.setData({
        errorText: err && err.message ? `提交失败：${err.message}` : "提交失败"
      });
    } finally {
      this.setData({
        submitting: false,
        submitStepText: ""
      });
    }
  }
});
