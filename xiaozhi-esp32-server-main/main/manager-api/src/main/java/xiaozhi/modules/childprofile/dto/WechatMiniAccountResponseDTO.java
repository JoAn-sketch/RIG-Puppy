package xiaozhi.modules.childprofile.dto;

import java.io.Serializable;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
@Schema(description = "微信小程序账号响应")
public class WechatMiniAccountResponseDTO implements Serializable {

    @Schema(description = "Puppy 账号编号")
    private String accountNo;

    @Schema(description = "微信 openid")
    private String openid;

    @Schema(description = "脱敏手机号")
    private String phoneNumberMasked;

    @Schema(description = "是否已绑定手机号")
    private Boolean phoneBound;
}
