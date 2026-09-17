package xiaozhi.modules.robotinit.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "初始化用户 Profile 请求")
public class ProfileInitializeDTO {

    @Schema(description = "微信 openid")
    private String openid;

    @Schema(description = "设备 ID")
    private String deviceId;
}
