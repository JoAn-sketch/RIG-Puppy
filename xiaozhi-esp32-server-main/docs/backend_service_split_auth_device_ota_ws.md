# Backend Service Split: Auth, Device, OTA, WebSocket

## Goal

Split the current device startup backend responsibilities into independent capability modules:

- Auth Service: issue and validate device connection credentials.
- Device Service: own persistent device registration, activation, ownership and metadata.
- OTA Service: own firmware version checks, firmware URL generation and rollout policy.
- WebSocket Gateway: own realtime connection handshake, token verification, session lifecycle and message routing.

The OTA endpoint no longer returns WebSocket credentials. Devices must call the standalone auth endpoint before opening a realtime connection.

## Current Coupling

Current startup flow:

```text
Device
  -> POST /ota/
  -> check activation
  -> check firmware
  -> generate WebSocket token
  -> connect WebSocket
```

The coupling problem is that OTA currently performs authentication work.

## Target Flow

```text
Boot
  -> WiFi
  -> Load token from NVS
  -> If token missing/expired, POST /auth/device
  -> Connect WebSocket
  -> Run OTA check in background
```

## Implemented

Added:

```text
POST /auth/device
```

Request:

```json
{
  "deviceId": "28:84:85:44:8D:E0",
  "clientId": "28:84:85:44:8D:E0",
  "firmwareVersion": "2.2.6"
}
```

Response:

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "token": "signature.timestamp",
    "expireSeconds": 2592000,
    "websocketUrl": "ws://122.51.155.114:8000/xiaozhi/v1/",
    "authEnabled": true
  }
}
```

The HMAC algorithm is unchanged:

```text
content = clientId + "|" + deviceId + "|" + timestamp
signature = HMAC_SHA256(content, server.secret)
token = base64url(signature).withoutPadding + "." + timestamp
```

## OTA Rule

`/ota/` owns firmware update checks only. It must not return WebSocket URL, WebSocket token, MQTT credentials, or any other realtime connection credentials.

## Migration Plan

Phase 1:

- Update firmware boot flow to use cached NVS token first.
- If missing or near expiration, call `/auth/device`.
- Move OTA check after WebSocket connection or run it in background.

Phase 2:

- Keep OTA only for firmware lifecycle data.

Phase 3:

- Add `/auth/refresh`, `/auth/revoke`, and token rotation policy if needed.

## Dependency Rules

Allowed:

```text
Device -> Auth
Device -> OTA
Device -> WebSocket
```

Forbidden:

```text
OTA -> Auth business logic
Auth -> OTA business logic
```

## Notes

- `openid` remains a WeChat user identifier and must not be used as device `clientId`.
- `Device-Id` remains the stable hardware identity, normally MAC.
- `Client-Id` remains the connection/client identity. If omitted, current server behavior defaults it to `Device-Id`.
