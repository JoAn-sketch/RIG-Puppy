package xiaozhi.modules.robotinit.event;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class ProfileInitializedEvent {
    private String deviceId;
    private String openid;
}
