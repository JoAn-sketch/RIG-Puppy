const { bindWechatAccount, saveWechatAvatar, syncWechatProfileFromServer } = require("../../utils/wechat-auth");
const {
  getWechatAccount,
  hasCompletedChildProfile,
  getInitializationState,
  updateWechatAccountProfile
} = require("../../utils/storage");

function chooseLocalImage(sourceType) {
  return new Promise((resolve, reject) => {
    wx.chooseImage({
      count: 1,
      sizeType: ["compressed"],
      sourceType,
      success(res) {
        const filePath = res && res.tempFilePaths && res.tempFilePaths[0] ? res.tempFilePaths[0] : "";
        if (!filePath) {
          reject(new Error("未选择图片"));
          return;
        }
        resolve(filePath);
      },
      fail(err) {
        reject(Object.assign(new Error("用户取消选择"), { cancelled: true, rawError: err }));
      }
    });
  });
}

Page({
  data: {
    loggingIn: false,
    savingAvatar: false,
    showAvatarSheet: false,
    pendingOpenid: "",
    avatarUrl: "",
    errorText: ""
  },

  async onOneTapLogin() {
    if (this.data.loggingIn || this.data.savingAvatar) {
      return;
    }

    this.setData({
      loggingIn: true,
      errorText: ""
    });

    try {
      const openid = await bindWechatAccount({ forceRefresh: true });
      await syncWechatProfileFromServer(openid);
      const account = getWechatAccount();
      if (account && account.avatarUrl && account.openid === openid) {
        this.redirectAfterLogin();
        return;
      }

      this.setData({
        pendingOpenid: openid,
        avatarUrl: "",
        showAvatarSheet: true
      });
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
    if (this.data.savingAvatar || this.data.loggingIn) {
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
      savingAvatar: true,
      errorText: ""
    });

    try {
      const savedAvatarUrl = await saveWechatAvatar(avatarUrl);
      updateWechatAccountProfile({
        avatarUrl: savedAvatarUrl,
        openid: this.data.pendingOpenid
      });
      this.setData({
        avatarUrl: savedAvatarUrl,
        showAvatarSheet: false,
        pendingOpenid: ""
      });
      wx.showToast({
        title: "登录成功",
        icon: "success"
      });
      this.redirectAfterLogin();
    } catch (err) {
      if (err && (err.cancelled || String(err.errMsg || "").includes("cancel"))) {
        return;
      }
      this.setData({
        errorText: err && err.message ? `头像保存失败：${err.message}` : "头像保存失败"
      });
    } finally {
      this.setData({
        savingAvatar: false
      });
    }
  },

  async onPickAlbumAvatar() {
    await this.onPickLocalAvatar(["album"]);
  },

  async onTakePhotoAvatar() {
    await this.onPickLocalAvatar(["camera"]);
  },

  async onPickLocalAvatar(sourceType) {
    if (this.data.savingAvatar || this.data.loggingIn) {
      return;
    }

    this.setData({
      savingAvatar: true,
      errorText: ""
    });

    try {
      const filePath = await chooseLocalImage(sourceType);
      const savedAvatarUrl = await saveWechatAvatar(filePath);
      updateWechatAccountProfile({
        avatarUrl: savedAvatarUrl,
        openid: this.data.pendingOpenid
      });
      this.setData({
        avatarUrl: savedAvatarUrl,
        showAvatarSheet: false,
        pendingOpenid: ""
      });
      wx.showToast({
        title: "登录成功",
        icon: "success"
      });
      this.redirectAfterLogin();
    } catch (err) {
      if (err && (err.cancelled || String(err.errMsg || "").includes("cancel"))) {
        return;
      }
      this.setData({
        errorText: err && err.message ? `头像保存失败：${err.message}` : "头像保存失败"
      });
    } finally {
      this.setData({
        savingAvatar: false
      });
    }
  },

  onCloseAvatarSheet() {
    if (this.data.savingAvatar) {
      return;
    }

    this.setData({
      showAvatarSheet: false
    });
  },

  noop() {},

  redirectAfterLogin() {
    if (hasCompletedChildProfile()) {
      wx.switchTab({
        url: "/pages/my-profile/index"
      });
      return;
    }

    const initializationState = getInitializationState();
    if (initializationState && initializationState.deviceId) {
      wx.reLaunch({
        url: "/pages/profile/index"
      });
      return;
    }

    wx.switchTab({
      url: "/pages/device-pair/index"
    });
  }
});
