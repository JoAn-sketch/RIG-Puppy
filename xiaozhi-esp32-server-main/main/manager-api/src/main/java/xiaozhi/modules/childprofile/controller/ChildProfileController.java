package xiaozhi.modules.childprofile.controller;

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
import xiaozhi.modules.childprofile.dto.ChildProfileActiveResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileUpsertDTO;
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
}
