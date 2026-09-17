package xiaozhi.modules.robotinit.service;

import java.util.Map;

import xiaozhi.modules.auth.dto.DeviceAuthRequestDTO;
import xiaozhi.modules.auth.dto.DeviceAuthResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileUpsertDTO;
import xiaozhi.modules.robotinit.dto.DeviceLifecycleBindDTO;
import xiaozhi.modules.robotinit.dto.DeviceLifecycleRegisterDTO;
import xiaozhi.modules.robotinit.dto.HouseholdCreateDTO;
import xiaozhi.modules.robotinit.dto.ProfileSyncResponseDTO;
import xiaozhi.modules.robotinit.dto.ProfileInitializeDTO;
import xiaozhi.modules.robotinit.dto.RobotSyncNotifyDTO;
import xiaozhi.modules.robotinit.dto.RobotInitializationStatusDTO;

public interface RobotInitializationService {

    RobotInitializationStatusDTO registerDevice(DeviceLifecycleRegisterDTO dto);

    DeviceAuthResponseDTO authenticateDevice(DeviceAuthRequestDTO dto) throws Exception;

    RobotInitializationStatusDTO bindDevice(DeviceLifecycleBindDTO dto);

    Map<String, Object> createHousehold(HouseholdCreateDTO dto);

    RobotInitializationStatusDTO initializeProfile(ProfileInitializeDTO dto);

    ChildProfileResponseDTO applyInitialConfiguration(ChildProfileUpsertDTO dto);

    Map<String, Object> notifyRobotSync(RobotSyncNotifyDTO dto);

    RobotInitializationStatusDTO getStatus(String deviceId, String openid);

    ProfileSyncResponseDTO syncProfile(String deviceId);

    Map<String, Object> legacyBindDevice(String openid, String deviceId);
}
