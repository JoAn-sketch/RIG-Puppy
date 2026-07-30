package xiaozhi.modules.auth.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "设备 token 校验结果")
public class DeviceAuthIntrospectionDTO {

    @Schema(description = "token 是否有效")
    private Boolean valid;

    @Schema(description = "失败原因；有效时为空")
    private String reason;

    @Schema(description = "token 剩余有效期，单位秒")
    private Integer remainingSeconds;

    @Schema(description = "是否开启 WebSocket token 认证")
    private Boolean authEnabled;
}
