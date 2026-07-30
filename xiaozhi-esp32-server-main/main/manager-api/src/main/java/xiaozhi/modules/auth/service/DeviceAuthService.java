package xiaozhi.modules.auth.service;

import xiaozhi.modules.auth.dto.DeviceAuthIntrospectionDTO;
import xiaozhi.modules.auth.dto.DeviceAuthRequestDTO;
import xiaozhi.modules.auth.dto.DeviceAuthResponseDTO;
import xiaozhi.modules.auth.dto.DeviceAuthTokenRequestDTO;

public interface DeviceAuthService {

    DeviceAuthResponseDTO authenticateDevice(DeviceAuthRequestDTO request) throws Exception;

    DeviceAuthResponseDTO refreshDeviceToken(DeviceAuthTokenRequestDTO request) throws Exception;

    void logoutDeviceToken(DeviceAuthTokenRequestDTO request);

    void revokeDeviceToken(DeviceAuthTokenRequestDTO request);

    DeviceAuthIntrospectionDTO introspectDeviceToken(DeviceAuthTokenRequestDTO request) throws Exception;

    String generateWebSocketToken(String clientId, String deviceId) throws Exception;
}
