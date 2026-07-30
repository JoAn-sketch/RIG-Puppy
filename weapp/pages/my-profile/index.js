const { syncWechatProfileFromServer } = require("../../utils/wechat-auth");
const {
  getChildProfile,
  getWechatAccount,
  hasCompletedChildProfile
} = require("../../utils/storage");

Page({
  data: {
    hasProfile: false,
    profileItems: [],
    avatarUrl: "",
    errorText: ""
  },

  async onShow() {
    this.refreshAccountState();
    const account = getWechatAccount();
    if (account && account.openid) {
      try {
        await syncWechatProfileFromServer(account.openid);
      } catch (err) {
        this.setData({
          errorText: err && err.message ? `档案同步失败：${err.message}` : "档案同步失败"
        });
      }
    }
    const profile = getChildProfile();
    if (!hasCompletedChildProfile()) {
      this.setData({
        hasProfile: false,
        profileItems: [],
      });
      wx.reLaunch({
        url: "/pages/profile/index"
      });
      return;
    }

    const profileItems = [
      { label: "我该怎么称呼你", value: profile.nickname || "-" },
      { label: "你怎么称呼这个机器人", value: profile.robotName || "-" },
      { label: "年龄", value: profile.age ? `${profile.age} 岁` : "-" },
      { label: "年龄分档", value: profile.ageGroup || "-" },
      { label: "绑定设备", value: profile.deviceId || "-" },
      { label: "我最喜欢哪些东西", value: (profile.favoriteThings || []).join("、") || "-" },
      { label: "最喜欢的小狗类型", value: profile.favoriteDogType || "-" },
      { label: "最想和 Puppy 做什么", value: profile.playWish || "-" },
      { label: "家长希望机器人帮助什么", value: (profile.parentHelp || []).join("、") || "-" }
    ];

    this.setData({
      hasProfile: true,
      profileItems,
      errorText: ""
    });
  },

  refreshAccountState() {
    const account = getWechatAccount();
    const avatarUrl = account && account.avatarUrl ? account.avatarUrl : "";
    this.setData({
      avatarUrl
    });
  }
});
