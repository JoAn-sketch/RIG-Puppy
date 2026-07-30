#ifndef DEVICE_AUTH_H
#define DEVICE_AUTH_H

#include <string>

class DeviceAuth {
public:
    bool EnsureWebsocketCredentials();
    bool RefreshWebsocketCredentials();

private:
    std::string BuildAuthUrl(const std::string& endpoint);
    std::string BuildRequestPayload(const std::string& token = "");
    bool AuthenticateDevice();
    bool RefreshDeviceToken(const std::string& token);
    bool RequestAndStoreCredentials(const std::string& url, const std::string& payload);
    bool TokenNeedsRefresh(const std::string& token, int expire_seconds) const;
    long long ExtractTokenTimestamp(const std::string& token) const;
    void StoreCredentials(const std::string& token, int expire_seconds, const std::string& websocket_url);
};

#endif  // DEVICE_AUTH_H
