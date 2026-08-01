const {
  bindWechatAccount,
  initializeWechatProfile,
  saveWechatAvatar
} = require("../../utils/wechat-auth");
const { continueStartupFlow } = require("../../utils/startup-flow");
const {
  getWechatAccount,
  isWechatProfileInitialized,
  markProfileInitialized
} = require("../../utils/storage");

Page({
  data: {
    loggingIn: false,
    needsAvatar: false,
    errorText: ""
  },

  async onOneTapLogin() {
    if (this.data.loggingIn) {
      return;
    }

    this.setData({
      loggingIn: true,
      errorText: ""
    });

    try {
      await bindWechatAccount();
      if (!isWechatProfileInitialized()) {
        this.setData({
          needsAvatar: true,
          errorText: ""
        });
        return;
      }

      wx.showToast({
        title: "登录成功",
        icon: "success"
      });
      continueStartupFlow();
    } catch (err) {
      this.setData({
        errorText: err && err.message ? `登录失败：${err.message}` : "登录失败"
      });
    } finally {
      this.setData({
        loggingIn: false
      });
    }
  },

  async onChooseAvatar(event) {
    if (this.data.loggingIn) {
      return;
    }

    const avatarUrl = event && event.detail ? event.detail.avatarUrl : "";
    if (!avatarUrl) {
      this.setData({
        errorText: "微信未返回头像，请重新选择"
      });
      return;
    }

    this.setData({
      loggingIn: true,
      errorText: ""
    });

    try {
      const account = getWechatAccount() || {};
      const openid = account.openid || await bindWechatAccount();
      const savedAvatarUrl = await saveWechatAvatar(avatarUrl);
      try {
        await initializeWechatProfile({
          openid,
          avatarUrl: savedAvatarUrl,
          gender: "",
          language: "zh-CN"
        });
      } catch (err) {
        // Local avatar initialization is enough for startup; backend sync can be added later.
        console.warn("profile init sync failed", err);
      }
      markProfileInitialized({
        openid,
        avatarUrl: savedAvatarUrl
      });
      wx.showToast({
        title: "登录成功",
        icon: "success"
      });
      continueStartupFlow();
    } catch (err) {
      this.setData({
        errorText: err && err.message ? `头像保存失败：${err.message}` : "头像保存失败"
      });
    } finally {
      this.setData({
        loggingIn: false
      });
    }
  }
});
