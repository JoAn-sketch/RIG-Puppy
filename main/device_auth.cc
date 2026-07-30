#include "device_auth.h"

#include "board.h"
#include "settings.h"
#include "system_info.h"

#include <cJSON.h>
#include <esp_ota_ops.h>
#include <esp_log.h>

#include <ctime>

#define TAG "DeviceAuth"

namespace {
constexpr int kDefaultTokenExpireSeconds = 60 * 60 * 24 * 30;
constexpr int kRefreshBeforeExpireSeconds = 60 * 60 * 24 * 3;

std::string GetConfiguredOtaUrl() {
    Settings settings("wifi", false);
    auto url = settings.GetString("ota_url");
    if (url.empty()) {
        url = CONFIG_OTA_URL;
    }
    return url;
}

std::string RemoveTrailingSlash(std::string value) {
    while (!value.empty() && value.back() == '/') {
        value.pop_back();
    }
    return value;
}

std::string ReplaceOtaWithAuth(std::string url) {
    url = RemoveTrailingSlash(url);
    const std::string ota_suffix = "/ota";
    if (url.size() >= ota_suffix.size() &&
        url.compare(url.size() - ota_suffix.size(), ota_suffix.size(), ota_suffix) == 0) {
        return url.substr(0, url.size() - ota_suffix.size()) + "/auth";
    }
    return url + "/auth";
}

std::string JsonString(cJSON* root) {
    auto raw = cJSON_PrintUnformatted(root);
    std::string result(raw ? raw : "");
    cJSON_free(raw);
    return result;
}
}  // namespace

bool DeviceAuth::EnsureWebsocketCredentials() {
    Settings settings("websocket", false);
    auto token = settings.GetString("token");
    int expire_seconds = settings.GetInt("expire_seconds", kDefaultTokenExpireSeconds);

    if (!token.empty() && !TokenNeedsRefresh(token, expire_seconds)) {
        ESP_LOGI(TAG, "Existing websocket token is still usable");
        return true;
    }

    if (!token.empty()) {
        ESP_LOGI(TAG, "Refreshing websocket token");
        if (RefreshDeviceToken(token)) {
            return true;
        }
        ESP_LOGW(TAG, "Refresh failed, requesting a new device token");
    }

    return AuthenticateDevice();
}

bool DeviceAuth::RefreshWebsocketCredentials() {
    Settings settings("websocket", false);
    auto token = settings.GetString("token");

    if (!token.empty()) {
        ESP_LOGI(TAG, "Forcing websocket token refresh");
        if (RefreshDeviceToken(token)) {
            return true;
        }
        ESP_LOGW(TAG, "Forced refresh failed, requesting a new device token");
    }

    return AuthenticateDevice();
}

std::string DeviceAuth::BuildAuthUrl(const std::string& endpoint) {
    Settings settings("auth", false);
    auto base_url = settings.GetString("url");
    if (base_url.empty()) {
        base_url = CONFIG_AUTH_URL;
    }
    if (base_url.empty()) {
        base_url = ReplaceOtaWithAuth(GetConfiguredOtaUrl());
    }
    return RemoveTrailingSlash(base_url) + "/" + endpoint;
}

std::string DeviceAuth::BuildRequestPayload(const std::string& token) {
    auto& board = Board::GetInstance();
    auto app_desc = esp_app_get_description();

    cJSON* root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "deviceId", SystemInfo::GetMacAddress().c_str());
    cJSON_AddStringToObject(root, "clientId", board.GetUuid().c_str());
    cJSON_AddStringToObject(root, "firmwareVersion", app_desc->version);
    if (!token.empty()) {
        cJSON_AddStringToObject(root, "token", token.c_str());
    }

    auto payload = JsonString(root);
    cJSON_Delete(root);
    return payload;
}

bool DeviceAuth::AuthenticateDevice() {
    return RequestAndStoreCredentials(BuildAuthUrl("device"), BuildRequestPayload());
}

bool DeviceAuth::RefreshDeviceToken(const std::string& token) {
    return RequestAndStoreCredentials(BuildAuthUrl("refresh"), BuildRequestPayload(token));
}

bool DeviceAuth::RequestAndStoreCredentials(const std::string& url, const std::string& payload) {
    auto network = Board::GetInstance().GetNetwork();
    auto http = network->CreateHttp(0);
    http->SetHeader("Content-Type", "application/json");
    http->SetHeader("Device-Id", SystemInfo::GetMacAddress().c_str());
    http->SetHeader("Client-Id", Board::GetInstance().GetUuid());
    http->SetContent(std::string(payload));

    ESP_LOGI(TAG, "Requesting auth credentials: %s", url.c_str());
    if (!http->Open("POST", url)) {
        ESP_LOGE(TAG, "Failed to open auth HTTP connection, code=0x%x", http->GetLastError());
        return false;
    }

    int status_code = http->GetStatusCode();
    auto body = http->ReadAll();
    http->Close();
    if (status_code != 200) {
        ESP_LOGE(TAG, "Auth request failed, status=%d, body=%s", status_code, body.c_str());
        return false;
    }

    cJSON* root = cJSON_Parse(body.c_str());
    if (root == nullptr) {
        ESP_LOGE(TAG, "Failed to parse auth response");
        return false;
    }

    cJSON* data = cJSON_GetObjectItem(root, "data");
    if (!cJSON_IsObject(data)) {
        data = root;
    }

    cJSON* token = cJSON_GetObjectItem(data, "token");
    cJSON* expire_seconds = cJSON_GetObjectItem(data, "expireSeconds");
    cJSON* websocket_url = cJSON_GetObjectItem(data, "websocketUrl");
    cJSON* auth_enabled = cJSON_GetObjectItem(data, "authEnabled");

    bool auth_enabled_value = !cJSON_IsBool(auth_enabled) || cJSON_IsTrue(auth_enabled);
    std::string token_value;
    if (cJSON_IsString(token)) {
        token_value = token->valuestring;
    }
    if (auth_enabled_value && token_value.empty()) {
        ESP_LOGE(TAG, "Auth response missing token");
        cJSON_Delete(root);
        return false;
    }

    int expire_value = cJSON_IsNumber(expire_seconds) ? expire_seconds->valueint : kDefaultTokenExpireSeconds;
    std::string websocket_url_value;
    if (cJSON_IsString(websocket_url)) {
        websocket_url_value = websocket_url->valuestring;
    }

    StoreCredentials(token_value, expire_value, websocket_url_value);
    cJSON_Delete(root);
    return true;
}

bool DeviceAuth::TokenNeedsRefresh(const std::string& token, int expire_seconds) const {
    long long issued_at = ExtractTokenTimestamp(token);
    if (issued_at <= 0 || expire_seconds <= 0) {
        return true;
    }

    time_t now = time(nullptr);
    if (now < 1700000000) {
        return true;
    }

    long long remaining = issued_at + expire_seconds - static_cast<long long>(now);
    return remaining <= kRefreshBeforeExpireSeconds;
}

long long DeviceAuth::ExtractTokenTimestamp(const std::string& token) const {
    auto dot = token.rfind('.');
    if (dot == std::string::npos || dot + 1 >= token.size()) {
        return 0;
    }

    try {
        return std::stoll(token.substr(dot + 1));
    } catch (...) {
        return 0;
    }
}

void DeviceAuth::StoreCredentials(const std::string& token, int expire_seconds, const std::string& websocket_url) {
    Settings settings("websocket", true);
    settings.SetString("token", token);
    settings.SetInt("expire_seconds", expire_seconds > 0 ? expire_seconds : kDefaultTokenExpireSeconds);
    settings.SetInt("token_issued_at", static_cast<int32_t>(ExtractTokenTimestamp(token)));
    if (!websocket_url.empty()) {
        settings.SetString("url", websocket_url);
    }
    ESP_LOGI(TAG, "Stored websocket credentials, auth=%s, expire=%d", token.empty() ? "off" : "on",
             expire_seconds);
}
