package xiaozhi.modules.auth.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "设备 token 操作请求")
public class DeviceAuthTokenRequestDTO {

    @Schema(description = "设备唯一标识，通常为 MAC 地址", requiredMode = Schema.RequiredMode.REQUIRED)
    private String deviceId;

    @Schema(description = "客户端连接标识；为空时默认使用 deviceId")
    private String clientId;

    @Schema(description = "WebSocket 认证 token", requiredMode = Schema.RequiredMode.REQUIRED)
    private String token;
}
