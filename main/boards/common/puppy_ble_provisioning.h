#ifndef PUPPY_BLE_PROVISIONING_H
#define PUPPY_BLE_PROVISIONING_H

#include <esp_err.h>
#include <esp_gap_ble_api.h>
#include <esp_gatts_api.h>

#include <mutex>
#include <string>

class PuppyBleProvisioning {
public:
    static PuppyBleProvisioning& GetInstance();

    esp_err_t init();
    esp_err_t deinit();

    PuppyBleProvisioning(const PuppyBleProvisioning&) = delete;
    PuppyBleProvisioning& operator=(const PuppyBleProvisioning&) = delete;

private:
    PuppyBleProvisioning() = default;
    ~PuppyBleProvisioning() = default;

    enum class CharBeingAdded {
        None,
        Write,
        Notify,
    };

    static void GapCallback(esp_gap_ble_cb_event_t event, esp_ble_gap_cb_param_t* param);
    static void GattsCallback(esp_gatts_cb_event_t event, esp_gatt_if_t gatts_if,
                              esp_ble_gatts_cb_param_t* param);
    static void ConnectTask(void* arg);

    void HandleGapEvent(esp_gap_ble_cb_event_t event, esp_ble_gap_cb_param_t* param);
    void HandleGattsEvent(esp_gatts_cb_event_t event, esp_gatt_if_t gatts_if,
                          esp_ble_gatts_cb_param_t* param);
    void HandleWrite(esp_gatt_if_t gatts_if, esp_ble_gatts_cb_param_t* param);
    void ProcessLine(const std::string& line);
    void ConnectWifi(std::string ssid, std::string password, std::string server_url);
    void SendStatus(const std::string& status, const std::string& reason = "");
    void NotifyLine(const std::string& line);
    void StartAdvertising();
    void ResetGattState();
    std::string BuildDeviceName() const;

    std::mutex mutex_;
    bool initialized_ = false;
    bool advertising_ = false;
    bool connected_ = false;
    bool subscribed_ = false;
    bool provisioning_done_ = false;
    bool connect_task_running_ = false;
    esp_gatt_if_t gatts_if_ = ESP_GATT_IF_NONE;
    uint16_t app_id_ = 0x55;
    uint16_t conn_id_ = 0;
    uint16_t service_handle_ = 0;
    uint16_t write_char_handle_ = 0;
    uint16_t notify_char_handle_ = 0;
    uint16_t notify_ccc_handle_ = 0;
    CharBeingAdded char_being_added_ = CharBeingAdded::None;
    std::string rx_buffer_;
    std::string device_name_;
};

#endif
