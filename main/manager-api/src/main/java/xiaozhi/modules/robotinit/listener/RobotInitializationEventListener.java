package xiaozhi.modules.robotinit.listener;

import java.util.Map;

import org.apache.commons.lang3.StringUtils;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;

import lombok.RequiredArgsConstructor;
import xiaozhi.modules.agent.dao.AgentDao;
import xiaozhi.modules.agent.entity.AgentEntity;
import xiaozhi.modules.childprofile.dao.ChildProfileDao;
import xiaozhi.modules.childprofile.dao.DeviceChildBindingDao;
import xiaozhi.modules.childprofile.entity.ChildProfileEntity;
import xiaozhi.modules.childprofile.entity.DeviceChildBindingEntity;
import xiaozhi.modules.childprofile.service.ChildProfileService;
import xiaozhi.modules.device.dao.DeviceDao;
import xiaozhi.modules.device.entity.DeviceEntity;
import xiaozhi.modules.device.support.DeviceLifecycleStatus;
import xiaozhi.modules.robotinit.event.DeviceBindSucceededEvent;
import xiaozhi.modules.robotinit.event.InitialConfigurationAppliedEvent;
import xiaozhi.modules.robotinit.event.ProfileInitializedEvent;

@Component
@RequiredArgsConstructor
public class RobotInitializationEventListener {

    private static final String PROFILE_STATUS_COMPLETED = "COMPLETED";
    private static final String BINDING_STATUS_BOUND = "BOUND";

    private final DeviceDao deviceDao;
    private final AgentDao agentDao;
    private final ChildProfileDao childProfileDao;
    private final DeviceChildBindingDao deviceChildBindingDao;
    private final ChildProfileService childProfileService;

    @EventListener
    @Transactional(rollbackFor = Exception.class)
    public void onDeviceBindSucceeded(DeviceBindSucceededEvent event) {
        String deviceId = normalizeDeviceId(event.getDeviceId());
        String openid = normalizeOpenid(event.getOpenid());
        if (StringUtils.isBlank(deviceId) || StringUtils.isBlank(openid)) {
            return;
        }

        updateBindingMetadata(deviceId, openid, event.getHouseholdId());
        ensureDeviceRuntimeConfig(deviceId);
        Map<String, Object> profile = childProfileService.getProfileByOpenid(openid);
        if (Boolean.TRUE.equals(profile.get("profileCompleted"))) {
            updateDeviceLifecycle(deviceId, DeviceLifecycleStatus.BOUND);
            updateDeviceLifecycle(deviceId, DeviceLifecycleStatus.PROFILE_INITIALIZED);
            updateDeviceLifecycle(deviceId, DeviceLifecycleStatus.READY);
            return;
        }

        updateDeviceLifecycle(deviceId, DeviceLifecycleStatus.BOUND);
        childProfileService.initializeProfileStorage(openid);
        updateDeviceLifecycle(deviceId, DeviceLifecycleStatus.PROFILE_INITIALIZED);
    }

    @EventListener
    @Transactional(rollbackFor = Exception.class)
    public void onProfileInitialized(ProfileInitializedEvent event) {
        String deviceId = normalizeDeviceId(event.getDeviceId());
        if (StringUtils.isBlank(deviceId)) {
            deviceId = resolveActiveDeviceId(event.getOpenid());
        }
        updateDeviceLifecycle(deviceId, DeviceLifecycleStatus.PROFILE_INITIALIZED);
    }

    @EventListener
    @Transactional(rollbackFor = Exception.class)
    public void onInitialConfigurationApplied(InitialConfigurationAppliedEvent event) {
        String openid = normalizeOpenid(event.getOpenid());
        String deviceId = normalizeDeviceId(event.getDeviceId());
        if (StringUtils.isBlank(deviceId)) {
            deviceId = resolveActiveDeviceId(openid);
        }
        markProfileCompleted(openid);
        ensureDeviceRuntimeConfig(deviceId);
        updateDeviceLifecycle(deviceId, DeviceLifecycleStatus.READY);
    }

    private void ensureDeviceRuntimeConfig(String deviceId) {
        if (StringUtils.isBlank(deviceId)) {
            return;
        }
        DeviceEntity device = deviceDao.selectById(deviceId);
        if (device == null) {
            return;
        }
        if (device.getUserId() != null && StringUtils.isNotBlank(device.getAgentId())) {
            return;
        }

        AgentEntity agent = resolveRuntimeAgent(device);
        if (agent == null || StringUtils.isBlank(agent.getId())) {
            return;
        }

        boolean changed = false;
        if (StringUtils.isBlank(device.getAgentId())) {
            device.setAgentId(agent.getId());
            changed = true;
        }
        if (device.getUserId() == null && agent.getUserId() != null) {
            device.setUserId(agent.getUserId());
            changed = true;
        }
        if (changed) {
            deviceDao.updateById(device);
        }
    }

    private AgentEntity resolveRuntimeAgent(DeviceEntity device) {
        if (StringUtils.isNotBlank(device.getAgentId())) {
            AgentEntity agent = agentDao.selectById(device.getAgentId());
            if (agent != null) {
                return agent;
            }
        }

        LambdaQueryWrapper<AgentEntity> wrapper = new LambdaQueryWrapper<AgentEntity>()
                .isNotNull(AgentEntity::getLlmModelId)
                .isNotNull(AgentEntity::getTtsModelId)
                .isNotNull(AgentEntity::getVadModelId)
                .isNotNull(AgentEntity::getAsrModelId)
                .orderByDesc(AgentEntity::getUpdatedAt)
                .last("LIMIT 1");
        if (device.getUserId() != null) {
            wrapper.eq(AgentEntity::getUserId, device.getUserId());
            AgentEntity userAgent = agentDao.selectOne(wrapper);
            if (userAgent != null) {
                return userAgent;
            }
        }

        return agentDao.selectOne(new LambdaQueryWrapper<AgentEntity>()
                .isNotNull(AgentEntity::getUserId)
                .isNotNull(AgentEntity::getLlmModelId)
                .isNotNull(AgentEntity::getTtsModelId)
                .isNotNull(AgentEntity::getVadModelId)
                .isNotNull(AgentEntity::getAsrModelId)
                .orderByDesc(AgentEntity::getUpdatedAt)
                .last("LIMIT 1"));
    }

    private void updateBindingMetadata(String deviceId, String openid, String householdId) {
        DeviceChildBindingEntity binding = deviceChildBindingDao.selectOne(
                new LambdaQueryWrapper<DeviceChildBindingEntity>()
                        .eq(DeviceChildBindingEntity::getDeviceId, deviceId)
                        .last("LIMIT 1"));
        if (binding == null) {
            return;
        }
        binding.setOpenid(openid);
        binding.setOwnerOpenid(openid);
        binding.setBindingStatus(BINDING_STATUS_BOUND);
        binding.setIsActive(1);
        if (StringUtils.isNotBlank(householdId)) {
            binding.setHouseholdId(StringUtils.trimToEmpty(householdId));
        }
        deviceChildBindingDao.updateById(binding);
    }

    private void markProfileCompleted(String openid) {
        if (StringUtils.isBlank(openid)) {
            return;
        }
        ChildProfileEntity profile = childProfileDao.selectOne(
                new LambdaQueryWrapper<ChildProfileEntity>()
                        .eq(ChildProfileEntity::getOpenid, openid)
                        .last("LIMIT 1"));
        if (profile == null) {
            return;
        }
        if (PROFILE_STATUS_COMPLETED.equalsIgnoreCase(StringUtils.trimToEmpty(profile.getStatus()))) {
            return;
        }
        profile.setStatus(PROFILE_STATUS_COMPLETED);
        childProfileDao.updateById(profile);
    }

    private void updateDeviceLifecycle(String deviceId, DeviceLifecycleStatus status) {
        if (StringUtils.isBlank(deviceId) || status == null) {
            return;
        }
        DeviceEntity device = deviceDao.selectById(deviceId);
        if (device == null) {
            return;
        }
        DeviceLifecycleStatus currentStatus = DeviceLifecycleStatus.from(device.getLifecycleStatus());
        if (currentStatus == DeviceLifecycleStatus.READY
                && (status == DeviceLifecycleStatus.BOUND || status == DeviceLifecycleStatus.PROFILE_INITIALIZED)) {
            return;
        }
        if (currentStatus == DeviceLifecycleStatus.PROFILE_INITIALIZED && status == DeviceLifecycleStatus.BOUND) {
            return;
        }
        if (currentStatus == DeviceLifecycleStatus.NEW) {
            DeviceLifecycleStatus.transition(device, DeviceLifecycleStatus.REGISTERED);
            DeviceLifecycleStatus.transition(device, DeviceLifecycleStatus.UNBOUND);
        } else if (currentStatus == DeviceLifecycleStatus.REGISTERED) {
            DeviceLifecycleStatus.transition(device, DeviceLifecycleStatus.UNBOUND);
        }
        DeviceLifecycleStatus.transition(device, status);
        deviceDao.updateById(device);
    }

    private String resolveActiveDeviceId(String openid) {
        if (StringUtils.isBlank(openid)) {
            return "";
        }
        DeviceChildBindingEntity binding = deviceChildBindingDao.selectOne(
                new LambdaQueryWrapper<DeviceChildBindingEntity>()
                        .eq(DeviceChildBindingEntity::getOpenid, openid)
                        .eq(DeviceChildBindingEntity::getIsActive, 1)
                        .last("LIMIT 1"));
        return binding == null ? "" : normalizeDeviceId(binding.getDeviceId());
    }

    private String normalizeOpenid(String value) {
        return StringUtils.trimToEmpty(value);
    }

    private String normalizeDeviceId(String value) {
        return StringUtils.trimToEmpty(value).toLowerCase();
    }
}
