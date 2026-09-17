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
@TableName("child_long_term_memory")
@Schema(description = "儿童长期记忆")
public class ChildLongTermMemoryEntity {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String openid;

    private String nicknamePreference;

    private Integer age;

    private String ageGroup;

    private Integer profileVersion;

    private String profileJson;

    @TableField(fill = FieldFill.INSERT)
    private Date createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private Date updatedAt;
}
