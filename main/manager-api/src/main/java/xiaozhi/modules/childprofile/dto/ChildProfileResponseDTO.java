package xiaozhi.modules.childprofile.dto;

import java.io.Serializable;
import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "儿童画像响应")
public class ChildProfileResponseDTO implements Serializable {

    @Schema(description = "孩子喜欢的称呼")
    private String nickname;

    @Schema(description = "年龄")
    private Integer age;

    @Schema(description = "年龄分档")
    private String ageGroup;

    @Schema(description = "孩子希望如何称呼机器人")
    private String robotNamePreference;

    @Schema(description = "兴趣内容")
    private List<String> interests;
}
