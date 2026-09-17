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
@TableName("device_child_binding")
@Schema(description = "设备与儿童画像绑定")
public class DeviceChildBindingEntity {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String deviceId;

    private String openid;

    private Integer isActive;

    @TableField(fill = FieldFill.INSERT)
    private Date createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private Date updatedAt;
}
