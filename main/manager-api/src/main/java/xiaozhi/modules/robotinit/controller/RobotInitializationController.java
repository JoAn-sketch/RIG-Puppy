package xiaozhi.modules.robotinit.controller;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.AllArgsConstructor;
import xiaozhi.common.utils.Result;
import xiaozhi.modules.auth.dto.DeviceAuthRequestDTO;
import xiaozhi.modules.auth.dto.DeviceAuthResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileUpsertDTO;
import xiaozhi.modules.robotinit.dto.DeviceLifecycleBindDTO;
import xiaozhi.modules.robotinit.dto.DeviceLifecycleRegisterDTO;
import xiaozhi.modules.robotinit.dto.HouseholdCreateDTO;
import xiaozhi.modules.robotinit.dto.ProfileInitializeDTO;
import xiaozhi.modules.robotinit.dto.ProfileSyncResponseDTO;
import xiaozhi.modules.robotinit.dto.RobotSyncNotifyDTO;
import xiaozhi.modules.robotinit.dto.RobotInitializationStatusDTO;
import xiaozhi.modules.robotinit.service.RobotInitializationService;

@RestController
@AllArgsConstructor
@RequestMapping("/api/v1/robot-initialization")
@Tag(name = "机器人初始化")
public class RobotInitializationController {

    private final RobotInitializationService robotInitializationService;

    @PostMapping("/device/register")
    @Operation(summary = "Stage 1: 设备联网后注册硬件")
    public Result<RobotInitializationStatusDTO> registerDevice(
            @RequestBody DeviceLifecycleRegisterDTO dto) {
        return new Result<RobotInitializationStatusDTO>().ok(robotInitializationService.registerDevice(dto));
    }

    @PostMapping("/device/auth")
    @Operation(summary = "Stage 2: 设备获取 WebSocket 认证凭证")
    public Result<DeviceAuthResponseDTO> authDevice(@RequestBody DeviceAuthRequestDTO dto) throws Exception {
        return new Result<DeviceAuthResponseDTO>().ok(robotInitializationService.authenticateDevice(dto));
    }

    @PostMapping("/device/bind")
    @Operation(summary = "Stage 3: 微信账号确认绑定设备")
    public Result<RobotInitializationStatusDTO> bindDevice(@RequestBody DeviceLifecycleBindDTO dto) {
        return new Result<RobotInitializationStatusDTO>().ok(robotInitializationService.bindDevice(dto));
    }

    @PostMapping("/household/create")
    @Operation(summary = "Stage 4: 创建或恢复家庭")
    public Result<Map<String, Object>> createHousehold(@RequestBody HouseholdCreateDTO dto) {
        return new Result<Map<String, Object>>().ok(robotInitializationService.createHousehold(dto));
    }

    @PostMapping("/profile/initialize")
    @Operation(summary = "Stage 5: 创建空用户 Profile")
    public Result<RobotInitializationStatusDTO> initializeProfile(@RequestBody ProfileInitializeDTO dto) {
        return new Result<RobotInitializationStatusDTO>().ok(robotInitializationService.initializeProfile(dto));
    }

    @PostMapping("/profile/apply")
    @Operation(summary = "Stage 6: 应用小程序收集到的初始画像配置")
    public Result<ChildProfileResponseDTO> applyInitialConfiguration(
            @Valid @RequestBody ChildProfileUpsertDTO dto) {
        return new Result<ChildProfileResponseDTO>().ok(robotInitializationService.applyInitialConfiguration(dto));
    }

    @PostMapping("/robot/sync-notify")
    @Operation(summary = "Stage 7: 通知机器人需要同步配置")
    public Result<Map<String, Object>> notifyRobotSync(@RequestBody RobotSyncNotifyDTO dto) {
        return new Result<Map<String, Object>>().ok(robotInitializationService.notifyRobotSync(dto));
    }

    @GetMapping("/status")
    @Operation(summary = "获取可恢复的初始化进度")
    public Result<RobotInitializationStatusDTO> getStatus(
            @RequestParam(value = "device_id", required = false) String deviceId,
            @RequestParam(value = "openid", required = false) String openid) {
        return new Result<RobotInitializationStatusDTO>().ok(robotInitializationService.getStatus(deviceId, openid));
    }

    @GetMapping("/profile/sync")
    @Operation(summary = "Stage 6: 机器人同步当前 Profile 和对话配置")
    public Result<ProfileSyncResponseDTO> syncProfile(@RequestParam("device_id") String deviceId) {
        return new Result<ProfileSyncResponseDTO>().ok(robotInitializationService.syncProfile(deviceId));
    }

    @PostMapping("/legacy/bind-device")
    @Operation(summary = "兼容旧小程序: 绑定微信账号和设备")
    public Result<Map<String, Object>> legacyBindDevice(@RequestBody Map<String, Object> body) {
        Object openidValue = body.get("openid");
        Object deviceIdValue = body.get("deviceId");
        String openid = openidValue == null ? "" : String.valueOf(openidValue);
        String deviceId = deviceIdValue == null ? "" : String.valueOf(deviceIdValue);
        return new Result<Map<String, Object>>().ok(robotInitializationService.legacyBindDevice(openid, deviceId));
    }
}
