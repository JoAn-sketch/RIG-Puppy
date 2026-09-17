package xiaozhi.modules.childprofile.service;

import xiaozhi.modules.childprofile.dto.WechatMiniLoginResponseDTO;
import xiaozhi.modules.childprofile.dto.WechatMiniAccountResponseDTO;

public interface WechatMiniAuthService {

    WechatMiniLoginResponseDTO login(String code);

    WechatMiniAccountResponseDTO bindPhone(String loginCode, String phoneCode);
}
