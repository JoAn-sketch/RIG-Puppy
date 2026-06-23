package xiaozhi.modules.childprofile.service.impl;

import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;

import xiaozhi.common.exception.RenException;
import xiaozhi.modules.childprofile.dao.ChildProfileDao;
import xiaozhi.modules.childprofile.dao.DeviceChildBindingDao;
import xiaozhi.modules.childprofile.dto.ChildProfileResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileUpsertDTO;
import xiaozhi.modules.childprofile.entity.ChildProfileEntity;
import xiaozhi.modules.childprofile.entity.DeviceChildBindingEntity;
import xiaozhi.modules.childprofile.service.ChildProfileService;

@Service
public class ChildProfileServiceImpl implements ChildProfileService {

    private final ChildProfileDao childProfileDao;
    private final DeviceChildBindingDao deviceChildBindingDao;

    public ChildProfileServiceImpl(ChildProfileDao childProfileDao, DeviceChildBindingDao deviceChildBindingDao) {
        this.childProfileDao = childProfileDao;
        this.deviceChildBindingDao = deviceChildBindingDao;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ChildProfileResponseDTO upsertProfile(ChildProfileUpsertDTO dto) {
        Integer age = dto.getAge();
        if (age == null || age < 3 || age > 11) {
            throw new RenException("age must be between 3 and 11");
        }
        String normalizedNickname = normalizeNickname(dto.getNickname());
        if (StringUtils.isBlank(normalizedNickname)) {
            throw new RenException("nickname required");
        }

        String normalizedOpenid = normalizeOpenid(dto.getOpenid());
        String normalizedDeviceId = normalizeDeviceId(dto.getDeviceId());
        String ageGroup = mapAgeGroup(age);

        ChildProfileEntity profileEntity = childProfileDao.selectOne(
                new LambdaQueryWrapper<ChildProfileEntity>()
                        .eq(ChildProfileEntity::getOpenid, normalizedOpenid)
                        .last("LIMIT 1"));
        if (profileEntity == null) {
            profileEntity = new ChildProfileEntity();
            profileEntity.setOpenid(normalizedOpenid);
            profileEntity.setNickname(normalizedNickname);
            profileEntity.setAge(age);
            profileEntity.setAgeGroup(ageGroup);
            childProfileDao.insert(profileEntity);
        } else {
            profileEntity.setNickname(normalizedNickname);
            profileEntity.setAge(age);
            profileEntity.setAgeGroup(ageGroup);
            childProfileDao.updateById(profileEntity);
        }

        DeviceChildBindingEntity bindingEntity = deviceChildBindingDao.selectOne(
                new LambdaQueryWrapper<DeviceChildBindingEntity>()
                        .eq(DeviceChildBindingEntity::getDeviceId, normalizedDeviceId)
                        .last("LIMIT 1"));
        if (bindingEntity == null) {
            bindingEntity = new DeviceChildBindingEntity();
            bindingEntity.setDeviceId(normalizedDeviceId);
            bindingEntity.setOpenid(normalizedOpenid);
            bindingEntity.setIsActive(1);
            deviceChildBindingDao.insert(bindingEntity);
        } else {
            bindingEntity.setDeviceId(normalizedDeviceId);
            bindingEntity.setOpenid(normalizedOpenid);
            bindingEntity.setIsActive(1);
            deviceChildBindingDao.updateById(bindingEntity);
        }

        return new ChildProfileResponseDTO(normalizedNickname, age, ageGroup);
    }

    @Override
    public ChildProfileResponseDTO getActiveProfile(String deviceId) {
        String normalizedDeviceId = normalizeDeviceId(deviceId);
        DeviceChildBindingEntity bindingEntity = deviceChildBindingDao.selectOne(
                new LambdaQueryWrapper<DeviceChildBindingEntity>()
                        .eq(DeviceChildBindingEntity::getDeviceId, normalizedDeviceId)
                        .eq(DeviceChildBindingEntity::getIsActive, 1)
                        .last("LIMIT 1"));
        if (bindingEntity == null || StringUtils.isBlank(bindingEntity.getOpenid())) {
            return null;
        }

        ChildProfileEntity profileEntity = childProfileDao.selectOne(
                new LambdaQueryWrapper<ChildProfileEntity>()
                        .eq(ChildProfileEntity::getOpenid, bindingEntity.getOpenid())
                        .last("LIMIT 1"));
        if (profileEntity == null) {
            return null;
        }

        return new ChildProfileResponseDTO(
                profileEntity.getNickname(),
                profileEntity.getAge(),
                profileEntity.getAgeGroup());
    }

    private String normalizeOpenid(String value) {
        return StringUtils.trimToEmpty(value);
    }

    private String normalizeDeviceId(String value) {
        String normalized = StringUtils.trimToEmpty(value);
        return normalized.toLowerCase();
    }

    private String normalizeNickname(String value) {
        return StringUtils.trimToEmpty(value);
    }

    private String mapAgeGroup(int age) {
        if (age >= 3 && age <= 5) {
            return "3-5";
        }
        if (age >= 6 && age <= 8) {
            return "6-8";
        }
        if (age >= 9 && age <= 11) {
            return "9-11";
        }
        return "6-8";
    }
}
