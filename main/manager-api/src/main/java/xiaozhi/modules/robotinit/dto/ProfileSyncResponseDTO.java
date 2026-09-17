package xiaozhi.modules.robotinit.dto;

import java.util.Map;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;
import xiaozhi.modules.childprofile.dto.ChildLongTermMemoryResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileResponseDTO;

@Data
@Schema(description = "机器人 Profile 同步响应")
public class ProfileSyncResponseDTO {

    private RobotInitializationStatusDTO initialization;

    private ChildProfileResponseDTO profile;

    private ChildLongTermMemoryResponseDTO longTermMemory;

    private Map<String, Object> capabilities;

    private Map<String, Object> conversationConfiguration;

    private Map<String, Object> dailyGreetingConfiguration;

    private Map<String, Object> safetyConfiguration;
}
