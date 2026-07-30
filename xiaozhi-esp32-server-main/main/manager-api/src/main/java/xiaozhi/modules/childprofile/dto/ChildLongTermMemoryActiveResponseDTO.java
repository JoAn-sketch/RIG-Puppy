package xiaozhi.modules.childprofile.dto;

import java.io.Serializable;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "当前活跃儿童长期记忆响应")
public class ChildLongTermMemoryActiveResponseDTO implements Serializable {

    @Schema(description = "长期记忆")
    private ChildLongTermMemoryResponseDTO longTermMemory;
}
