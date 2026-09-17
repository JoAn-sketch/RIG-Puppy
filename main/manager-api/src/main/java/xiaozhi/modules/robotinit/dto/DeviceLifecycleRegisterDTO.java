package xiaozhi.modules.robotinit.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "设备注册生命周期请求")
public class DeviceLifecycleRegisterDTO {

    @Schema(description = "设备 ID，通常为 MAC 地址")
    private String deviceId;

    @Schema(description = "设备 MAC 地址")
    private String macAddress;

    @Schema(description = "客户端连接 ID")
    private String clientId;

    @Schema(description = "固件版本")
    private String firmwareVersion;

    @Schema(description = "设备型号")
    private String model;

    @Schema(description = "板型")
    private String board;
}
