const {
  hasCompletedChildProfile,
  getInitializationState
} = require("./storage");

function getMainEntryRoute() {
  if (hasCompletedChildProfile()) {
    return "/pages/my-profile/index";
  }

  const initializationState = getInitializationState();
  if (initializationState && initializationState.deviceId) {
    return "/pages/profile/index";
  }

  return "/pages/device-onboarding/index";
}

function getStartupRoute() {
  return getMainEntryRoute();
}

function navigateToRoute(route) {
  if (route === "/pages/my-profile/index" || route === "/pages/today-companion/index" || route === "/pages/device-pair/index") {
    wx.switchTab({ url: route });
    return;
  }

  wx.reLaunch({ url: route });
}

function continueStartupFlow() {
  navigateToRoute(getStartupRoute());
}

function enterMainFlow() {
  navigateToRoute(getMainEntryRoute());
}

module.exports = {
  getMainEntryRoute,
  getStartupRoute,
  navigateToRoute,
  continueStartupFlow,
  enterMainFlow
};
