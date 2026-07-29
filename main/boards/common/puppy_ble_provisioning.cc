#include "puppy_ble_provisioning.h"

#include "settings.h"
#include "system_info.h"

#include <cJSON.h>
#include <esp_bt.h>
#include <esp_bt_device.h>
#include <esp_bt_main.h>
#include <esp_gap_ble_api.h>
#include <esp_gatt_common_api.h>
#include <esp_log.h>

#include <algorithm>
#include <cstring>
#include <vector>

#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <ssid_manager.h>
#include <wifi_manager.h>

namespace {

constexpr const char* TAG = "PuppyBleProvisioning";
constexpr uint16_t kClientConfigUuid = ESP_GATT_UUID_CHAR_CLIENT_CONFIG;
constexpr uint16_t kNumHandles = 8;
constexpr uint16_t kAppId = 0x55;
constexpr size_t kMaxRxBuffer = 512;
constexpr size_t kNotifyChunkSize = 20;
constexpr TickType_t kWifiConnectTimeout = pdMS_TO_TICKS(20000);

// ESP-IDF expects 128-bit BLE UUIDs in little-endian byte order.
static const uint8_t kServiceUuid128[16] = {
    0x01, 0xA0, 0xF3, 0xD6, 0x92, 0x8F, 0x93, 0xA9,
    0x2F, 0x4E, 0x6A, 0x6B, 0xA0, 0xA7, 0x84, 0x8F,
};

static const uint8_t kWriteUuid128[16] = {
    0x01, 0xA0, 0xF3, 0xD6, 0x92, 0x8F, 0x93, 0xA9,
    0x2F, 0x4E, 0x6A, 0x6B, 0xA1, 0xA7, 0x84, 0x8F,
};

static const uint8_t kNotifyUuid128[16] = {
    0x01, 0xA0, 0xF3, 0xD6, 0x92, 0x8F, 0x93, 0xA9,
    0x2F, 0x4E, 0x6A, 0x6B, 0xA2, 0xA7, 0x84, 0x8F,
};

esp_bt_uuid_t MakeUuid128(const uint8_t uuid128[16]) {
    esp_bt_uuid_t uuid = {};
    uuid.len = ESP_UUID_LEN_128;
    memcpy(uuid.uuid.uuid128, uuid128, ESP_UUID_LEN_128);
    return uuid;
}

esp_bt_uuid_t MakeUuid16(uint16_t uuid16) {
    esp_bt_uuid_t uuid = {};
    uuid.len = ESP_UUID_LEN_16;
    uuid.uuid.uuid16 = uuid16;
    return uuid;
}

esp_ble_adv_data_t BuildAdvData() {
    esp_ble_adv_data_t adv_data = {};
    adv_data.set_scan_rsp = false;
    adv_data.include_name = true;
    adv_data.include_txpower = true;
    adv_data.min_interval = 0x20;
    adv_data.max_interval = 0x40;
    adv_data.appearance = 0x00;
    adv_data.manufacturer_len = 0;
    adv_data.p_manufacturer_data = nullptr;
    adv_data.service_data_len = 0;
    adv_data.p_service_data = nullptr;
    adv_data.service_uuid_len = ESP_UUID_LEN_128;
    adv_data.p_service_uuid = const_cast<uint8_t*>(kServiceUuid128);
    adv_data.flag = ESP_BLE_ADV_FLAG_GEN_DISC | ESP_BLE_ADV_FLAG_BREDR_NOT_SPT;
    return adv_data;
}

esp_ble_adv_params_t BuildAdvParams() {
    esp_ble_adv_params_t adv_params = {};
    adv_params.adv_int_min = 0x20;
    adv_params.adv_int_max = 0x40;
    adv_params.adv_type = ADV_TYPE_IND;
    adv_params.own_addr_type = BLE_ADDR_TYPE_PUBLIC;
    adv_params.channel_map = ADV_CHNL_ALL;
    adv_params.adv_filter_policy = ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY;
    return adv_params;
}

std::string JsonString(cJSON* root) {
    char* raw = cJSON_PrintUnformatted(root);
    if (!raw) {
        return "{}";
    }
    std::string result(raw);
    cJSON_free(raw);
    return result;
}

std::string GetString(cJSON* root, const char* key) {
    cJSON* item = cJSON_GetObjectItem(root, key);
    return cJSON_IsString(item) && item->valuestring ? item->valuestring : "";
}

bool IsWebsocketUrl(const std::string& url) {
    return url.rfind("ws://", 0) == 0 || url.rfind("wss://", 0) == 0;
}

struct ConnectArgs {
    PuppyBleProvisioning* self;
    std::string ssid;
    std::string password;
    std::string server_url;
};

}  // namespace

PuppyBleProvisioning& PuppyBleProvisioning::GetInstance() {
    static PuppyBleProvisioning instance;
    return instance;
}

esp_err_t PuppyBleProvisioning::init() {
    std::lock_guard<std::mutex> lock(mutex_);
    if (initialized_) {
        ESP_LOGW(TAG, "Already initialized");
        return ESP_OK;
    }

    ResetGattState();
    app_id_ = kAppId;
    device_name_ = BuildDeviceName();

    esp_err_t ret = esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);
    if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
        ESP_LOGW(TAG, "Classic BT memory release skipped: %s", esp_err_to_name(ret));
    }

    if (esp_bt_controller_get_status() == ESP_BT_CONTROLLER_STATUS_IDLE) {
        esp_bt_controller_config_t bt_cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
        ret = esp_bt_controller_init(&bt_cfg);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "BT controller init failed: %s", esp_err_to_name(ret));
            return ret;
        }
    }

    if (esp_bt_controller_get_status() == ESP_BT_CONTROLLER_STATUS_INITED) {
        ret = esp_bt_controller_enable(ESP_BT_MODE_BLE);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "BT controller enable failed: %s", esp_err_to_name(ret));
            return ret;
        }
    }

    if (esp_bluedroid_get_status() == ESP_BLUEDROID_STATUS_UNINITIALIZED) {
        ret = esp_bluedroid_init();
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Bluedroid init failed: %s", esp_err_to_name(ret));
            return ret;
        }
    }

    if (esp_bluedroid_get_status() == ESP_BLUEDROID_STATUS_INITIALIZED) {
        ret = esp_bluedroid_enable();
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Bluedroid enable failed: %s", esp_err_to_name(ret));
            return ret;
        }
    }

    initialized_ = true;

    ret = esp_ble_gap_register_callback(GapCallback);
    if (ret != ESP_OK) {
        initialized_ = false;
        ESP_LOGE(TAG, "GAP callback register failed: %s", esp_err_to_name(ret));
        return ret;
    }

    ret = esp_ble_gatts_register_callback(GattsCallback);
    if (ret != ESP_OK) {
        initialized_ = false;
        ESP_LOGE(TAG, "GATTS callback register failed: %s", esp_err_to_name(ret));
        return ret;
    }

    ret = esp_ble_gatts_app_register(app_id_);
    if (ret != ESP_OK) {
        initialized_ = false;
        ESP_LOGE(TAG, "GATTS app register failed: %s", esp_err_to_name(ret));
        return ret;
    }

    ESP_LOGI(TAG, "Puppy BLE provisioning started as %s", device_name_.c_str());
    return ESP_OK;
}

esp_err_t PuppyBleProvisioning::deinit() {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!initialized_) {
        return ESP_OK;
    }

    if (advertising_) {
        esp_ble_gap_stop_advertising();
        advertising_ = false;
    }
    if (connected_ && gatts_if_ != ESP_GATT_IF_NONE) {
        esp_ble_gatts_close(gatts_if_, conn_id_);
    }
    if (gatts_if_ != ESP_GATT_IF_NONE) {
        esp_ble_gatts_app_unregister(gatts_if_);
    }

    esp_err_t ret = ESP_OK;
    if (esp_bluedroid_get_status() == ESP_BLUEDROID_STATUS_ENABLED) {
        ret = esp_bluedroid_disable();
        if (ret != ESP_OK) {
            ESP_LOGW(TAG, "Bluedroid disable failed: %s", esp_err_to_name(ret));
        }
    }
    if (esp_bluedroid_get_status() == ESP_BLUEDROID_STATUS_INITIALIZED) {
        ret = esp_bluedroid_deinit();
        if (ret != ESP_OK) {
            ESP_LOGW(TAG, "Bluedroid deinit failed: %s", esp_err_to_name(ret));
        }
    }
    if (esp_bt_controller_get_status() == ESP_BT_CONTROLLER_STATUS_ENABLED) {
        ret = esp_bt_controller_disable();
        if (ret != ESP_OK) {
            ESP_LOGW(TAG, "BT controller disable failed: %s", esp_err_to_name(ret));
        }
    }
    if (esp_bt_controller_get_status() == ESP_BT_CONTROLLER_STATUS_INITED) {
        ret = esp_bt_controller_deinit();
        if (ret != ESP_OK) {
            ESP_LOGW(TAG, "BT controller deinit failed: %s", esp_err_to_name(ret));
        }
    }

    initialized_ = false;
    ResetGattState();
    ESP_LOGI(TAG, "Puppy BLE provisioning stopped");
    return ESP_OK;
}

void PuppyBleProvisioning::GapCallback(esp_gap_ble_cb_event_t event, esp_ble_gap_cb_param_t* param) {
    GetInstance().HandleGapEvent(event, param);
}

void PuppyBleProvisioning::GattsCallback(esp_gatts_cb_event_t event, esp_gatt_if_t gatts_if,
                                         esp_ble_gatts_cb_param_t* param) {
    GetInstance().HandleGattsEvent(event, gatts_if, param);
}

void PuppyBleProvisioning::HandleGapEvent(esp_gap_ble_cb_event_t event,
                                          esp_ble_gap_cb_param_t* param) {
    switch (event) {
        case ESP_GAP_BLE_ADV_DATA_SET_COMPLETE_EVT:
            StartAdvertising();
            break;
        case ESP_GAP_BLE_ADV_START_COMPLETE_EVT:
            if (param->adv_start_cmpl.status == ESP_BT_STATUS_SUCCESS) {
                std::lock_guard<std::mutex> lock(mutex_);
                advertising_ = true;
                ESP_LOGI(TAG, "Advertising started");
            } else {
                ESP_LOGE(TAG, "Advertising start failed: %d", param->adv_start_cmpl.status);
            }
            break;
        case ESP_GAP_BLE_ADV_STOP_COMPLETE_EVT:
            ESP_LOGI(TAG, "Advertising stopped");
            break;
        default:
            break;
    }
}

void PuppyBleProvisioning::HandleGattsEvent(esp_gatts_cb_event_t event, esp_gatt_if_t gatts_if,
                                            esp_ble_gatts_cb_param_t* param) {
    switch (event) {
        case ESP_GATTS_REG_EVT: {
            if (param->reg.status != ESP_GATT_OK) {
                ESP_LOGE(TAG, "GATTS register failed: %d", param->reg.status);
                return;
            }
            {
                std::lock_guard<std::mutex> lock(mutex_);
                gatts_if_ = gatts_if;
            }
            esp_ble_gap_set_device_name(device_name_.c_str());
            esp_ble_adv_data_t adv_data = BuildAdvData();
            esp_ble_gap_config_adv_data(&adv_data);

            esp_gatt_srvc_id_t service_id = {};
            service_id.is_primary = true;
            service_id.id.inst_id = 0;
            service_id.id.uuid = MakeUuid128(kServiceUuid128);
            esp_ble_gatts_create_service(gatts_if, &service_id, kNumHandles);
            break;
        }
        case ESP_GATTS_CREATE_EVT: {
            if (param->create.status != ESP_GATT_OK) {
                ESP_LOGE(TAG, "Service create failed: %d", param->create.status);
                return;
            }
            {
                std::lock_guard<std::mutex> lock(mutex_);
                service_handle_ = param->create.service_handle;
                char_being_added_ = CharBeingAdded::Write;
            }
            esp_ble_gatts_start_service(param->create.service_handle);

            esp_bt_uuid_t write_uuid = MakeUuid128(kWriteUuid128);
            esp_ble_gatts_add_char(param->create.service_handle, &write_uuid, ESP_GATT_PERM_WRITE,
                                   ESP_GATT_CHAR_PROP_BIT_WRITE | ESP_GATT_CHAR_PROP_BIT_WRITE_NR,
                                   nullptr, nullptr);
            break;
        }
        case ESP_GATTS_ADD_CHAR_EVT: {
            if (param->add_char.status != ESP_GATT_OK) {
                ESP_LOGE(TAG, "Characteristic add failed: %d", param->add_char.status);
                return;
            }

            CharBeingAdded current = CharBeingAdded::None;
            {
                std::lock_guard<std::mutex> lock(mutex_);
                current = char_being_added_;
                if (current == CharBeingAdded::Write) {
                    write_char_handle_ = param->add_char.attr_handle;
                    char_being_added_ = CharBeingAdded::Notify;
                } else if (current == CharBeingAdded::Notify) {
                    notify_char_handle_ = param->add_char.attr_handle;
                    char_being_added_ = CharBeingAdded::None;
                }
            }

            if (current == CharBeingAdded::Write) {
                esp_bt_uuid_t notify_uuid = MakeUuid128(kNotifyUuid128);
                esp_ble_gatts_add_char(service_handle_, &notify_uuid, ESP_GATT_PERM_READ,
                                       ESP_GATT_CHAR_PROP_BIT_READ | ESP_GATT_CHAR_PROP_BIT_NOTIFY,
                                       nullptr, nullptr);
            } else if (current == CharBeingAdded::Notify) {
                esp_bt_uuid_t descr_uuid = MakeUuid16(kClientConfigUuid);
                esp_ble_gatts_add_char_descr(service_handle_, &descr_uuid,
                                             ESP_GATT_PERM_READ | ESP_GATT_PERM_WRITE,
                                             nullptr, nullptr);
            }
            break;
        }
        case ESP_GATTS_ADD_CHAR_DESCR_EVT:
            if (param->add_char_descr.status == ESP_GATT_OK) {
                std::lock_guard<std::mutex> lock(mutex_);
                notify_ccc_handle_ = param->add_char_descr.attr_handle;
                ESP_LOGI(TAG, "Puppy BLE service ready");
            } else {
                ESP_LOGE(TAG, "Descriptor add failed: %d", param->add_char_descr.status);
            }
            break;
        case ESP_GATTS_CONNECT_EVT:
            {
                std::lock_guard<std::mutex> lock(mutex_);
                connected_ = true;
                advertising_ = false;
                gatts_if_ = gatts_if;
                conn_id_ = param->connect.conn_id;
            }
            ESP_LOGI(TAG, "Mini-program connected");
            break;
        case ESP_GATTS_DISCONNECT_EVT:
            {
                bool should_advertise = false;
                {
                    std::lock_guard<std::mutex> lock(mutex_);
                    connected_ = false;
                    subscribed_ = false;
                    should_advertise = !provisioning_done_;
                }
                ESP_LOGI(TAG, "Mini-program disconnected");
                if (should_advertise) {
                    StartAdvertising();
                }
            }
            break;
        case ESP_GATTS_WRITE_EVT:
            HandleWrite(gatts_if, param);
            break;
        default:
            break;
    }
}

void PuppyBleProvisioning::HandleWrite(esp_gatt_if_t gatts_if,
                                       esp_ble_gatts_cb_param_t* param) {
    auto& write = param->write;
    if (write.need_rsp) {
        esp_ble_gatts_send_response(gatts_if, write.conn_id, write.trans_id, ESP_GATT_OK, nullptr);
    }
    if (write.is_prep || write.len == 0 || write.value == nullptr) {
        return;
    }

    uint16_t write_char_handle = 0;
    uint16_t notify_ccc_handle = 0;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        write_char_handle = write_char_handle_;
        notify_ccc_handle = notify_ccc_handle_;
    }

    if (write.handle == notify_ccc_handle && write.len >= 2) {
        const uint16_t ccc = write.value[0] | (write.value[1] << 8);
        std::lock_guard<std::mutex> lock(mutex_);
        subscribed_ = (ccc & 0x0001) != 0;
        ESP_LOGI(TAG, "Notify subscription %s", subscribed_ ? "enabled" : "disabled");
        return;
    }

    if (write.handle != write_char_handle) {
        return;
    }

    std::vector<std::string> lines;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        rx_buffer_.append(reinterpret_cast<const char*>(write.value), write.len);
        if (rx_buffer_.size() > kMaxRxBuffer) {
            ESP_LOGW(TAG, "Provisioning payload too large, clearing buffer");
            rx_buffer_.clear();
            lines.emplace_back("");
        }

        size_t pos = std::string::npos;
        while ((pos = rx_buffer_.find('\n')) != std::string::npos) {
            lines.emplace_back(rx_buffer_.substr(0, pos));
            rx_buffer_.erase(0, pos + 1);
        }

        if (!rx_buffer_.empty() && rx_buffer_.front() == '{' && rx_buffer_.back() == '}') {
            lines.emplace_back(rx_buffer_);
            rx_buffer_.clear();
        }
    }

    for (const auto& line : lines) {
        ProcessLine(line);
    }
}

void PuppyBleProvisioning::ProcessLine(const std::string& line) {
    if (line.empty()) {
        SendStatus("error", "payload_too_large");
        return;
    }

    cJSON* root = cJSON_Parse(line.c_str());
    if (!cJSON_IsObject(root)) {
        cJSON_Delete(root);
        SendStatus("error", "invalid_json");
        return;
    }

    std::string ssid = GetString(root, "ssid");
    std::string password = GetString(root, "password");
    std::string server_url = GetString(root, "serverUrl");
    if (server_url.empty()) {
        server_url = GetString(root, "server_url");
    }
    cJSON_Delete(root);

    if (ssid.empty()) {
        SendStatus("error", "missing_ssid");
        return;
    }

    SendStatus("wifi_connecting");
    ConnectWifi(std::move(ssid), std::move(password), std::move(server_url));
}

void PuppyBleProvisioning::ConnectWifi(std::string ssid, std::string password,
                                       std::string server_url) {
    bool already_running = false;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (connect_task_running_) {
            already_running = true;
        } else {
            connect_task_running_ = true;
        }
    }
    if (already_running) {
        SendStatus("error", "wifi_connecting");
        return;
    }

    auto* args = new ConnectArgs{this, std::move(ssid), std::move(password), std::move(server_url)};
    BaseType_t ok = xTaskCreate(ConnectTask, "puppy_ble_wifi", 6144, args, 3, nullptr);
    if (ok != pdPASS) {
        delete args;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            connect_task_running_ = false;
        }
        SendStatus("error", "task_create_failed");
    }
}

void PuppyBleProvisioning::ConnectTask(void* arg) {
    auto* args = static_cast<ConnectArgs*>(arg);
    auto* self = args->self;
    std::string ssid = std::move(args->ssid);
    std::string password = std::move(args->password);
    std::string server_url = std::move(args->server_url);
    delete args;

    ESP_LOGI(TAG, "Connecting to WiFi SSID: %s", ssid.c_str());
    SsidManager::GetInstance().AddSsid(ssid, password);

    if (IsWebsocketUrl(server_url)) {
        Settings settings("websocket", true);
        settings.SetString("url", server_url);
        ESP_LOGI(TAG, "Updated websocket url from provisioning");
    } else if (!server_url.empty()) {
        ESP_LOGI(TAG, "Ignoring non-websocket serverUrl from provisioning: %s",
                 server_url.c_str());
    }

    auto& wifi_manager = WifiManager::GetInstance();
    wifi_manager.StopStation();
    wifi_manager.StartStation();

    TickType_t start = xTaskGetTickCount();
    while (xTaskGetTickCount() - start < kWifiConnectTimeout) {
        if (wifi_manager.IsConnected()) {
            {
                std::lock_guard<std::mutex> lock(self->mutex_);
                self->provisioning_done_ = true;
                self->connect_task_running_ = false;
            }
            self->SendStatus("wifi_connected");
            vTaskDelay(pdMS_TO_TICKS(1500));
            self->deinit();
            vTaskDelete(nullptr);
        }
        vTaskDelay(pdMS_TO_TICKS(300));
    }

    {
        std::lock_guard<std::mutex> lock(self->mutex_);
        self->connect_task_running_ = false;
    }
    wifi_manager.StopStation();
    self->SendStatus("error", "wifi_connect_timeout");
    vTaskDelete(nullptr);
}

void PuppyBleProvisioning::SendStatus(const std::string& status, const std::string& reason) {
    cJSON* root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "status", status.c_str());
    cJSON_AddStringToObject(root, "deviceId", SystemInfo::GetMacAddress().c_str());
    if (!reason.empty()) {
        cJSON_AddStringToObject(root, "reason", reason.c_str());
    }
    std::string line = JsonString(root) + "\n";
    cJSON_Delete(root);
    NotifyLine(line);
}

void PuppyBleProvisioning::NotifyLine(const std::string& line) {
    esp_gatt_if_t gatts_if = ESP_GATT_IF_NONE;
    uint16_t conn_id = 0;
    uint16_t notify_char_handle = 0;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!connected_ || !subscribed_) {
            ESP_LOGW(TAG, "BLE status not sent, connected=%d subscribed=%d: %s",
                     connected_, subscribed_, line.c_str());
            return;
        }
        gatts_if = gatts_if_;
        conn_id = conn_id_;
        notify_char_handle = notify_char_handle_;
    }

    for (size_t offset = 0; offset < line.size(); offset += kNotifyChunkSize) {
        size_t chunk = std::min(kNotifyChunkSize, line.size() - offset);
        esp_err_t ret = esp_ble_gatts_send_indicate(
            gatts_if, conn_id, notify_char_handle, chunk,
            reinterpret_cast<uint8_t*>(const_cast<char*>(line.data() + offset)), false);
        if (ret != ESP_OK) {
            ESP_LOGW(TAG, "Notify failed: %s", esp_err_to_name(ret));
            return;
        }
        vTaskDelay(pdMS_TO_TICKS(30));
    }
    ESP_LOGI(TAG, "BLE status sent: %s", line.c_str());
}

void PuppyBleProvisioning::StartAdvertising() {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!initialized_ || advertising_ || connected_) {
        return;
    }
    esp_ble_adv_params_t adv_params = BuildAdvParams();
    esp_err_t ret = esp_ble_gap_start_advertising(&adv_params);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Start advertising failed: %s", esp_err_to_name(ret));
    }
}

void PuppyBleProvisioning::ResetGattState() {
    advertising_ = false;
    connected_ = false;
    subscribed_ = false;
    provisioning_done_ = false;
    connect_task_running_ = false;
    gatts_if_ = ESP_GATT_IF_NONE;
    conn_id_ = 0;
    service_handle_ = 0;
    write_char_handle_ = 0;
    notify_char_handle_ = 0;
    notify_ccc_handle_ = 0;
    char_being_added_ = CharBeingAdded::None;
    rx_buffer_.clear();
}

std::string PuppyBleProvisioning::BuildDeviceName() const {
    std::string mac = SystemInfo::GetMacAddress();
    mac.erase(std::remove(mac.begin(), mac.end(), ':'), mac.end());
    if (mac.size() >= 6) {
        return "Puppy-" + mac.substr(mac.size() - 6);
    }
    return "Puppy";
}
