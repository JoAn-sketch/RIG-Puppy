package xiaozhi.modules.auth.controller;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.AllArgsConstructor;
import xiaozhi.common.utils.Result;
import xiaozhi.modules.auth.dto.DeviceAuthIntrospectionDTO;
import xiaozhi.modules.auth.dto.DeviceAuthRequestDTO;
import xiaozhi.modules.auth.dto.DeviceAuthResponseDTO;
import xiaozhi.modules.auth.dto.DeviceAuthTokenRequestDTO;
import xiaozhi.modules.auth.service.DeviceAuthService;

@RestController
@AllArgsConstructor
@RequestMapping("/auth")
@Tag(name = "设备认证")
public class AuthController {

    private final DeviceAuthService deviceAuthService;

    @PostMapping("/device")
    @Operation(summary = "设备获取 WebSocket 认证凭证")
    public Result<DeviceAuthResponseDTO> authDevice(@RequestBody DeviceAuthRequestDTO request) throws Exception {
        return new Result<DeviceAuthResponseDTO>().ok(deviceAuthService.authenticateDevice(request));
    }

    @PostMapping("/refresh")
    @Operation(summary = "刷新设备 WebSocket 认证凭证")
    public Result<DeviceAuthResponseDTO> refresh(@RequestBody DeviceAuthTokenRequestDTO request) throws Exception {
        return new Result<DeviceAuthResponseDTO>().ok(deviceAuthService.refreshDeviceToken(request));
    }

    @PostMapping("/logout")
    @Operation(summary = "设备登出并吊销当前 token")
    public Result<Boolean> logout(@RequestBody DeviceAuthTokenRequestDTO request) {
        deviceAuthService.logoutDeviceToken(request);
        return new Result<Boolean>().ok(true);
    }

    @PostMapping("/revoke")
    @Operation(summary = "吊销指定设备 token")
    public Result<Boolean> revoke(@RequestBody DeviceAuthTokenRequestDTO request) {
        deviceAuthService.revokeDeviceToken(request);
        return new Result<Boolean>().ok(true);
    }

    @PostMapping("/introspect")
    @Operation(summary = "内部校验设备 token 状态")
    public Result<DeviceAuthIntrospectionDTO> introspect(@RequestBody DeviceAuthTokenRequestDTO request) throws Exception {
        return new Result<DeviceAuthIntrospectionDTO>().ok(deviceAuthService.introspectDeviceToken(request));
    }
}
