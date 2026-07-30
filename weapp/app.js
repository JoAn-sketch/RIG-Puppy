const { hasCompletedChildProfile, getInitializationState } = require("./utils/storage");

App({
  onShow() {
    const currentPages = getCurrentPages();
    if (!currentPages || !currentPages.length) {
      return;
    }

    const currentRoute = currentPages[currentPages.length - 1].route;
    const shouldShowMyProfile = hasCompletedChildProfile();
    const initializationState = getInitializationState();
    const hasInitializedDevice = !!(initializationState && initializationState.deviceId);

    if (shouldShowMyProfile && currentRoute === "pages/profile/index") {
      wx.switchTab({
        url: "/pages/my-profile/index"
      });
      return;
    }

    if (!shouldShowMyProfile && currentRoute === "pages/my-profile/index") {
      if (hasInitializedDevice) {
        wx.reLaunch({
          url: "/pages/profile/index"
        });
        return;
      }
      wx.switchTab({
        url: "/pages/device-pair/index"
      });
      return;
    }

    if (!shouldShowMyProfile && currentRoute === "pages/profile/index" && !hasInitializedDevice) {
      wx.switchTab({
        url: "/pages/device-pair/index"
      });
    }
  }
});
