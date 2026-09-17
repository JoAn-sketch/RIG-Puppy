package xiaozhi.modules.robotinit.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "机器人初始化状态")
public class RobotInitializationStatusDTO {

    private String deviceId;

    private String openid;

    private String status;

    private Boolean registered;

    private Boolean bound;

    private Boolean profileInitialized;

    private Boolean profileCompleted;

    private String nextStep;
}
