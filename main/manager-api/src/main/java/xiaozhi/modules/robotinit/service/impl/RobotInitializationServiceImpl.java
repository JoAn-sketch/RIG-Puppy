package xiaozhi.modules.robotinit.service.impl;

import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestTemplate;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;

import lombok.RequiredArgsConstructor;
import xiaozhi.common.exception.RenException;
import xiaozhi.modules.auth.dto.DeviceAuthRequestDTO;
import xiaozhi.modules.auth.dto.DeviceAuthResponseDTO;
import xiaozhi.modules.auth.service.DeviceAuthService;
import xiaozhi.modules.childprofile.dao.ChildProfileDao;
import xiaozhi.modules.childprofile.dao.DeviceChildBindingDao;
import xiaozhi.modules.childprofile.dto.ChildLongTermMemoryResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileUpsertDTO;
import xiaozhi.modules.childprofile.entity.ChildProfileEntity;
import xiaozhi.modules.childprofile.entity.DeviceChildBindingEntity;
import xiaozhi.modules.childprofile.service.ChildProfileService;
import xiaozhi.modules.device.dao.DeviceDao;
import xiaozhi.modules.device.entity.DeviceEntity;
import xiaozhi.modules.device.support.DeviceLifecycleStatus;
import xiaozhi.modules.robotinit.dao.HouseholdDao;
import xiaozhi.modules.robotinit.dto.DeviceLifecycleBindDTO;
import xiaozhi.modules.robotinit.dto.DeviceLifecycleRegisterDTO;
import xiaozhi.modules.robotinit.dto.HouseholdCreateDTO;
import xiaozhi.modules.robotinit.dto.ProfileInitializeDTO;
import xiaozhi.modules.robotinit.dto.ProfileSyncResponseDTO;
import xiaozhi.modules.robotinit.dto.RobotSyncNotifyDTO;
import xiaozhi.modules.robotinit.dto.RobotInitializationStatusDTO;
import xiaozhi.modules.robotinit.entity.HouseholdEntity;
import xiaozhi.modules.robotinit.event.DeviceBindSucceededEvent;
import xiaozhi.modules.robotinit.service.RobotInitializationService;

@Service
@RequiredArgsConstructor
public class RobotInitializationServiceImpl implements RobotInitializationService {

    private static final String PROFILE_STATUS_INITIALIZED = "INITIALIZED";
    private static final String PROFILE_STATUS_COMPLETED = "COMPLETED";
    private static final String BINDING_STATUS_BOUND = "BOUND";
    private static final String BINDING_STATUS_INACTIVE = "INACTIVE";
    private static final String HOUSEHOLD_STATUS_ACTIVE = "ACTIVE";
    private static final String FIRST_ADOPTION_GREETING_TEMPLATE =
            "你好呀，{user_name}！我是{robot_name}，谢谢你带我回家！以后请多多关照，我们一起长大吧！";

    private final DeviceDao deviceDao;
    private final DeviceAuthService deviceAuthService;
    private final ChildProfileDao childProfileDao;
    private final DeviceChildBindingDao deviceChildBindingDao;
    private final HouseholdDao householdDao;
    private final ChildProfileService childProfileService;
    private final ApplicationEventPublisher eventPublisher;
    private final RestTemplate restTemplate;

    @Value("${xiaozhi.runtime-debug.base-url:http://127.0.0.1:8003}")
    private String runtimeDebugBaseUrl;

    @Value("${xiaozhi.runtime-debug.token:04219c19-8d5b-410c-84af-511faf293509}")
    private String runtimeDebugToken;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public RobotInitializationStatusDTO registerDevice(DeviceLifecycleRegisterDTO dto) {
        if (dto == null) {
            throw new RenException("device register payload required");
        }

        String deviceId = normalizeDeviceId(firstNonBlank(dto.getDeviceId(), dto.getMacAddress()));
        if (StringUtils.isBlank(deviceId)) {
            throw new RenException("deviceId required");
        }

        String macAddress = normalizeDeviceId(firstNonBlank(dto.getMacAddress(), deviceId));
        DeviceEntity device = findDevice(deviceId, macAddress);
        Date now = new Date();
        boolean inserting = false;
        if (device == null) {
            device = new DeviceEntity();
            device.setId(deviceId);
            device.setMacAddress(macAddress);
            device.setAutoUpdate(1);
            device.setCreateDate(now);
            inserting = true;
        }

        device.setLastConnectedAt(now);
        device.setUpdateDate(now);
        applyDeviceMetadata(device, dto.getClientId(), dto.getFirmwareVersion(), dto.getBoard(), dto.getModel());
        DeviceLifecycleStatus currentStatus = DeviceLifecycleStatus.from(device.getLifecycleStatus());
        if (currentStatus == DeviceLifecycleStatus.NEW) {
            DeviceLifecycleStatus.transition(device, DeviceLifecycleStatus.REGISTERED);
            DeviceLifecycleStatus.transition(device, DeviceLifecycleStatus.UNBOUND);
        } else if (currentStatus == DeviceLifecycleStatus.REGISTERED) {
            DeviceLifecycleStatus.transition(device, DeviceLifecycleStatus.UNBOUND);
        }

        if (inserting) {
            deviceDao.insert(device);
        } else {
            deviceDao.updateById(device);
        }

        return getStatus(device.getId(), null);
    }

    @Override
    public DeviceAuthResponseDTO authenticateDevice(DeviceAuthRequestDTO dto) throws Exception {
        return deviceAuthService.authenticateDevice(dto);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public RobotInitializationStatusDTO bindDevice(DeviceLifecycleBindDTO dto) {
        if (dto == null) {
            throw new RenException("device bind payload required");
        }
        String openid = normalizeOpenid(dto.getOpenid());
        String deviceId = normalizeDeviceId(dto.getDeviceId());
        if (StringUtils.isBlank(openid)) {
            throw new RenException("openid required");
        }
        if (StringUtils.isBlank(deviceId)) {
            throw new RenException("deviceId required");
        }

        ensureRegisteredDevice(deviceId);
        deactivateActiveBindingsForOpenid(openid);
        deactivateActiveBindingsForDevice(deviceId);

        DeviceChildBindingEntity binding = deviceChildBindingDao.selectOne(
                new LambdaQueryWrapper<DeviceChildBindingEntity>()
                        .eq(DeviceChildBindingEntity::getDeviceId, deviceId)
                        .last("LIMIT 1"));
        if (binding == null) {
            binding = new DeviceChildBindingEntity();
            binding.setDeviceId(deviceId);
            binding.setOpenid(openid);
        }
        binding.setOpenid(openid);
        binding.setHouseholdId(StringUtils.trimToEmpty(dto.getHouseholdId()));
        binding.setOwnerOpenid(openid);
        binding.setBindingStatus(BINDING_STATUS_BOUND);
        binding.setIsActive(1);
        if (binding.getId() == null) {
            deviceChildBindingDao.insert(binding);
        } else {
            deviceChildBindingDao.updateById(binding);
        }

        eventPublisher.publishEvent(new DeviceBindSucceededEvent(deviceId, openid, binding.getHouseholdId()));
        return getStatus(deviceId, openid);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> createHousehold(HouseholdCreateDTO dto) {
        if (dto == null) {
            throw new RenException("household payload required");
        }
        String openid = normalizeOpenid(dto.getOpenid());
        String deviceId = normalizeDeviceId(dto.getDeviceId());
        if (StringUtils.isBlank(openid)) {
            throw new RenException("openid required");
        }

        HouseholdEntity household = householdDao.selectOne(
                new LambdaQueryWrapper<HouseholdEntity>()
                        .eq(HouseholdEntity::getOwnerOpenid, openid)
                        .last("LIMIT 1"));
        if (household == null) {
            household = new HouseholdEntity();
            household.setOwnerOpenid(openid);
            household.setHouseholdName(StringUtils.defaultIfBlank(
                    StringUtils.trimToEmpty(dto.getHouseholdName()),
                    "Puppy Household"));
            household.setStatus(HOUSEHOLD_STATUS_ACTIVE);
            householdDao.insert(household);
        } else {
            boolean changed = false;
            if (!HOUSEHOLD_STATUS_ACTIVE.equalsIgnoreCase(StringUtils.trimToEmpty(household.getStatus()))) {
                household.setStatus(HOUSEHOLD_STATUS_ACTIVE);
                changed = true;
            }
            if (StringUtils.isNotBlank(dto.getHouseholdName())) {
                household.setHouseholdName(StringUtils.trimToEmpty(dto.getHouseholdName()));
                changed = true;
            }
            if (changed) {
                householdDao.updateById(household);
            }
        }

        if (StringUtils.isNotBlank(deviceId)) {
            DeviceChildBindingEntity binding = findActiveBindingByDeviceId(deviceId);
            if (binding != null && openid.equals(normalizeOpenid(binding.getOpenid()))) {
                binding.setHouseholdId(household.getId());
                binding.setOwnerOpenid(openid);
                binding.setBindingStatus(BINDING_STATUS_BOUND);
                deviceChildBindingDao.updateById(binding);
            }
        }

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("householdId", household.getId());
        response.put("openid", openid);
        response.put("deviceId", deviceId);
        response.put("status", household.getStatus());
        return response;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public RobotInitializationStatusDTO initializeProfile(ProfileInitializeDTO dto) {
        if (dto == null) {
            throw new RenException("profile initialization payload required");
        }
        String openid = normalizeOpenid(dto.getOpenid());
        String deviceId = normalizeDeviceId(dto.getDeviceId());
        if (StringUtils.isBlank(openid)) {
            throw new RenException("openid required");
        }
        if (StringUtils.isBlank(deviceId)) {
            deviceId = resolveActiveDeviceId(openid);
        }
        childProfileService.initializeProfileStorage(openid);
        if (StringUtils.isNotBlank(deviceId)) {
            DeviceEntity device = findDevice(deviceId, deviceId);
            if (device != null && DeviceLifecycleStatus.from(device.getLifecycleStatus()) != DeviceLifecycleStatus.READY) {
                DeviceLifecycleStatus.transition(device, DeviceLifecycleStatus.PROFILE_INITIALIZED);
                deviceDao.updateById(device);
            }
        }
        return getStatus(deviceId, openid);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ChildProfileResponseDTO applyInitialConfiguration(ChildProfileUpsertDTO dto) {
        if (dto == null) {
            throw new RenException("profile payload required");
        }
        String openid = normalizeOpenid(dto.getOpenid());
        if (StringUtils.isBlank(openid)) {
            throw new RenException("openid required");
        }

        String deviceId = normalizeDeviceId(dto.getDeviceId());
        if (StringUtils.isBlank(deviceId)) {
            deviceId = resolveActiveDeviceId(openid);
            dto.setDeviceId(deviceId);
        }
        return childProfileService.upsertProfile(dto);
    }

    @Override
    public Map<String, Object> notifyRobotSync(RobotSyncNotifyDTO dto) {
        String deviceId = normalizeDeviceId(dto == null ? null : dto.getDeviceId());
        if (StringUtils.isBlank(deviceId)) {
            throw new RenException("deviceId required");
        }
        ChildProfileResponseDTO profile = childProfileService.getActiveProfile(deviceId);
        Map<String, Object> greetingResult = scheduleFirstAdoptionGreeting(deviceId, profile);

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("deviceId", deviceId);
        response.put("syncRequired", true);
        response.put("status", getStatus(deviceId, null).getStatus());
        response.put("firstAdoptionGreeting", greetingResult);
        return response;
    }

    @Override
    public RobotInitializationStatusDTO getStatus(String deviceId, String openid) {
        return buildStatus(normalizeDeviceId(deviceId), normalizeOpenid(openid));
    }

    @Override
    public ProfileSyncResponseDTO syncProfile(String deviceId) {
        String normalizedDeviceId = normalizeDeviceId(deviceId);
        if (StringUtils.isBlank(normalizedDeviceId)) {
            throw new RenException("deviceId required");
        }

        String openid = resolveActiveOpenid(normalizedDeviceId);
        ProfileSyncResponseDTO response = new ProfileSyncResponseDTO();
        response.setInitialization(getStatus(normalizedDeviceId, openid));
        response.setProfile(childProfileService.getActiveProfile(normalizedDeviceId));
        ChildLongTermMemoryResponseDTO memory = childProfileService.getActiveLongTermMemory(normalizedDeviceId);
        response.setLongTermMemory(memory);
        response.setCapabilities(defaultCapabilities());
        response.setConversationConfiguration(defaultConversationConfiguration());
        response.setDailyGreetingConfiguration(defaultDailyGreetingConfiguration());
        response.setSafetyConfiguration(defaultSafetyConfiguration());
        return response;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> legacyBindDevice(String openid, String deviceId) {
        DeviceLifecycleBindDTO dto = new DeviceLifecycleBindDTO();
        dto.setOpenid(openid);
        dto.setDeviceId(deviceId);
        RobotInitializationStatusDTO status = bindDevice(dto);

        Map<String, Object> response = new LinkedHashMap<>(childProfileService.getProfileByOpenid(normalizeOpenid(openid)));
        response.put("deviceId", normalizeDeviceId(deviceId));
        response.put("bound", status.getBound());
        response.put("initialization", status);
        return response;
    }

    private Map<String, Object> scheduleFirstAdoptionGreeting(String deviceId, ChildProfileResponseDTO profile) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("pushed", false);
        if (profile == null) {
            result.put("message", "profile missing; greeting skipped");
            return result;
        }

        String userName = StringUtils.trimToEmpty(profile.getNickname());
        String robotName = StringUtils.trimToEmpty(profile.getRobotNamePreference());
        if (StringUtils.isBlank(userName) || StringUtils.isBlank(robotName)) {
            result.put("message", "user_name or robot_name missing; greeting skipped");
            return result;
        }

        String text = FIRST_ADOPTION_GREETING_TEMPLATE
                .replace("{user_name}", userName)
                .replace("{robot_name}", robotName);

        result.put("scheduled", true);
        result.put("text", text);
        CompletableFuture.runAsync(() -> triggerFirstAdoptionGreetingWithRetry(
                deviceId, userName, robotName, text));
        return result;
    }

    private void triggerFirstAdoptionGreetingWithRetry(String deviceId, String userName, String robotName, String text) {
        int attempts = 8;
        for (int attempt = 1; attempt <= attempts; attempt++) {
            Map<String, Object> response = triggerFirstAdoptionGreeting(deviceId, userName, robotName, text);
            Object pushed = response.get("pushed");
            if (Boolean.TRUE.equals(pushed)) {
                return;
            }
            if (attempt < attempts) {
                try {
                    Thread.sleep(2000L);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return;
                }
            }
        }
    }

    private Map<String, Object> triggerFirstAdoptionGreeting(
            String deviceId, String userName, String robotName, String text) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("pushed", false);
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("device_id", deviceId);
        payload.put("user_name", userName);
        payload.put("robot_name", robotName);
        payload.put("text", text);

        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.set("x-debug-token", runtimeDebugToken);
            @SuppressWarnings("unchecked")
            Map<String, Object> runtimeResponse = restTemplate.postForObject(
                    StringUtils.removeEnd(runtimeDebugBaseUrl, "/") + "/debug/runtime/device/first-adoption-greeting",
                    new HttpEntity<>(payload, headers),
                    Map.class);
            if (runtimeResponse != null) {
                result.putAll(runtimeResponse);
            }
            result.put("text", text);
            return result;
        } catch (Exception e) {
            result.put("message", "runtime greeting push failed: " + e.getMessage());
            result.put("text", text);
            return result;
        }
    }

    private void applyDeviceMetadata(DeviceEntity device, String clientId, String firmwareVersion, String board,
            String model) {
        if (StringUtils.isNotBlank(clientId)) {
            device.setClientId(StringUtils.trimToEmpty(clientId));
        }
        if (StringUtils.isNotBlank(firmwareVersion)) {
            device.setAppVersion(StringUtils.trimToEmpty(firmwareVersion));
        }
        if (StringUtils.isNotBlank(board)) {
            device.setBoard(StringUtils.trimToEmpty(board));
        }
        if (StringUtils.isNotBlank(model)) {
            device.setModel(StringUtils.trimToEmpty(model));
        }
    }

    private void ensureRegisteredDevice(String deviceId) {
        DeviceEntity device = findDevice(deviceId, deviceId);
        if (device != null) {
            return;
        }
        Date now = new Date();
        device = new DeviceEntity();
        device.setId(deviceId);
        device.setMacAddress(deviceId);
        device.setAutoUpdate(1);
        device.setLastConnectedAt(now);
        device.setCreateDate(now);
        device.setUpdateDate(now);
        DeviceLifecycleStatus.transition(device, DeviceLifecycleStatus.REGISTERED);
        DeviceLifecycleStatus.transition(device, DeviceLifecycleStatus.UNBOUND);
        deviceDao.insert(device);
    }

    private RobotInitializationStatusDTO buildStatus(String deviceId, String openid) {
        String resolvedDeviceId = deviceId;
        String resolvedOpenid = openid;

        DeviceChildBindingEntity binding = null;
        if (StringUtils.isNotBlank(resolvedDeviceId)) {
            binding = findActiveBindingByDeviceId(resolvedDeviceId);
            if (binding != null && StringUtils.isBlank(resolvedOpenid)) {
                resolvedOpenid = normalizeOpenid(binding.getOpenid());
            }
        }
        if (binding == null && StringUtils.isNotBlank(resolvedOpenid)) {
            binding = findActiveBindingByOpenid(resolvedOpenid);
            if (binding != null && StringUtils.isBlank(resolvedDeviceId)) {
                resolvedDeviceId = normalizeDeviceId(binding.getDeviceId());
            }
        }

        DeviceEntity device = findDevice(resolvedDeviceId, resolvedDeviceId);
        ChildProfileEntity profile = findProfile(resolvedOpenid);

        boolean registered = device != null;
        boolean bound = binding != null && Integer.valueOf(1).equals(binding.getIsActive());
        boolean profileInitialized = profile != null;
        boolean profileCompleted = isProfileCompleted(profile);

        String status = determineStatus(device, registered, bound, profileInitialized, profileCompleted);
        RobotInitializationStatusDTO dto = new RobotInitializationStatusDTO();
        dto.setDeviceId(resolvedDeviceId);
        dto.setOpenid(resolvedOpenid);
        dto.setStatus(status);
        dto.setRegistered(registered);
        dto.setBound(bound);
        dto.setProfileInitialized(profileInitialized);
        dto.setProfileCompleted(profileCompleted);
        dto.setNextStep(determineNextStep(status));
        return dto;
    }

    private String determineStatus(DeviceEntity device, boolean registered, boolean bound, boolean profileInitialized,
            boolean profileCompleted) {
        if (device != null) {
            DeviceLifecycleStatus lifecycleStatus = DeviceLifecycleStatus.from(device.getLifecycleStatus());
            if (lifecycleStatus == DeviceLifecycleStatus.SUSPENDED
                    || lifecycleStatus == DeviceLifecycleStatus.RESETTING
                    || lifecycleStatus == DeviceLifecycleStatus.RETIRED) {
                return lifecycleStatus.name();
            }
        }
        if (!registered) {
            return DeviceLifecycleStatus.NEW.name();
        }
        if (!bound) {
            return DeviceLifecycleStatus.UNBOUND.name();
        }
        if (!profileInitialized) {
            return DeviceLifecycleStatus.BOUND.name();
        }
        if (!profileCompleted) {
            return DeviceLifecycleStatus.PROFILE_INITIALIZED.name();
        }
        return DeviceLifecycleStatus.READY.name();
    }

    private String determineNextStep(String status) {
        if (DeviceLifecycleStatus.NEW.name().equals(status)) {
            return "DEVICE_REGISTER";
        }
        if (DeviceLifecycleStatus.REGISTERED.name().equals(status)
                || DeviceLifecycleStatus.UNBOUND.name().equals(status)) {
            return "DEVICE_BIND";
        }
        if (DeviceLifecycleStatus.BOUND.name().equals(status)) {
            return "PROFILE_INITIALIZATION";
        }
        if (DeviceLifecycleStatus.PROFILE_INITIALIZED.name().equals(status)) {
            return "APPLY_INITIAL_CONFIGURATION";
        }
        return "NONE";
    }

    private DeviceEntity findDevice(String deviceId, String macAddress) {
        if (StringUtils.isNotBlank(deviceId)) {
            DeviceEntity byId = deviceDao.selectById(deviceId);
            if (byId != null) {
                return byId;
            }
        }
        if (StringUtils.isBlank(macAddress)) {
            return null;
        }
        return deviceDao.selectOne(
                new LambdaQueryWrapper<DeviceEntity>()
                        .eq(DeviceEntity::getMacAddress, macAddress)
                        .last("LIMIT 1"));
    }

    private ChildProfileEntity findProfile(String openid) {
        if (StringUtils.isBlank(openid)) {
            return null;
        }
        return childProfileDao.selectOne(
                new LambdaQueryWrapper<ChildProfileEntity>()
                        .eq(ChildProfileEntity::getOpenid, openid)
                        .last("LIMIT 1"));
    }

    private DeviceChildBindingEntity findActiveBindingByDeviceId(String deviceId) {
        if (StringUtils.isBlank(deviceId)) {
            return null;
        }
        return deviceChildBindingDao.selectOne(
                new LambdaQueryWrapper<DeviceChildBindingEntity>()
                        .eq(DeviceChildBindingEntity::getDeviceId, deviceId)
                        .eq(DeviceChildBindingEntity::getIsActive, 1)
                        .last("LIMIT 1"));
    }

    private DeviceChildBindingEntity findActiveBindingByOpenid(String openid) {
        if (StringUtils.isBlank(openid)) {
            return null;
        }
        return deviceChildBindingDao.selectOne(
                new LambdaQueryWrapper<DeviceChildBindingEntity>()
                        .eq(DeviceChildBindingEntity::getOpenid, openid)
                        .eq(DeviceChildBindingEntity::getIsActive, 1)
                        .last("LIMIT 1"));
    }

    private String resolveActiveOpenid(String deviceId) {
        DeviceChildBindingEntity binding = findActiveBindingByDeviceId(deviceId);
        return binding == null ? "" : normalizeOpenid(binding.getOpenid());
    }

    private String resolveActiveDeviceId(String openid) {
        DeviceChildBindingEntity binding = findActiveBindingByOpenid(openid);
        return binding == null ? "" : normalizeDeviceId(binding.getDeviceId());
    }

    private void deactivateActiveBindingsForOpenid(String openid) {
        List<DeviceChildBindingEntity> activeBindings = deviceChildBindingDao.selectList(
                new LambdaQueryWrapper<DeviceChildBindingEntity>()
                        .eq(DeviceChildBindingEntity::getOpenid, openid)
                        .eq(DeviceChildBindingEntity::getIsActive, 1));
        for (DeviceChildBindingEntity binding : activeBindings) {
            binding.setIsActive(0);
            binding.setBindingStatus(BINDING_STATUS_INACTIVE);
            deviceChildBindingDao.updateById(binding);
        }
    }

    private void deactivateActiveBindingsForDevice(String deviceId) {
        List<DeviceChildBindingEntity> activeBindings = deviceChildBindingDao.selectList(
                new LambdaQueryWrapper<DeviceChildBindingEntity>()
                        .eq(DeviceChildBindingEntity::getDeviceId, deviceId)
                        .eq(DeviceChildBindingEntity::getIsActive, 1));
        for (DeviceChildBindingEntity binding : activeBindings) {
            binding.setIsActive(0);
            binding.setBindingStatus(BINDING_STATUS_INACTIVE);
            deviceChildBindingDao.updateById(binding);
        }
    }

    private boolean isProfileCompleted(ChildProfileEntity profile) {
        if (profile == null) {
            return false;
        }
        String status = StringUtils.trimToEmpty(profile.getStatus());
        if (PROFILE_STATUS_COMPLETED.equalsIgnoreCase(status)) {
            return true;
        }
        if (PROFILE_STATUS_INITIALIZED.equalsIgnoreCase(status)) {
            return false;
        }
        return profile.getAge() != null && StringUtils.isNotBlank(profile.getNickname());
    }

    private Map<String, Object> defaultCapabilities() {
        Map<String, Object> capabilities = new LinkedHashMap<>();
        capabilities.put("deviceRegister", true);
        capabilities.put("deviceAuth", true);
        capabilities.put("deviceBind", true);
        capabilities.put("profileSync", true);
        capabilities.put("dailyGreeting", true);
        return capabilities;
    }

    private Map<String, Object> defaultConversationConfiguration() {
        Map<String, Object> config = new LinkedHashMap<>();
        config.put("conversationOpenness", true);
        config.put("interestAdapter", true);
        config.put("memoryRecall", true);
        return config;
    }

    private Map<String, Object> defaultDailyGreetingConfiguration() {
        Map<String, Object> config = new LinkedHashMap<>();
        config.put("enabled", true);
        config.put("trigger", "first_meaningful_interaction");
        return config;
    }

    private Map<String, Object> defaultSafetyConfiguration() {
        Map<String, Object> config = new LinkedHashMap<>();
        config.put("safetyFirst", true);
        config.put("skipProactiveGreetingOnCriticalInput", true);
        return config;
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (StringUtils.isNotBlank(value)) {
                return value;
            }
        }
        return "";
    }

    private String normalizeOpenid(String value) {
        return StringUtils.trimToEmpty(value);
    }

    private String normalizeDeviceId(String value) {
        return StringUtils.trimToEmpty(value).toLowerCase();
    }
}
