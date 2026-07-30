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
@TableName("child_profile")
@Schema(description = "儿童基础画像")
public class ChildProfileEntity {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String openid;

    private String nickname;

    private Integer age;

    private String ageGroup;

    private String interestsJson;

    @TableField(fill = FieldFill.INSERT)
    private Date createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private Date updatedAt;
}
