package xiaozhi.modules.childprofile.service;

import xiaozhi.modules.childprofile.dto.ChildProfileResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileUpsertDTO;

public interface ChildProfileService {

    ChildProfileResponseDTO upsertProfile(ChildProfileUpsertDTO dto);

    ChildProfileResponseDTO getActiveProfile(String deviceId);
}
