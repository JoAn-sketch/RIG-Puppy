package xiaozhi.modules.robotinit.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "创建家庭请求")
public class HouseholdCreateDTO {

    @Schema(description = "微信 openid")
    private String openid;

    @Schema(description = "设备 ID")
    private String deviceId;

    @Schema(description = "家庭名称")
    private String householdName;
}
