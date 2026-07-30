package xiaozhi.modules.childprofile.dto;

import java.io.Serializable;
import java.util.List;

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

    @Schema(description = "设备 ID（兼容旧客户端，当前不再用于账号绑定）")
    private String deviceId;

    @Min(3)
    @Max(11)
    @Schema(description = "年龄，范围 3-11", requiredMode = Schema.RequiredMode.REQUIRED)
    private Integer age;

    @NotBlank
    @Size(max = 32)
    @Schema(description = "孩子喜欢的称呼", requiredMode = Schema.RequiredMode.REQUIRED)
    private String nickname;

    @Size(max = 32)
    @Schema(description = "孩子希望如何称呼机器人")
    private String robotNamePreference;

    @Schema(description = "兴趣内容，最多 3 个")
    private List<@Size(max = 32) String> interests;
}
