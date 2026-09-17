package xiaozhi.modules.robotinit.event;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class DeviceBindSucceededEvent {
    private String deviceId;
    private String openid;
    private String householdId;
}
