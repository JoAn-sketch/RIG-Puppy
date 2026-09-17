package xiaozhi.modules.robotinit.event;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class InitialConfigurationAppliedEvent {
    private String deviceId;
    private String openid;
}
