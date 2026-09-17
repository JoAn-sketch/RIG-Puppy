package xiaozhi.modules.childprofile.dto;

import java.io.Serializable;
import java.util.Date;
import java.util.List;
import java.util.Map;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "儿童长期记忆响应")
public class ChildLongTermMemoryResponseDTO implements Serializable {

    @Schema(description = "孩子喜欢的称呼")
    private String nicknamePreference;

    @Schema(description = "年龄")
    private Integer age;

    @Schema(description = "年龄分档")
    private String ageGroup;

    @Schema(description = "孩子希望如何称呼机器人")
    private String robotNamePreference;

    @Schema(description = "兴趣列表")
    private List<String> interests;

    @Schema(description = "喜欢的小狗类型")
    private List<String> favoriteDogTypes;

    @Schema(description = "最想和机器人做什么")
    private List<String> desiredActivities;

    @Schema(description = "家长希望机器人帮助什么")
    private List<String> parentGoals;

    @Schema(description = "后续扩展字段")
    private Map<String, Object> extraAttributes;

    @Schema(description = "长期记忆结构版本")
    private Integer profileVersion;

    @Schema(description = "最近更新时间")
    private Date updatedAt;
}
