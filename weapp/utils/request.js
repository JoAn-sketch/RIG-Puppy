const { API_BASE_URL } = require("./config");

function request(options) {
  const {
    url,
    method = "GET",
    data = {},
    timeout = 15000,
    header = {},
    timeoutMessage = ""
  } = options || {};

  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_BASE_URL}${url}`,
      method,
      data,
      timeout,
      header: {
        "content-type": "application/json",
        ...header
      },
      success(res) {
        const payload = res.data || {};
        if (res.statusCode >= 200 && res.statusCode < 300 && payload.code === 0) {
          resolve(payload.data);
          return;
        }

        const message = payload.msg || `HTTP ${res.statusCode}`;
        reject(new Error(message));
      },
      fail(err) {
        const rawMessage = err && err.errMsg ? err.errMsg : "network request failed";
        const message = rawMessage.includes("timeout") && timeoutMessage
          ? timeoutMessage
          : rawMessage;
        reject(new Error(message));
      }
    });
  });
}

module.exports = {
  request
};
