package xiaozhi.modules.auth.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "设备认证响应")
public class DeviceAuthResponseDTO {

    @Schema(description = "WebSocket 认证 token；关闭认证时为空")
    private String token;

    @Schema(description = "token 有效期，单位秒")
    private Integer expireSeconds;

    @Schema(description = "WebSocket 地址")
    private String websocketUrl;

    @Schema(description = "是否开启 WebSocket token 认证")
    private Boolean authEnabled;
}
