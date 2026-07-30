package xiaozhi.modules.childprofile.entity;

import java.util.Date;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@TableName("wechat_mini_account")
@Schema(description = "微信小程序账号绑定")
public class WechatMiniAccountEntity {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String accountNo;

    private String openid;

    private String unionid;

    private String sessionKey;

    private String phoneNumber;

    private String phoneNumberMasked;

    private String countryCode;

    private Integer phoneBound;

    @TableField(fill = FieldFill.INSERT)
    private Date createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private Date updatedAt;

    private Date lastLoginAt;
}
