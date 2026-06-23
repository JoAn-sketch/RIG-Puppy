package xiaozhi.modules.childprofile.dto;

import java.io.Serializable;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
@Schema(description = "微信小程序登录响应")
public class WechatMiniLoginResponseDTO implements Serializable {

    @Schema(description = "微信 openid")
    private String openid;

    @Schema(description = "微信 session_key")
    private String sessionKey;
}
