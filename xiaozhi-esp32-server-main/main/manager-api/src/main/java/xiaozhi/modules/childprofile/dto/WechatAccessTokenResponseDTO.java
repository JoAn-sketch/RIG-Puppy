package xiaozhi.modules.childprofile.dto;

import java.io.Serializable;

import com.fasterxml.jackson.annotation.JsonProperty;

import lombok.Data;

@Data
public class WechatAccessTokenResponseDTO implements Serializable {

    @JsonProperty("access_token")
    private String accessToken;

    @JsonProperty("expires_in")
    private Integer expiresIn;

    private Integer errcode;

    private String errmsg;
}
