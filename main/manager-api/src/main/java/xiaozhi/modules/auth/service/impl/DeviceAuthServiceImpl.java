package xiaozhi.modules.auth.service.impl;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Service;

import lombok.AllArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import xiaozhi.common.constant.Constant;
import xiaozhi.common.redis.RedisUtils;
import xiaozhi.modules.auth.dto.DeviceAuthIntrospectionDTO;
import xiaozhi.modules.auth.dto.DeviceAuthRequestDTO;
import xiaozhi.modules.auth.dto.DeviceAuthResponseDTO;
import xiaozhi.modules.auth.dto.DeviceAuthTokenRequestDTO;
import xiaozhi.modules.auth.service.DeviceAuthService;
import xiaozhi.modules.sys.service.SysParamsService;

@Slf4j
@Service
@AllArgsConstructor
public class DeviceAuthServiceImpl implements DeviceAuthService {

    private static final int DEFAULT_TOKEN_EXPIRE_SECONDS = 60 * 60 * 24 * 30;
    private static final String REVOKED_TOKEN_KEY_PREFIX = "auth:device:revoked:";

    private final SysParamsService sysParamsService;
    private final RedisUtils redisUtils;

    @Override
    public DeviceAuthResponseDTO authenticateDevice(DeviceAuthRequestDTO request) throws Exception {
        String deviceId = StringUtils.trimToEmpty(request == null ? null : request.getDeviceId());
        if (StringUtils.isBlank(deviceId)) {
            throw new IllegalArgumentException("deviceId is required");
        }

        String clientId = StringUtils.trimToEmpty(request.getClientId());
        if (StringUtils.isBlank(clientId)) {
            clientId = deviceId;
        }

        boolean authEnabled = isAuthEnabled();
        String token = authEnabled ? generateWebSocketToken(clientId, deviceId) : "";

        DeviceAuthResponseDTO response = new DeviceAuthResponseDTO();
        response.setToken(token);
        response.setExpireSeconds(resolveTokenExpireSeconds());
        response.setWebsocketUrl(resolveWebsocketUrl());
        response.setAuthEnabled(authEnabled);
        return response;
    }

    @Override
    public DeviceAuthResponseDTO refreshDeviceToken(DeviceAuthTokenRequestDTO request) throws Exception {
        DeviceTokenValidation validation = validateDeviceToken(request);
        if (!validation.valid) {
            throw new IllegalArgumentException("Invalid token: " + validation.reason);
        }

        revokeToken(request.getToken(), validation.remainingSeconds);

        DeviceAuthRequestDTO authRequest = new DeviceAuthRequestDTO();
        authRequest.setDeviceId(validation.deviceId);
        authRequest.setClientId(validation.clientId);
        return authenticateDevice(authRequest);
    }

    @Override
    public void logoutDeviceToken(DeviceAuthTokenRequestDTO request) {
        revokeDeviceToken(request);
    }

    @Override
    public void revokeDeviceToken(DeviceAuthTokenRequestDTO request) {
        DeviceTokenValidation validation = validateDeviceTokenWithoutThrow(request);
        if (StringUtils.isNotBlank(request == null ? null : request.getToken())) {
            long ttl = validation.remainingSeconds > 0 ? validation.remainingSeconds : resolveTokenExpireSeconds();
            revokeToken(request.getToken(), ttl);
        }
    }

    @Override
    public DeviceAuthIntrospectionDTO introspectDeviceToken(DeviceAuthTokenRequestDTO request) throws Exception {
        DeviceTokenValidation validation = validateDeviceToken(request);
        DeviceAuthIntrospectionDTO result = new DeviceAuthIntrospectionDTO();
        result.setValid(validation.valid);
        result.setReason(validation.reason);
        result.setRemainingSeconds(validation.remainingSeconds);
        result.setAuthEnabled(isAuthEnabled());
        return result;
    }

    @Override
    public String generateWebSocketToken(String clientId, String deviceId) throws Exception {
        String secretKey = sysParamsService.getValue(Constant.SERVER_SECRET, false);
        if (StringUtils.isBlank(secretKey) || "null".equalsIgnoreCase(secretKey)) {
            throw new IllegalStateException("WebSocket认证密钥未配置(server.secret)");
        }

        long timestamp = System.currentTimeMillis() / 1000;
        String content = String.format("%s|%s|%d", clientId, deviceId, timestamp);

        Mac hmac = Mac.getInstance("HmacSHA256");
        SecretKeySpec keySpec = new SecretKeySpec(secretKey.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
        hmac.init(keySpec);
        byte[] signature = hmac.doFinal(content.getBytes(StandardCharsets.UTF_8));
        String signatureBase64 = Base64.getUrlEncoder().withoutPadding().encodeToString(signature);

        return String.format("%s.%d", signatureBase64, timestamp);
    }

    private DeviceTokenValidation validateDeviceTokenWithoutThrow(DeviceAuthTokenRequestDTO request) {
        try {
            return validateDeviceToken(request);
        } catch (Exception e) {
            DeviceTokenValidation validation = new DeviceTokenValidation();
            validation.valid = false;
            validation.reason = "invalid";
            return validation;
        }
    }

    private DeviceTokenValidation validateDeviceToken(DeviceAuthTokenRequestDTO request) throws Exception {
        DeviceTokenValidation validation = new DeviceTokenValidation();
        validation.authEnabled = isAuthEnabled();

        String deviceId = StringUtils.trimToEmpty(request == null ? null : request.getDeviceId());
        if (StringUtils.isBlank(deviceId)) {
            return validation.invalid("missing_device_id");
        }

        String clientId = StringUtils.trimToEmpty(request.getClientId());
        if (StringUtils.isBlank(clientId)) {
            clientId = deviceId;
        }

        validation.deviceId = deviceId;
        validation.clientId = clientId;

        if (!validation.authEnabled) {
            validation.valid = true;
            validation.remainingSeconds = resolveTokenExpireSeconds();
            return validation;
        }

        String token = StringUtils.trimToEmpty(request.getToken());
        if (StringUtils.isBlank(token)) {
            return validation.invalid("missing_token");
        }
        if (isTokenRevoked(token)) {
            return validation.invalid("revoked");
        }

        String[] tokenParts = token.split("\\.", 2);
        if (tokenParts.length != 2 || StringUtils.isBlank(tokenParts[0]) || StringUtils.isBlank(tokenParts[1])) {
            return validation.invalid("malformed_token");
        }

        long timestamp;
        try {
            timestamp = Long.parseLong(tokenParts[1]);
        } catch (NumberFormatException e) {
            return validation.invalid("malformed_timestamp");
        }

        long now = System.currentTimeMillis() / 1000;
        int expireSeconds = resolveTokenExpireSeconds();
        long remainingSeconds = timestamp + expireSeconds - now;
        if (remainingSeconds <= 0) {
            return validation.invalid("expired");
        }

        String expectedSignature = sign(String.format("%s|%s|%d", clientId, deviceId, timestamp));
        if (!MessageDigest.isEqual(
                tokenParts[0].getBytes(StandardCharsets.UTF_8),
                expectedSignature.getBytes(StandardCharsets.UTF_8))) {
            return validation.invalid("signature_mismatch");
        }

        validation.valid = true;
        validation.remainingSeconds = (int) Math.min(remainingSeconds, Integer.MAX_VALUE);
        return validation;
    }

    private boolean isAuthEnabled() {
        String authEnabledValue = sysParamsService.getValue(Constant.SERVER_AUTH_ENABLED, true);
        return "true".equalsIgnoreCase(authEnabledValue);
    }

    private String sign(String content) throws Exception {
        String secretKey = resolveSecretKey();

        Mac hmac = Mac.getInstance("HmacSHA256");
        SecretKeySpec keySpec = new SecretKeySpec(secretKey.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
        hmac.init(keySpec);
        byte[] signature = hmac.doFinal(content.getBytes(StandardCharsets.UTF_8));
        return Base64.getUrlEncoder().withoutPadding().encodeToString(signature);
    }

    private String resolveSecretKey() {
        String secretKey = sysParamsService.getValue(Constant.SERVER_SECRET, false);
        if (StringUtils.isBlank(secretKey) || "null".equalsIgnoreCase(secretKey)) {
            throw new IllegalStateException("WebSocket认证密钥未配置(server.secret)");
        }
        return secretKey;
    }

    private void revokeToken(String token, long ttlSeconds) {
        if (StringUtils.isBlank(token)) {
            return;
        }
        long ttl = ttlSeconds > 0 ? ttlSeconds : resolveTokenExpireSeconds();
        redisUtils.set(revokedTokenKey(token), "revoked", ttl);
    }

    private boolean isTokenRevoked(String token) {
        return redisUtils.get(revokedTokenKey(token)) != null;
    }

    private String revokedTokenKey(String token) {
        return REVOKED_TOKEN_KEY_PREFIX + sha256Hex(token);
    }

    private String sha256Hex(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        } catch (Exception e) {
            throw new IllegalStateException("Unable to hash token", e);
        }
    }

    private String resolveWebsocketUrl() {
        String websocketUrl = sysParamsService.getValue(Constant.SERVER_WEBSOCKET, true);
        if (StringUtils.isBlank(websocketUrl) || "null".equalsIgnoreCase(websocketUrl)) {
            return "";
        }
        return websocketUrl.split("\\;")[0];
    }

    private Integer resolveTokenExpireSeconds() {
        String configured = sysParamsService.getValue("server.auth.expire_seconds", true);
        if (StringUtils.isBlank(configured) || "null".equalsIgnoreCase(configured)) {
            return DEFAULT_TOKEN_EXPIRE_SECONDS;
        }
        try {
            int value = Integer.parseInt(configured.trim());
            return value > 0 ? value : DEFAULT_TOKEN_EXPIRE_SECONDS;
        } catch (NumberFormatException e) {
            log.warn("Invalid server.auth.expire_seconds: {}", configured);
            return DEFAULT_TOKEN_EXPIRE_SECONDS;
        }
    }

    private static class DeviceTokenValidation {
        private boolean valid;
        private boolean authEnabled;
        private String reason;
        private int remainingSeconds;
        private String deviceId;
        private String clientId;

        private DeviceTokenValidation invalid(String reason) {
            this.valid = false;
            this.reason = reason;
            this.remainingSeconds = 0;
            return this;
        }
    }
}
