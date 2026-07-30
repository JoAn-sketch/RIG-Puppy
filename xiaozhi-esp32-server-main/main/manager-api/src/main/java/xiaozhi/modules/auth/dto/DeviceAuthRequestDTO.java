package xiaozhi.modules.auth.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "设备认证请求")
public class DeviceAuthRequestDTO {

    @Schema(description = "设备唯一标识，通常为 MAC 地址", requiredMode = Schema.RequiredMode.REQUIRED)
    private String deviceId;

    @Schema(description = "客户端连接标识；为空时默认使用 deviceId")
    private String clientId;

    @Schema(description = "当前固件版本，预留给认证策略使用")
    private String firmwareVersion;
}
