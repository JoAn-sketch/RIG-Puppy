package xiaozhi.modules.robotinit.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "设备绑定生命周期请求")
public class DeviceLifecycleBindDTO {

    @Schema(description = "微信 openid")
    private String openid;

    @Schema(description = "设备 ID")
    private String deviceId;

    @Schema(description = "家庭 ID，V1 可为空")
    private String householdId;
}
