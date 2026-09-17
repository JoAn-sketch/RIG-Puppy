package xiaozhi.modules.childprofile.controller;

import java.util.List;
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
import xiaozhi.modules.childprofile.dto.ChildLongTermMemoryActiveResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildLongTermMemoryResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileActiveResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileUpsertDTO;
import xiaozhi.modules.childprofile.dto.DailyActivitySummaryResponseDTO;
import xiaozhi.modules.childprofile.service.ChildProfileService;

@RestController
@AllArgsConstructor
@RequestMapping("/api/v1/child-profile")
@Tag(name = "儿童画像")
public class ChildProfileController {

    private final ChildProfileService childProfileService;

    @PostMapping
    @Operation(summary = "创建或更新儿童画像")
    public Result<ChildProfileActiveResponseDTO> upsert(@Valid @RequestBody ChildProfileUpsertDTO dto) {
        ChildProfileResponseDTO profile = childProfileService.upsertProfile(dto);
        Result<ChildProfileActiveResponseDTO> result = new Result<>();
        result.setMsg("profile updated");
        return result.ok(new ChildProfileActiveResponseDTO(profile));
    }

    @GetMapping("/active")
    @Operation(summary = "获取设备当前活跃儿童画像")
    public Result<ChildProfileActiveResponseDTO> getActive(@RequestParam("device_id") String deviceId) {
        ChildProfileResponseDTO profile = childProfileService.getActiveProfile(deviceId);
        return new Result<ChildProfileActiveResponseDTO>().ok(new ChildProfileActiveResponseDTO(profile));
    }

    @GetMapping("/account")
    @Operation(summary = "获取微信账号当前儿童画像")
    public Result<Map<String, Object>> getAccountProfile(@RequestParam("openid") String openid) {
        Map<String, Object> profile = childProfileService.getProfileByOpenid(openid);
        return new Result<Map<String, Object>>().ok(profile);
    }

    @PostMapping("/bind-device")
    @Operation(summary = "绑定微信账号和设备")
    public Result<Map<String, Object>> bindDevice(@RequestBody Map<String, Object> body) {
        Object openidValue = body.get("openid");
        Object deviceIdValue = body.get("deviceId");
        String openid = openidValue == null ? "" : String.valueOf(openidValue);
        String deviceId = deviceIdValue == null ? "" : String.valueOf(deviceIdValue);
        Map<String, Object> profile = childProfileService.bindDevice(openid, deviceId);
        return new Result<Map<String, Object>>().ok(profile);
    }

    @GetMapping("/long-term-memory/active")
    @Operation(summary = "获取设备当前活跃儿童长期记忆")
    public Result<ChildLongTermMemoryActiveResponseDTO> getActiveLongTermMemory(
            @RequestParam("device_id") String deviceId) {
        ChildLongTermMemoryResponseDTO memory = childProfileService.getActiveLongTermMemory(deviceId);
        return new Result<ChildLongTermMemoryActiveResponseDTO>()
                .ok(new ChildLongTermMemoryActiveResponseDTO(memory));
    }

    @GetMapping("/today-companion")
    @Operation(summary = "获取今日陪伴活动聚合摘要")
    public Result<DailyActivitySummaryResponseDTO> getTodayCompanionSummary(
            @RequestParam("device_id") String deviceId) {
        DailyActivitySummaryResponseDTO summary = childProfileService.getTodayCompanionSummary(deviceId);
        return new Result<DailyActivitySummaryResponseDTO>().ok(summary);
    }

    @GetMapping("/today-companion/history")
    @Operation(summary = "获取最近每日陪伴活动聚合摘要")
    public Result<List<DailyActivitySummaryResponseDTO>> getTodayCompanionHistory(
            @RequestParam("device_id") String deviceId,
            @RequestParam(value = "days", required = false) Integer days) {
        List<DailyActivitySummaryResponseDTO> summaries = childProfileService.getTodayCompanionHistory(deviceId, days);
        return new Result<List<DailyActivitySummaryResponseDTO>>().ok(summaries);
    }
}
