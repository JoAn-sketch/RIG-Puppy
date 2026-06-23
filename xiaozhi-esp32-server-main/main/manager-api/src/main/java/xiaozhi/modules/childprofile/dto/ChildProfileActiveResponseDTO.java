package xiaozhi.modules.childprofile.dto;

import java.io.Serializable;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "当前活跃儿童画像响应")
public class ChildProfileActiveResponseDTO implements Serializable {

    @Schema(description = "儿童画像")
    private ChildProfileResponseDTO childProfile;
}
