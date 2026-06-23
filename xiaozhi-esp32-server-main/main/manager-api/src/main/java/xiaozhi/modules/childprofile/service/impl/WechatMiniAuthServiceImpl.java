package xiaozhi.modules.childprofile.service.impl;

import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import lombok.AllArgsConstructor;
import xiaozhi.common.exception.RenException;
import xiaozhi.common.utils.JsonUtils;
import xiaozhi.modules.childprofile.dto.WechatCode2SessionResponseDTO;
import xiaozhi.modules.childprofile.dto.WechatMiniLoginResponseDTO;
import xiaozhi.modules.childprofile.service.WechatMiniAuthService;
import xiaozhi.modules.sys.service.SysParamsService;

@Service
@AllArgsConstructor
public class WechatMiniAuthServiceImpl implements WechatMiniAuthService {

    private static final String WECHAT_MINI_APPID_PARAM = "wechat.mini.appid";
    private static final String WECHAT_MINI_SECRET_PARAM = "wechat.mini.secret";
    private static final String CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session";

    private final SysParamsService sysParamsService;
    private final RestTemplate restTemplate;

    @Override
    public WechatMiniLoginResponseDTO login(String code) {
        String normalizedCode = StringUtils.trimToEmpty(code);
        if (StringUtils.isBlank(normalizedCode)) {
            throw new RenException("code is required");
        }

        String appid = sysParamsService.getValue(WECHAT_MINI_APPID_PARAM, true);
        String secret = sysParamsService.getValue(WECHAT_MINI_SECRET_PARAM, true);
        if (StringUtils.isBlank(appid) || StringUtils.isBlank(secret)) {
            throw new RenException("wechat mini appid/secret not configured");
        }

        String requestUrl = UriComponentsBuilder.fromHttpUrl(CODE2SESSION_URL)
                .queryParam("appid", appid)
                .queryParam("secret", secret)
                .queryParam("js_code", normalizedCode)
                .queryParam("grant_type", "authorization_code")
                .build()
                .toUriString();

        String responseText = restTemplate.getForObject(requestUrl, String.class);
        if (StringUtils.isBlank(responseText)) {
            throw new RenException("wechat login failed: empty response");
        }

        WechatCode2SessionResponseDTO response = JsonUtils.parseObject(
                responseText,
                WechatCode2SessionResponseDTO.class);
        if (response == null) {
            throw new RenException("wechat login failed: empty response");
        }
        if (response.getErrcode() != null && response.getErrcode() != 0) {
            throw new RenException("wechat login failed: " + response.getErrmsg());
        }
        if (StringUtils.isBlank(response.getOpenid())) {
            throw new RenException("wechat login failed: openid missing");
        }

        return new WechatMiniLoginResponseDTO(response.getOpenid(), response.getSessionKey());
    }
}
