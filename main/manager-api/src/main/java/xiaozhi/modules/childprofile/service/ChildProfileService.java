package xiaozhi.modules.childprofile.service;

import java.util.List;
import java.util.Map;

import xiaozhi.modules.childprofile.dto.ChildProfileResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileUpsertDTO;
import xiaozhi.modules.childprofile.dto.ChildLongTermMemoryResponseDTO;
import xiaozhi.modules.childprofile.dto.DailyActivitySummaryResponseDTO;

public interface ChildProfileService {

    ChildProfileResponseDTO upsertProfile(ChildProfileUpsertDTO dto);

    ChildProfileResponseDTO getActiveProfile(String deviceId);

    Map<String, Object> getProfileByOpenid(String openid);

    Map<String, Object> bindDevice(String openid, String deviceId);

    ChildLongTermMemoryResponseDTO getActiveLongTermMemory(String deviceId);

    DailyActivitySummaryResponseDTO getTodayCompanionSummary(String deviceId);

    List<DailyActivitySummaryResponseDTO> getTodayCompanionHistory(String deviceId, Integer days);
}
