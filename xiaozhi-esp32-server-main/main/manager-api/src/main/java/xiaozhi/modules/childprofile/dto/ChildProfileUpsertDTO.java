package xiaozhi.modules.childprofile.dto;

import java.io.Serializable;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
@Schema(description = "儿童画像提交参数")
public class ChildProfileUpsertDTO implements Serializable {

    @NotBlank
    @Schema(description = "微信 openid", requiredMode = Schema.RequiredMode.REQUIRED)
    private String openid;

    @NotBlank
    @Schema(description = "设备 ID", requiredMode = Schema.RequiredMode.REQUIRED)
    private String deviceId;

    @Min(3)
    @Max(11)
    @Schema(description = "年龄，范围 3-11", requiredMode = Schema.RequiredMode.REQUIRED)
    private Integer age;

    @NotBlank
    @Size(max = 32)
    @Schema(description = "孩子喜欢的称呼", requiredMode = Schema.RequiredMode.REQUIRED)
    private String nickname;
}
