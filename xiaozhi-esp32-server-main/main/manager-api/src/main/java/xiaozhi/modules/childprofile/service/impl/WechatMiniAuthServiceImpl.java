package xiaozhi.modules.childprofile.service.impl;

import java.util.Date;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;

import org.apache.commons.lang3.StringUtils;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import lombok.AllArgsConstructor;
import xiaozhi.common.exception.RenException;
import xiaozhi.common.utils.JsonUtils;
import xiaozhi.modules.childprofile.dao.WechatMiniAccountDao;
import xiaozhi.modules.childprofile.dto.WechatAccessTokenResponseDTO;
import xiaozhi.modules.childprofile.dto.WechatCode2SessionResponseDTO;
import xiaozhi.modules.childprofile.dto.WechatMiniAccountResponseDTO;
import xiaozhi.modules.childprofile.dto.WechatMiniLoginResponseDTO;
import xiaozhi.modules.childprofile.dto.WechatPhoneNumberResponseDTO;
import xiaozhi.modules.childprofile.entity.WechatMiniAccountEntity;
import xiaozhi.modules.childprofile.service.WechatMiniAuthService;
import xiaozhi.modules.sys.service.SysParamsService;

@Service
@AllArgsConstructor
public class WechatMiniAuthServiceImpl implements WechatMiniAuthService {

    private static final String WECHAT_MINI_APPID_PARAM = "wechat.mini.appid";
    private static final String WECHAT_MINI_SECRET_PARAM = "wechat.mini.secret";
    private static final String CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session";
    private static final String ACCESS_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token";
    private static final String GET_PHONE_NUMBER_URL = "https://api.weixin.qq.com/wxa/business/getuserphonenumber";

    private final SysParamsService sysParamsService;
    private final RestTemplate restTemplate;
    private final WechatMiniAccountDao wechatMiniAccountDao;

    @Override
    public WechatMiniLoginResponseDTO login(String code) {
        WechatCode2SessionResponseDTO response = code2Session(code);
        upsertAccount(response, null, null);

        return new WechatMiniLoginResponseDTO(response.getOpenid(), response.getSessionKey());
    }

    @Override
    public WechatMiniAccountResponseDTO bindPhone(String loginCode, String phoneCode) {
        WechatCode2SessionResponseDTO session = code2Session(loginCode);
        WechatPhoneNumberResponseDTO.PhoneInfo phoneInfo = getPhoneInfo(phoneCode);
        WechatMiniAccountEntity account = upsertAccount(session, phoneInfo, true);

        return toAccountResponse(account);
    }

    private WechatCode2SessionResponseDTO code2Session(String code) {
        String normalizedCode = StringUtils.trimToEmpty(code);
        if (StringUtils.isBlank(normalizedCode)) {
            throw new RenException("code is required");
        }

        WechatMiniConfig config = getWechatMiniConfig();

        String requestUrl = UriComponentsBuilder.fromHttpUrl(CODE2SESSION_URL)
                .queryParam("appid", config.appid())
                .queryParam("secret", config.secret())
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

        return response;
    }

    private WechatPhoneNumberResponseDTO.PhoneInfo getPhoneInfo(String phoneCode) {
        String normalizedPhoneCode = StringUtils.trimToEmpty(phoneCode);
        if (StringUtils.isBlank(normalizedPhoneCode)) {
            throw new RenException("phoneCode is required");
        }

        String accessToken = getAccessToken();
        String requestUrl = UriComponentsBuilder.fromHttpUrl(GET_PHONE_NUMBER_URL)
                .queryParam("access_token", accessToken)
                .build()
                .toUriString();

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        Map<String, String> requestBody = new HashMap<>();
        requestBody.put("code", normalizedPhoneCode);

        String responseText = restTemplate.postForObject(
                requestUrl,
                new HttpEntity<>(requestBody, headers),
                String.class);
        if (StringUtils.isBlank(responseText)) {
            throw new RenException("wechat phone bind failed: empty response");
        }

        WechatPhoneNumberResponseDTO response = JsonUtils.parseObject(
                responseText,
                WechatPhoneNumberResponseDTO.class);
        if (response == null) {
            throw new RenException("wechat phone bind failed: empty response");
        }
        if (response.getErrcode() != null && response.getErrcode() != 0) {
            throw new RenException("wechat phone bind failed: " + response.getErrmsg());
        }
        if (response.getPhoneInfo() == null
                || StringUtils.isBlank(getPhoneNumber(response.getPhoneInfo()))) {
            throw new RenException("wechat phone bind failed: phone missing");
        }

        return response.getPhoneInfo();
    }

    private String getAccessToken() {
        WechatMiniConfig config = getWechatMiniConfig();
        String requestUrl = UriComponentsBuilder.fromHttpUrl(ACCESS_TOKEN_URL)
                .queryParam("grant_type", "client_credential")
                .queryParam("appid", config.appid())
                .queryParam("secret", config.secret())
                .build()
                .toUriString();

        String responseText = restTemplate.getForObject(requestUrl, String.class);
        if (StringUtils.isBlank(responseText)) {
            throw new RenException("wechat access token failed: empty response");
        }

        WechatAccessTokenResponseDTO response = JsonUtils.parseObject(
                responseText,
                WechatAccessTokenResponseDTO.class);
        if (response == null) {
            throw new RenException("wechat access token failed: empty response");
        }
        if (response.getErrcode() != null && response.getErrcode() != 0) {
            throw new RenException("wechat access token failed: " + response.getErrmsg());
        }
        if (StringUtils.isBlank(response.getAccessToken())) {
            throw new RenException("wechat access token failed: token missing");
        }

        return response.getAccessToken();
    }

    private WechatMiniAccountEntity upsertAccount(
            WechatCode2SessionResponseDTO session,
            WechatPhoneNumberResponseDTO.PhoneInfo phoneInfo,
            Boolean phoneBound) {
        WechatMiniAccountEntity account = wechatMiniAccountDao.selectOne(
                new LambdaQueryWrapper<WechatMiniAccountEntity>()
                        .eq(WechatMiniAccountEntity::getOpenid, session.getOpenid())
                        .last("LIMIT 1"));

        Date now = new Date();
        if (account == null) {
            account = new WechatMiniAccountEntity();
            account.setAccountNo(generateAccountNo());
            account.setOpenid(session.getOpenid());
            account.setPhoneBound(0);
            account.setCreatedAt(now);
        }
        if (account.getPhoneBound() == null) {
            account.setPhoneBound(0);
        }

        account.setSessionKey(session.getSessionKey());
        account.setUnionid(session.getUnionid());
        account.setLastLoginAt(now);

        if (phoneInfo != null) {
            String phoneNumber = getPhoneNumber(phoneInfo);
            account.setPhoneNumber(phoneNumber);
            account.setPhoneNumberMasked(maskPhoneNumber(phoneNumber));
            account.setCountryCode(phoneInfo.getCountryCode());
            account.setPhoneBound(Boolean.TRUE.equals(phoneBound) ? 1 : account.getPhoneBound());
        }

        if (account.getId() == null) {
            wechatMiniAccountDao.insert(account);
        } else {
            wechatMiniAccountDao.updateById(account);
        }

        return account;
    }

    private WechatMiniAccountResponseDTO toAccountResponse(WechatMiniAccountEntity account) {
        return new WechatMiniAccountResponseDTO(
                account.getAccountNo(),
                account.getOpenid(),
                account.getPhoneNumberMasked(),
                account.getPhoneBound() != null && account.getPhoneBound() == 1);
    }

    private WechatMiniConfig getWechatMiniConfig() {
        String appid = sysParamsService.getValue(WECHAT_MINI_APPID_PARAM, true);
        String secret = sysParamsService.getValue(WECHAT_MINI_SECRET_PARAM, true);
        if (StringUtils.isBlank(appid) || StringUtils.isBlank(secret)) {
            throw new RenException("wechat mini appid/secret not configured");
        }
        return new WechatMiniConfig(appid, secret);
    }

    private String getPhoneNumber(WechatPhoneNumberResponseDTO.PhoneInfo phoneInfo) {
        if (StringUtils.isNotBlank(phoneInfo.getPurePhoneNumber())) {
            return phoneInfo.getPurePhoneNumber();
        }
        return StringUtils.trimToEmpty(phoneInfo.getPhoneNumber());
    }

    private String maskPhoneNumber(String phoneNumber) {
        String normalizedPhoneNumber = StringUtils.trimToEmpty(phoneNumber);
        if (normalizedPhoneNumber.length() < 7) {
            return normalizedPhoneNumber;
        }
        return normalizedPhoneNumber.substring(0, 3)
                + "****"
                + normalizedPhoneNumber.substring(normalizedPhoneNumber.length() - 4);
    }

    private String generateAccountNo() {
        return "puppy_" + UUID.randomUUID().toString().replace("-", "");
    }

    private record WechatMiniConfig(String appid, String secret) {
    }
}
