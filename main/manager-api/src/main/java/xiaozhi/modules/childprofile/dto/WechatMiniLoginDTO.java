package xiaozhi.modules.childprofile.dto;

import java.io.Serializable;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
@Schema(description = "微信小程序登录参数")
public class WechatMiniLoginDTO implements Serializable {

    @NotBlank
    @Schema(description = "wx.login 返回的 code", requiredMode = Schema.RequiredMode.REQUIRED)
    private String code;
}
