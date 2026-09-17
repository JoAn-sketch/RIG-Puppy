package xiaozhi.modules.robotinit.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "通知机器人同步请求")
public class RobotSyncNotifyDTO {

    @Schema(description = "设备 ID")
    private String deviceId;
}
