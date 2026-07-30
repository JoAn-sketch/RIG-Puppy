package xiaozhi.modules.childprofile.dto;

import java.io.Serializable;

import com.fasterxml.jackson.annotation.JsonProperty;

import lombok.Data;

@Data
public class WechatPhoneNumberResponseDTO implements Serializable {

    private Integer errcode;

    private String errmsg;

    @JsonProperty("phone_info")
    private PhoneInfo phoneInfo;

    @Data
    public static class PhoneInfo implements Serializable {

        private String phoneNumber;

        private String purePhoneNumber;

        private String countryCode;
    }
}
