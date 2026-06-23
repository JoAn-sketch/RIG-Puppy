package xiaozhi.modules.childprofile.service;

import xiaozhi.modules.childprofile.dto.WechatMiniLoginResponseDTO;

public interface WechatMiniAuthService {

    WechatMiniLoginResponseDTO login(String code);
}
