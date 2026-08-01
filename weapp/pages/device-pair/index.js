const {
  API_BASE_URL,
  PUPPY_OTA_URL,
  PUPPY_BLE_NAME_PREFIX,
  PUPPY_BLE_SERVICE_UUID,
  PUPPY_BLE_WIFI_WRITE_UUID,
  PUPPY_BLE_STATUS_NOTIFY_UUID
} = require("../../utils/config");
const {
  bindWechatAccount,
  syncWechatProfileFromServer,
  registerRobotDevice,
  authenticateRobotDevice,
  bindRobotDevice,
  createHousehold,
  initializeRobotProfile
} = require("../../utils/wechat-auth");
const {
  updateWechatAccountProfile,
  saveInitializationState
} = require("../../utils/storage");

const BLE_WRITE_CHUNK_SIZE = 20;
const PROVISIONING_TOTAL_TIMEOUT_MS = 120000;
const PROVISIONING_SUCCESS_STATUSES = new Set([
  "ok",
  "success",
  "wifi_connected",
  "connected",
  "bind_ready",
  "credentials_saved",
  "waiting_for_credentials"
]);
const PROVISIONING_PENDING_STATUSES = new Set([
  "wifi_connecting",
  "connecting",
  "wifi_joining",
  "wifi_start",
  "wifi_started"
]);
const PROVISIONING_FAILURE_STATUSES = new Set([
  "fail",
  "failed",
  "error",
  "wifi_failed",
  "wifi_fail",
  "wifi_connect_failed",
  "wifi_password_error",
  "wifi_no_ap",
  "wifi_timeout"
]);

function normalizeUuid(value) {
  return String(value || "").trim().toUpperCase();
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function withTimeout(promise, ms, message) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(message)), ms);
    Promise.resolve(promise)
      .then((value) => {
        clearTimeout(timer);
        resolve(value);
      })
      .catch((err) => {
        clearTimeout(timer);
        reject(err);
      });
  });
}

function promisifyWx(fnName, options = {}) {
  return new Promise((resolve, reject) => {
    wx[fnName]({
      ...options,
      success: resolve,
      fail: reject
    });
  });
}

function utf8ToArrayBuffer(text) {
  const bytes = [];
  const value = String(text || "");
  for (let i = 0; i < value.length; i += 1) {
    let code = value.charCodeAt(i);
    if (code < 0x80) {
      bytes.push(code);
    } else if (code < 0x800) {
      bytes.push(0xc0 | (code >> 6));
      bytes.push(0x80 | (code & 0x3f));
    } else if (code >= 0xd800 && code <= 0xdbff) {
      i += 1;
      const next = value.charCodeAt(i);
      code = 0x10000 + (((code & 0x3ff) << 10) | (next & 0x3ff));
      bytes.push(0xf0 | (code >> 18));
      bytes.push(0x80 | ((code >> 12) & 0x3f));
      bytes.push(0x80 | ((code >> 6) & 0x3f));
      bytes.push(0x80 | (code & 0x3f));
    } else {
      bytes.push(0xe0 | (code >> 12));
      bytes.push(0x80 | ((code >> 6) & 0x3f));
      bytes.push(0x80 | (code & 0x3f));
    }
  }
  return new Uint8Array(bytes).buffer;
}

function arrayBufferToUtf8(buffer) {
  const bytes = new Uint8Array(buffer || []);
  let output = "";
  let index = 0;
  while (index < bytes.length) {
    const first = bytes[index];
    if (first < 0x80) {
      output += String.fromCharCode(first);
      index += 1;
    } else if ((first & 0xe0) === 0xc0) {
      const second = bytes[index + 1] || 0;
      output += String.fromCharCode(((first & 0x1f) << 6) | (second & 0x3f));
      index += 2;
    } else if ((first & 0xf0) === 0xe0) {
      const second = bytes[index + 1] || 0;
      const third = bytes[index + 2] || 0;
      output += String.fromCharCode(((first & 0x0f) << 12) | ((second & 0x3f) << 6) | (third & 0x3f));
      index += 3;
    } else {
      const second = bytes[index + 1] || 0;
      const third = bytes[index + 2] || 0;
      const fourth = bytes[index + 3] || 0;
      const codePoint = ((first & 0x07) << 18) | ((second & 0x3f) << 12) | ((third & 0x3f) << 6) | (fourth & 0x3f);
      const offset = codePoint - 0x10000;
      output += String.fromCharCode(0xd800 + (offset >> 10), 0xdc00 + (offset & 0x3ff));
      index += 4;
    }
  }
  return output;
}

function sliceArrayBuffer(buffer, start, end) {
  return buffer.slice(start, end);
}

function getDeviceName(device) {
  return String(device && (device.localName || device.name) || "").trim();
}

function isPuppyDevice(device) {
  const name = getDeviceName(device);
  return name.toLowerCase().startsWith(PUPPY_BLE_NAME_PREFIX.toLowerCase());
}

function extractDeviceKey(device) {
  const name = getDeviceName(device);
  const suffix = name.replace(new RegExp(`^${PUPPY_BLE_NAME_PREFIX}[-_\\s]*`, "i"), "").trim();
  if (!suffix) {
    return "";
  }
  if (/^[0-9a-fA-F]{12}$/.test(suffix)) {
    return suffix.match(/.{1,2}/g).join(":").toUpperCase();
  }
  return suffix;
}

function normalizeDeviceId(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "";
  }
  const compact = raw.replace(/[^0-9a-fA-F]/g, "");
  if (compact.length === 12) {
    return compact.match(/.{1,2}/g).join(":").toLowerCase();
  }
  return raw.toLowerCase();
}

function parseProvisioningStatus(text) {
  const value = String(text || "").trim();
  if (!value) {
    return null;
  }
  try {
    return JSON.parse(value);
  } catch (err) {
    return null;
  }
}

function getProvisioningStatus(value) {
  return String(value && value.status || "").trim().toLowerCase();
}

function isProvisioningTerminalStatus(value) {
  const status = getProvisioningStatus(value);
  if (!status) {
    return true;
  }
  return PROVISIONING_SUCCESS_STATUSES.has(status) || PROVISIONING_FAILURE_STATUSES.has(status);
}

function looksLikeFiveGHzSsid(ssid) {
  const value = String(ssid || "").trim();
  if (!value) {
    return false;
  }
  return /(^|[\s_\-])5g(hz)?($|[\s_\-])/i.test(value)
    || /5ghz/i.test(value)
    || /[\s_\-]5g$/i.test(value);
}

function pickFirstString(...values) {
  for (let i = 0; i < values.length; i += 1) {
    const value = String(values[i] || "").trim();
    if (value) {
      return value;
    }
  }
  return "";
}

function extractDeviceAuthCredentials(authResult) {
  const websocket = authResult && authResult.websocket && typeof authResult.websocket === "object"
    ? authResult.websocket
    : {};
  const accessToken = pickFirstString(
    authResult && authResult.accessToken,
    authResult && authResult.access_token,
    authResult && authResult.token,
    authResult && authResult.websocketToken,
    websocket.token
  );
  return {
    accessToken,
    refreshToken: pickFirstString(
      authResult && authResult.refreshToken,
      authResult && authResult.refresh_token
    ),
    websocketUrl: pickFirstString(
      authResult && authResult.websocketUrl,
      authResult && authResult.websocket_url,
      websocket.url
    ),
    authUrl: pickFirstString(
      authResult && authResult.authUrl,
      authResult && authResult.auth_url
    ),
    expireSeconds: Number(
      (authResult && (authResult.expireSeconds || authResult.expire_seconds))
      || 0
    )
  };
}

function isFiveGHzWifi(item) {
  if (!item) {
    return false;
  }
  const frequency = Number(item.frequency || item.freq || 0);
  if (frequency >= 4900) {
    return true;
  }
  const channel = Number(item.channel || 0);
  if (channel > 14) {
    return true;
  }
  return looksLikeFiveGHzSsid(item.SSID);
}

function filterSupportedWifiList(rawList) {
  const source = Array.isArray(rawList) ? rawList : [];
  const supported = source
    .filter((item) => item && item.SSID && !isFiveGHzWifi(item))
    .sort((a, b) => Number(b.signalStrength || 0) - Number(a.signalStrength || 0));
  return {
    supported,
    hiddenCount: source.filter((item) => item && item.SSID && isFiveGHzWifi(item)).length
  };
}

Page({
  data: {
    scanning: false,
    connecting: false,
    provisioning: false,
    gettingWifiList: false,
    devices: [],
    wifiList: [],
    selectedDeviceId: "",
    selectedDeviceName: "",
    ssid: "",
    password: "",
    deviceKey: "",
    canProvision: false,
    provisionHint: "需要先选择 Puppy，并填写 Wi‑Fi 名称和密码。",
    provisionLogs: [],
    statusText: "等待扫描 Puppy。",
    wifiListHint: "获取附近 Wi‑Fi 是可选项；如果拿不到列表，直接手动输入 Wi‑Fi 名称即可。",
    ssidWarning: "",
    errorText: ""
  },

  onLoad() {
    if (wx.onGetWifiList) {
      wx.onGetWifiList((res) => {
        const result = filterSupportedWifiList((res && res.wifiList) || []);
        this.setData({
          wifiList: result.supported,
          gettingWifiList: false,
          wifiListHint: result.hiddenCount
            ? `已隐藏 ${result.hiddenCount} 个 Puppy 不支持的 5GHz Wi‑Fi。请选择 2.4GHz Wi‑Fi。`
            : "已显示 Puppy 支持的 2.4GHz Wi‑Fi。"
        });
      });
    }
    this.tryLoadConnectedWifi();
  },

  onUnload() {
    this.stopBluetooth();
  },

  async tryLoadConnectedWifi() {
    if (!wx.startWifi || !wx.getConnectedWifi) {
      return;
    }
    try {
      await promisifyWx("startWifi");
      const result = await promisifyWx("getConnectedWifi");
      const ssid = result && result.wifi ? result.wifi.SSID : "";
      if (ssid) {
        if (isFiveGHzWifi(result.wifi)) {
          this.setData({
            ssid: "",
            ssidWarning: "当前手机连接的可能是 5GHz Wi‑Fi，Puppy 不支持。请切换到 2.4GHz 后再配网。"
          });
          this.updateCanProvision();
          return;
        }
        this.setData({ ssid });
        this.updateCanProvision();
      }
    } catch (err) {
      // 用户仍可手动输入 Wi-Fi 名称。
    }
  },

  async onGetWifiListTap() {
    if (!wx.startWifi || !wx.getWifiList) {
      this.setData({
        gettingWifiList: false,
        wifiListHint: "当前微信版本不支持获取 Wi‑Fi 列表，请直接手动输入 Wi‑Fi 名称。",
        errorText: ""
      });
      return;
    }
    this.setData({
      gettingWifiList: true,
      wifiListHint: "正在请求 Wi‑Fi 列表；如果微信没有返回，仍然可以手动输入 Wi‑Fi 名称。",
      errorText: ""
    });
    try {
      await promisifyWx("startWifi");
      await this.ensureWifiListPermission();
      await promisifyWx("getWifiList");
      setTimeout(() => {
        if (this.data.gettingWifiList) {
          this.setData({
            gettingWifiList: false,
            wifiListHint: "微信没有返回 Wi‑Fi 列表。请直接手动输入 Wi‑Fi 名称；真机需要打开定位、Wi‑Fi 和小程序定位权限。"
          });
        }
      }, 5000);
    } catch (err) {
      this.setData({
        gettingWifiList: false,
        wifiListHint: this.formatWifiListError(err),
        errorText: ""
      });
    }
  },

  async ensureWifiListPermission() {
    if (!wx.authorize) {
      return;
    }
    try {
      await promisifyWx("authorize", { scope: "scope.userLocation" });
    } catch (err) {
      // Wi-Fi 列表依赖系统位置权限；拒绝后仍允许手动输入 SSID。
    }
  },

  onSelectWifi(event) {
    const ssid = event.currentTarget.dataset.ssid || "";
    if (looksLikeFiveGHzSsid(ssid)) {
      this.setData({
        ssid: "",
        ssidWarning: "这个 Wi‑Fi 看起来是 5GHz，Puppy 不支持。请选择 2.4GHz Wi‑Fi。",
        errorText: ""
      });
      this.updateCanProvision();
      return;
    }
    this.setData({
      ssid,
      ssidWarning: "",
      errorText: ""
    });
    this.updateCanProvision();
  },

  async onScanTap() {
    if (this.data.scanning || this.data.connecting || this.data.provisioning) {
      return;
    }
    this.setData({
      scanning: true,
      devices: [],
      selectedDeviceId: "",
      selectedDeviceName: "",
      errorText: "",
      statusText: "正在打开蓝牙并扫描 Puppy..."
    });
    this.updateCanProvision();

    try {
      await promisifyWx("openBluetoothAdapter");
      wx.onBluetoothDeviceFound(this.handleBluetoothDeviceFound.bind(this));
      await promisifyWx("startBluetoothDevicesDiscovery", {
        allowDuplicatesKey: false,
        interval: 0
      });
      await sleep(8000);
      await this.stopDiscoveryOnly();
      this.setData({
        scanning: false,
        statusText: this.data.devices.length ? "请选择要配网的 Puppy。" : "没有发现 Puppy，请确认设备在配网模式。"
      });
    } catch (err) {
      this.setData({
        scanning: false,
        errorText: this.formatBluetoothError(err),
        statusText: "扫描失败。"
      });
    }
  },

  handleBluetoothDeviceFound(res) {
    const foundDevices = (res && res.devices) || [];
    const nextDevices = [...this.data.devices];
    let changed = false;
    foundDevices.forEach((device) => {
      if (!isPuppyDevice(device)) {
        return;
      }
      const existingIndex = nextDevices.findIndex((item) => item.deviceId === device.deviceId);
      const item = {
        ...device,
        name: getDeviceName(device) || "Puppy",
        deviceKey: extractDeviceKey(device)
      };
      if (existingIndex >= 0) {
        nextDevices[existingIndex] = {
          ...nextDevices[existingIndex],
          ...item
        };
      } else {
        nextDevices.push(item);
      }
      changed = true;
    });
    if (changed) {
      this.setData({ devices: nextDevices });
    }
  },

  onSelectDevice(event) {
    const deviceId = event.currentTarget.dataset.deviceId;
    const device = this.data.devices.find((item) => item.deviceId === deviceId);
    if (!device) {
      return;
    }
    this.setData({
      selectedDeviceId: device.deviceId,
      selectedDeviceName: device.name,
      deviceKey: device.deviceKey || this.data.deviceKey,
      errorText: "",
      statusText: `已选择 ${device.name}。`
    });
    this.updateCanProvision();
  },

  onSsidInput(event) {
    const ssid = event.detail.value || "";
    this.setData({
      ssid,
      ssidWarning: looksLikeFiveGHzSsid(ssid)
        ? "这个 Wi‑Fi 名称看起来是 5GHz，Puppy 不支持。请填写 2.4GHz Wi‑Fi。"
        : "",
      errorText: ""
    });
    this.updateCanProvision();
  },

  onPasswordInput(event) {
    this.setData({ password: event.detail.value || "", errorText: "" });
    this.updateCanProvision();
  },

  updateCanProvision() {
    const missing = this.getProvisionMissingItems();
    this.setData({
      canProvision: missing.length === 0,
      provisionHint: missing.length
        ? `还差：${missing.join("、")}。`
        : "信息已填好，可以发送配网信息。"
    });
  },

  getProvisionMissingItems() {
    const missing = [];
    if (!this.data.selectedDeviceId) {
      missing.push("选择 Puppy");
    }
    if (!this.data.ssid.trim()) {
      missing.push("Wi‑Fi 名称");
    } else if (looksLikeFiveGHzSsid(this.data.ssid)) {
      missing.push("2.4GHz Wi‑Fi");
    }
    if (!this.data.password) {
      missing.push("Wi‑Fi 密码");
    }
    return missing;
  },

  async onProvisionTap() {
    if (this.data.provisioning || this.data.connecting) {
      return;
    }
    const missing = this.getProvisionMissingItems();
    if (missing.length) {
      const message = `还不能发送，请先完成：${missing.join("、")}`;
      this.setData({
        errorText: message,
        statusText: "配网信息还没有填完整。"
      });
      wx.showToast({ title: "信息未填完整", icon: "none" });
      return;
    }

    this.setData({
      provisioning: true,
      connecting: true,
      errorText: "",
      provisionLogs: [],
      statusText: "正在连接 Puppy 蓝牙..."
    });
    this.appendProvisionLog("开始配网");

    try {
      const boundDeviceId = await withTimeout(
        this.runProvisioningFlow(),
        PROVISIONING_TOTAL_TIMEOUT_MS,
        "配网总流程超时，请重新让 Puppy 进入配网模式后再试"
      );
      this.appendProvisionLog(`初始化完成：${boundDeviceId}`);
      wx.showToast({ title: "绑定成功", icon: "success" });
      setTimeout(() => {
        wx.reLaunch({ url: "/pages/profile/index" });
      }, 800);
    } catch (err) {
      this.setData({
        errorText: err && err.message ? err.message : "配网失败",
        statusText: "配网失败，请确认 Puppy 仍在配网模式。"
      });
    } finally {
      this.setData({
        provisioning: false,
        connecting: false
      });
      this.updateCanProvision();
    }
  },

  async runProvisioningFlow() {
    const bleTarget = await this.connectProvisioningBle();
    this.setData({
      connecting: false,
      statusText: "正在发送 Wi‑Fi 配置信息..."
    });

    const payload = {
      type: "wifi_provision",
      version: 1,
      ssid: this.data.ssid.trim(),
      password: this.data.password,
      serverUrl: PUPPY_OTA_URL,
      otaUrl: PUPPY_OTA_URL,
      apiBaseUrl: API_BASE_URL,
      timestamp: Date.now()
    };
    const statusWaiter = this.prepareProvisioningStatusWaiter(bleTarget);
    await this.writeProvisioningPayload(bleTarget, JSON.stringify(payload) + "\n");

    this.setData({ statusText: "Wi‑Fi 已发送，等待 Puppy 返回连接结果..." });
    this.appendProvisionLog("Wi‑Fi 信息已写入 BLE");
    const provisioningResult = await this.resolveProvisioningResult(statusWaiter, 25000);
    const initialization = await this.completeInitializationFlow(provisioningResult);
    await this.sendActivationCredentials(bleTarget, initialization.deviceId, initialization.authResult);
    this.setData({ statusText: `Puppy 初始化完成：${initialization.deviceId}` });
    return initialization.deviceId;
  },

  appendProvisionLog(text) {
    const logs = this.data.provisionLogs || [];
    const time = new Date();
    const timestamp = `${String(time.getHours()).padStart(2, "0")}:${String(time.getMinutes()).padStart(2, "0")}:${String(time.getSeconds()).padStart(2, "0")}`;
    this.setData({
      provisionLogs: [...logs.slice(-11), `${timestamp} ${text}`]
    });
  },

  async connectProvisioningBle() {
    const deviceId = this.data.selectedDeviceId;
    this.appendProvisionLog("停止蓝牙扫描");
    await this.stopDiscoveryOnly();
    this.appendProvisionLog("连接 Puppy 蓝牙");
    await withTimeout(
      promisifyWx("createBLEConnection", { deviceId, timeout: 10000 }),
      12000,
      "连接 Puppy 蓝牙超时，请确认设备仍在配网模式并靠近手机"
    );
    this.setData({ statusText: "已连接 Puppy，正在读取 BLE 服务..." });
    this.appendProvisionLog("读取 BLE 服务");
    const servicesResult = await withTimeout(
      promisifyWx("getBLEDeviceServices", { deviceId }),
      8000,
      "读取 Puppy BLE 服务超时，请重新扫描后再试"
    );
    const services = servicesResult.services || [];
    const service = services.find((item) => normalizeUuid(item.uuid) === normalizeUuid(PUPPY_BLE_SERVICE_UUID));
    if (!service) {
      throw new Error("没有找到 Puppy 配网服务，请确认固件已支持 BLE 配网协议");
    }

    this.setData({ statusText: "已找到配网服务，正在读取写入通道..." });
    this.appendProvisionLog("读取 BLE 特征值");
    const charsResult = await withTimeout(
      promisifyWx("getBLEDeviceCharacteristics", {
        deviceId,
        serviceId: service.uuid
      }),
      8000,
      "读取 Puppy BLE 通道超时，请重新扫描后再试"
    );
    const characteristics = charsResult.characteristics || [];
    const writeChar = characteristics.find((item) => normalizeUuid(item.uuid) === normalizeUuid(PUPPY_BLE_WIFI_WRITE_UUID));
    if (!writeChar || !(writeChar.properties && (writeChar.properties.write || writeChar.properties.writeNoResponse))) {
      throw new Error("没有找到 Puppy 配网写入通道，请确认固件 UUID 配置一致");
    }
    const notifyChar = characteristics.find((item) => normalizeUuid(item.uuid) === normalizeUuid(PUPPY_BLE_STATUS_NOTIFY_UUID));
    this.appendProvisionLog(`找到写入通道：${writeChar.properties.write ? "write" : "writeNoResponse"}`);
    return {
      deviceId,
      serviceId: service.uuid,
      characteristicId: writeChar.uuid,
      writeType: writeChar.properties.write ? "write" : "writeNoResponse",
      writeTypes: [
        writeChar.properties.write ? "write" : "",
        writeChar.properties.writeNoResponse ? "writeNoResponse" : ""
      ].filter((item) => item),
      notifyCharacteristicId: notifyChar && notifyChar.uuid ? notifyChar.uuid : ""
    };
  },

  async prepareProvisioningStatusWaiter(target) {
    if (!target || !target.notifyCharacteristicId || !wx.notifyBLECharacteristicValueChange) {
      return null;
    }

    // Firmware should send one JSON object per line and terminate it with "\n".
    // Example: {"status":"wifi_connected","deviceId":"e8:3d:c1:f5:49:b8"}\n
    this.appendProvisionLog("开启结果通知通道");
    let bufferText = "";
    const statusPromise = new Promise((resolve) => {
      const handleStatusText = (text) => {
        const parsed = parseProvisioningStatus(text);
        if (!parsed) {
          return false;
        }
        if (isProvisioningTerminalStatus(parsed)) {
          resolve(parsed);
        } else {
          this.handleProvisioningProgress(parsed);
        }
        return true;
      };

      const handler = (res) => {
        if (!res || res.deviceId !== target.deviceId || normalizeUuid(res.characteristicId) !== normalizeUuid(target.notifyCharacteristicId)) {
          return;
        }

        bufferText += arrayBufferToUtf8(res.value);
        if (bufferText.includes("\n")) {
          const parts = bufferText.split("\n");
          bufferText = parts.pop() || "";
          for (let i = 0; i < parts.length; i += 1) {
            if (handleStatusText(parts[i])) {
              return;
            }
          }
          return;
        }

        if (handleStatusText(bufferText)) {
          bufferText = "";
        }
      };

      wx.onBLECharacteristicValueChange(handler);
    });

    wx.notifyBLECharacteristicValueChange({
      deviceId: target.deviceId,
      serviceId: target.serviceId,
      characteristicId: target.notifyCharacteristicId,
      state: true,
      success: () => {
        this.appendProvisionLog("结果通知通道已开启");
      },
      fail: () => {
        this.appendProvisionLog("结果通知通道不可用，继续发送 Wi‑Fi");
      }
    });
    this.appendProvisionLog("结果通知通道请求已发出，继续发送 Wi‑Fi");
    return statusPromise;
  },

  handleProvisioningProgress(provisioningResult) {
    const status = getProvisioningStatus(provisioningResult);
    if (!status || !PROVISIONING_PENDING_STATUSES.has(status)) {
      this.appendProvisionLog(`收到设备状态：${status || "unknown"}`);
      return;
    }
    this.setData({ statusText: "Puppy 正在连接 Wi‑Fi，请稍等..." });
    this.appendProvisionLog(`设备状态：${status}`);
  },

  async resolveProvisioningResult(statusWaiter, timeoutMs = 25000) {
    if (!statusWaiter) {
      return null;
    }
    const timeout = new Promise((resolve) => {
      setTimeout(() => resolve(null), timeoutMs);
    });
    return Promise.race([statusWaiter, timeout]);
  },

  async completeInitializationFlow(provisioningResult) {
    const resultDeviceId = normalizeDeviceId(
      provisioningResult && (
        provisioningResult.deviceId
        || provisioningResult.device_id
        || provisioningResult.mac
        || provisioningResult.macAddress
      )
    );
    const fallbackDeviceId = normalizeDeviceId(this.data.deviceKey);
    const deviceId = resultDeviceId || fallbackDeviceId;
    if (!deviceId) {
      throw new Error("Wi‑Fi 已发送，但没有拿到设备ID。请让固件通过 notify 返回 {\"status\":\"wifi_connected\",\"deviceId\":\"...\"}\\n，或让 BLE 名称带 MAC。");
    }

    const status = getProvisioningStatus(provisioningResult);
    if (status && !PROVISIONING_SUCCESS_STATUSES.has(status)) {
      throw new Error(`Puppy 配网未成功：${status}`);
    }

    this.setData({ statusText: "正在获取微信账号..." });
    this.appendProvisionLog("获取微信账号 openid");
    const openid = await withTimeout(
      bindWechatAccount(),
      25000,
      "微信登录超时，请稍后重试"
    );
    this.appendProvisionLog("设备注册");
    const registerResult = await registerRobotDevice({
      openid,
      userId: openid,
      ownerOpenid: openid,
      deviceId,
      macAddress: deviceId,
      clientId: deviceId,
      firmwareVersion: "",
      model: "",
      board: ""
    });
    this.appendProvisionLog(`设备状态：${(registerResult && registerResult.status) || "REGISTERED"}`);
    this.setData({ statusText: "正在绑定设备..." });
    await bindRobotDevice({
      openid,
      deviceId,
      householdId: ""
    });
    this.appendProvisionLog("设备绑定完成");
    this.setData({ statusText: "正在认证设备..." });
    const authResult = await authenticateRobotDevice({
      openid,
      userId: openid,
      ownerOpenid: openid,
      deviceId,
      clientId: deviceId,
      firmwareVersion: ""
    });
    this.appendProvisionLog("设备认证完成");
    this.setData({ statusText: "正在创建家庭..." });
    const householdResult = await createHousehold({
      openid,
      userId: openid,
      ownerOpenid: openid,
      deviceId,
      householdName: "Puppy 家庭"
    });
    const householdId = householdResult && householdResult.householdId ? householdResult.householdId : "";
    this.appendProvisionLog(`家庭已创建：${householdId || "unknown"}`);
    this.setData({ statusText: "正在初始化 Profile..." });
    const initResult = await initializeRobotProfile({
      openid,
      userId: openid,
      ownerOpenid: openid,
      deviceId
    });
    this.appendProvisionLog(`Profile 状态：${(initResult && initResult.status) || "INITIALIZED"}`);
    updateWechatAccountProfile({
      openid,
      deviceId,
      deviceBound: true,
      householdId,
      initializationStatus: (initResult && initResult.status) || "INITIALIZED",
      deviceBoundAt: Date.now()
    });
    saveInitializationState({
      openid,
      deviceId,
      householdId,
      status: (initResult && initResult.status) || "INITIALIZED",
      step: "PROFILE"
    });
    try {
      this.appendProvisionLog("同步账号档案");
      await syncWechatProfileFromServer(openid);
    } catch (err) {
      // 绑定已完成；档案同步失败时下次进入“我的档案”会再同步。
    }
    return { deviceId, authResult };
  },

  async sendActivationCredentials(target, deviceId, authResult) {
    const credentials = extractDeviceAuthCredentials(authResult);
    if (!credentials.accessToken) {
      throw new Error("设备认证完成，但后端未返回 token，无法让 Puppy 上线。");
    }

    const payload = {
      type: "activation_credentials",
      version: 1,
      deviceId,
      accessToken: credentials.accessToken,
      token: credentials.accessToken,
      refreshToken: credentials.refreshToken,
      websocketUrl: credentials.websocketUrl,
      authUrl: credentials.authUrl,
      expireSeconds: credentials.expireSeconds,
      timestamp: Date.now()
    };
    this.setData({ statusText: "正在把设备凭证发送给 Puppy..." });
    this.appendProvisionLog("发送设备凭证");
    const statusWaiter = this.prepareProvisioningStatusWaiter(target);
    await this.writeProvisioningPayload(target, JSON.stringify(payload) + "\n", "设备凭证");
    const result = await this.resolveProvisioningResult(statusWaiter, 8000);
    const status = getProvisioningStatus(result);
    if (status && !PROVISIONING_SUCCESS_STATUSES.has(status)) {
      throw new Error(`Puppy 保存凭证失败：${status}`);
    }
    this.appendProvisionLog(status ? `设备凭证已保存：${status}` : "设备凭证已写入 BLE");
  },

  async writeProvisioningPayload(target, text, label = "Wi‑Fi 数据") {
    const buffer = utf8ToArrayBuffer(text);
    const totalChunks = Math.ceil(buffer.byteLength / BLE_WRITE_CHUNK_SIZE);
    this.appendProvisionLog(`准备写入 ${label}，共 ${totalChunks} 包，方式 ${(target.writeTypes || [target.writeType]).join("/")}`);
    for (let offset = 0; offset < buffer.byteLength; offset += BLE_WRITE_CHUNK_SIZE) {
      const chunk = sliceArrayBuffer(buffer, offset, Math.min(offset + BLE_WRITE_CHUNK_SIZE, buffer.byteLength));
      const chunkIndex = Math.floor(offset / BLE_WRITE_CHUNK_SIZE) + 1;
      this.setData({ statusText: `正在发送 ${label}... ${chunkIndex}/${totalChunks}` });
      if (chunkIndex === 1 || chunkIndex === totalChunks) {
        this.appendProvisionLog(`写入 ${label} ${chunkIndex}/${totalChunks}`);
      }
      await this.writeBleChunkWithFallback(target, chunk, chunkIndex);
      await sleep(35);
    }
  },

  async writeBleChunkWithFallback(target, chunk, chunkIndex) {
    const writeTypes = target.writeTypes && target.writeTypes.length
      ? target.writeTypes
      : [target.writeType || "write"];
    let lastError = null;
    for (let i = 0; i < writeTypes.length; i += 1) {
      const writeType = writeTypes[i];
      try {
        await withTimeout(
          promisifyWx("writeBLECharacteristicValue", {
            deviceId: target.deviceId,
            serviceId: target.serviceId,
            characteristicId: target.characteristicId,
            value: chunk,
            writeType
          }),
          5000,
          `写入第 ${chunkIndex} 包超时`
        );
        return;
      } catch (err) {
        lastError = err;
        this.appendProvisionLog(`第 ${chunkIndex} 包 ${writeType} 失败`);
      }
    }
    const message = lastError && lastError.message
      ? lastError.message
      : "写入 Wi‑Fi 配置信息失败";
    throw new Error(`${message}，请确认 Puppy 仍在配网模式`);
  },

  async stopDiscoveryOnly() {
    if (!wx.stopBluetoothDevicesDiscovery) {
      return;
    }
    try {
      await withTimeout(
        promisifyWx("stopBluetoothDevicesDiscovery"),
        3000,
        "停止蓝牙扫描超时"
      );
    } catch (err) {
      // 忽略停止扫描失败。
    }
  },

  async stopBluetooth() {
    await this.stopDiscoveryOnly();
    if (this.data.selectedDeviceId && wx.closeBLEConnection) {
      try {
        await promisifyWx("closeBLEConnection", { deviceId: this.data.selectedDeviceId });
      } catch (err) {
        // 忽略断开失败。
      }
    }
    if (wx.closeBluetoothAdapter) {
      try {
        await promisifyWx("closeBluetoothAdapter");
      } catch (err) {
        // 忽略关闭失败。
      }
    }
  },

  formatBluetoothError(err) {
    const message = err && err.errMsg ? err.errMsg : "";
    if (message.includes("not available")) {
      return "蓝牙不可用，请打开手机蓝牙后重试";
    }
    if (message.includes("auth deny")) {
      return "小程序没有蓝牙权限，请在系统设置里允许蓝牙权限";
    }
    return message || "蓝牙操作失败";
  },

  formatWifiListError(err) {
    const message = err && err.errMsg ? err.errMsg : "";
    if (message.includes("auth deny") || message.includes("authorize")) {
      return "没有位置权限，微信不能返回附近 Wi‑Fi。请直接手动输入 Wi‑Fi 名称，或在真机设置里打开小程序定位权限后重试。";
    }
    if (message.includes("not supported")) {
      return "当前环境不支持获取 Wi‑Fi 列表。微信开发者工具通常拿不到真实 Wi‑Fi，请直接手动输入 Wi‑Fi 名称。";
    }
    if (message.includes("wifi is disable") || message.includes("not available")) {
      return "手机 Wi‑Fi 未打开或不可用。请打开 Wi‑Fi 后重试，也可以直接手动输入 Wi‑Fi 名称。";
    }
    return "微信没有返回 Wi‑Fi 列表。请直接手动输入 Wi‑Fi 名称；真机需要打开定位、Wi‑Fi 和小程序定位权限。";
  }
});
