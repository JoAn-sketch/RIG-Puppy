package xiaozhi.modules.childprofile.controller;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.AllArgsConstructor;
import xiaozhi.modules.childprofile.dto.WechatMiniAccountResponseDTO;
import xiaozhi.modules.childprofile.dto.WechatMiniBindPhoneDTO;
import xiaozhi.common.utils.Result;
import xiaozhi.modules.childprofile.dto.WechatMiniLoginDTO;
import xiaozhi.modules.childprofile.dto.WechatMiniLoginResponseDTO;
import xiaozhi.modules.childprofile.service.WechatMiniAuthService;

@RestController
@AllArgsConstructor
@RequestMapping("/api/v1/wechat-mini")
@Tag(name = "微信小程序登录")
public class WechatMiniAuthController {

    private final WechatMiniAuthService wechatMiniAuthService;

    @PostMapping("/login")
    @Operation(summary = "使用 wx.login code 换取 openid")
    public Result<WechatMiniLoginResponseDTO> login(@Valid @RequestBody WechatMiniLoginDTO dto) {
        WechatMiniLoginResponseDTO data = wechatMiniAuthService.login(dto.getCode());
        return new Result<WechatMiniLoginResponseDTO>().ok(data);
    }

    @PostMapping("/bind-phone")
    @Operation(summary = "使用微信手机号授权 code 创建账号并绑定微信账号")
    public Result<WechatMiniAccountResponseDTO> bindPhone(@Valid @RequestBody WechatMiniBindPhoneDTO dto) {
        WechatMiniAccountResponseDTO data = wechatMiniAuthService.bindPhone(dto.getLoginCode(), dto.getPhoneCode());
        return new Result<WechatMiniAccountResponseDTO>().ok(data);
    }
}
