package xiaozhi.modules.childprofile.service.impl;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import xiaozhi.common.exception.RenException;
import xiaozhi.modules.childprofile.dao.ChildLongTermMemoryDao;
import xiaozhi.modules.childprofile.dao.ChildDailyActivitySummaryDao;
import xiaozhi.modules.childprofile.dao.ChildProfileDao;
import xiaozhi.modules.childprofile.dao.DeviceChildBindingDao;
import xiaozhi.modules.childprofile.dto.ChildLongTermMemoryResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileResponseDTO;
import xiaozhi.modules.childprofile.dto.ChildProfileUpsertDTO;
import xiaozhi.modules.childprofile.dto.DailyActivitySummaryResponseDTO;
import xiaozhi.modules.childprofile.entity.ChildDailyActivitySummaryEntity;
import xiaozhi.modules.childprofile.entity.ChildLongTermMemoryEntity;
import xiaozhi.modules.childprofile.entity.ChildProfileEntity;
import xiaozhi.modules.childprofile.entity.DeviceChildBindingEntity;
import xiaozhi.modules.childprofile.service.ChildProfileService;
import xiaozhi.modules.childprofile.support.InterestKeyNormalizer;

@Service
public class ChildProfileServiceImpl implements ChildProfileService {

    private static final int LONG_TERM_MEMORY_PROFILE_VERSION = 1;
    private static final int MAX_DAILY_ACTIVITY_HISTORY_DAYS = 14;

    private final ChildDailyActivitySummaryDao childDailyActivitySummaryDao;
    private final ChildLongTermMemoryDao childLongTermMemoryDao;
    private final ChildProfileDao childProfileDao;
    private final DeviceChildBindingDao deviceChildBindingDao;
    private final ObjectMapper objectMapper;

    public ChildProfileServiceImpl(
            ChildDailyActivitySummaryDao childDailyActivitySummaryDao,
            ChildLongTermMemoryDao childLongTermMemoryDao,
            ChildProfileDao childProfileDao,
            DeviceChildBindingDao deviceChildBindingDao,
            ObjectMapper objectMapper) {
        this.childDailyActivitySummaryDao = childDailyActivitySummaryDao;
        this.childLongTermMemoryDao = childLongTermMemoryDao;
        this.childProfileDao = childProfileDao;
        this.deviceChildBindingDao = deviceChildBindingDao;
        this.objectMapper = objectMapper;
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
        String normalizedRobotNamePreference = normalizeOptionalName(dto.getRobotNamePreference());
        List<String> normalizedInterests = normalizeLimitedStringList(dto.getInterests(), 3);
        normalizedInterests = InterestKeyNormalizer.normalizeInterestList(normalizedInterests);

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
            profileEntity.setInterestsJson(writeStringListJson(normalizedInterests));
            childProfileDao.insert(profileEntity);
        } else {
            profileEntity.setNickname(normalizedNickname);
            profileEntity.setAge(age);
            profileEntity.setAgeGroup(ageGroup);
            profileEntity.setInterestsJson(writeStringListJson(normalizedInterests));
            childProfileDao.updateById(profileEntity);
        }

        upsertLongTermMemory(
                normalizedOpenid,
                normalizedNickname,
                normalizedRobotNamePreference,
                age,
                ageGroup,
                normalizedInterests);

        return new ChildProfileResponseDTO(
                normalizedNickname,
                age,
                ageGroup,
                normalizedRobotNamePreference,
                normalizedInterests);
    }

    @Override
    public ChildProfileResponseDTO getActiveProfile(String deviceId) {
        String normalizedDeviceId = normalizeDeviceId(deviceId);
        String openid = resolveActiveOpenid(normalizedDeviceId);
        if (StringUtils.isBlank(openid)) {
            return null;
        }

        ChildProfileEntity profileEntity = childProfileDao.selectOne(
                new LambdaQueryWrapper<ChildProfileEntity>()
                        .eq(ChildProfileEntity::getOpenid, openid)
                        .last("LIMIT 1"));
        if (profileEntity == null) {
            return null;
        }

        return buildProfileResponse(profileEntity);
    }

    @Override
    public Map<String, Object> getProfileByOpenid(String openid) {
        String normalizedOpenid = normalizeOpenid(openid);
        ChildProfileEntity profileEntity = childProfileDao.selectOne(
                new LambdaQueryWrapper<ChildProfileEntity>()
                        .eq(ChildProfileEntity::getOpenid, normalizedOpenid)
                        .last("LIMIT 1"));

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("openid", normalizedOpenid);
        response.put("deviceId", resolveActiveDeviceId(normalizedOpenid));
        response.put("profileCompleted", profileEntity != null);
        if (profileEntity == null) {
            response.put("nickname", "");
            response.put("age", null);
            response.put("ageGroup", "");
            response.put("robotNamePreference", "");
            response.put("interests", new ArrayList<String>());
            return response;
        }

        response.put("nickname", StringUtils.trimToEmpty(profileEntity.getNickname()));
        response.put("age", profileEntity.getAge());
        response.put("ageGroup", StringUtils.trimToEmpty(profileEntity.getAgeGroup()));
        response.put("robotNamePreference", buildRobotNamePreferenceForOpenid(normalizedOpenid));
        response.put("interests", InterestKeyNormalizer.normalizeInterestList(parseStringListJson(profileEntity.getInterestsJson())));
        return response;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> bindDevice(String openid, String deviceId) {
        String normalizedOpenid = normalizeOpenid(openid);
        String normalizedDeviceId = normalizeDeviceId(deviceId);
        if (StringUtils.isBlank(normalizedOpenid)) {
            throw new RenException("openid required");
        }
        if (StringUtils.isBlank(normalizedDeviceId)) {
            throw new RenException("deviceId required");
        }

        deactivateActiveBindingsForOpenid(normalizedOpenid);
        deactivateActiveBindingsForDevice(normalizedDeviceId);

        DeviceChildBindingEntity binding = deviceChildBindingDao.selectOne(
                new LambdaQueryWrapper<DeviceChildBindingEntity>()
                        .eq(DeviceChildBindingEntity::getDeviceId, normalizedDeviceId)
                        .last("LIMIT 1"));
        if (binding == null) {
            binding = new DeviceChildBindingEntity();
            binding.setDeviceId(normalizedDeviceId);
            binding.setOpenid(normalizedOpenid);
            binding.setIsActive(1);
            deviceChildBindingDao.insert(binding);
        } else {
            binding.setOpenid(normalizedOpenid);
            binding.setIsActive(1);
            deviceChildBindingDao.updateById(binding);
        }

        Map<String, Object> response = getProfileByOpenid(normalizedOpenid);
        response.put("deviceId", normalizedDeviceId);
        response.put("bound", true);
        return response;
    }

    private void deactivateActiveBindingsForOpenid(String openid) {
        List<DeviceChildBindingEntity> activeBindings = deviceChildBindingDao.selectList(
                new LambdaQueryWrapper<DeviceChildBindingEntity>()
                        .eq(DeviceChildBindingEntity::getIsActive, 1)
                        .eq(DeviceChildBindingEntity::getOpenid, openid));
        for (DeviceChildBindingEntity binding : activeBindings) {
            binding.setIsActive(0);
            deviceChildBindingDao.updateById(binding);
        }
    }

    private void deactivateActiveBindingsForDevice(String deviceId) {
        List<DeviceChildBindingEntity> activeBindings = deviceChildBindingDao.selectList(
                new LambdaQueryWrapper<DeviceChildBindingEntity>()
                        .eq(DeviceChildBindingEntity::getIsActive, 1)
                        .eq(DeviceChildBindingEntity::getDeviceId, deviceId));
        for (DeviceChildBindingEntity binding : activeBindings) {
            binding.setIsActive(0);
            deviceChildBindingDao.updateById(binding);
        }
    }

    @Override
    public ChildLongTermMemoryResponseDTO getActiveLongTermMemory(String deviceId) {
        String normalizedDeviceId = normalizeDeviceId(deviceId);
        String openid = resolveActiveOpenid(normalizedDeviceId);
        if (StringUtils.isBlank(openid)) {
            return null;
        }

        ChildLongTermMemoryEntity memoryEntity = childLongTermMemoryDao.selectOne(
                new LambdaQueryWrapper<ChildLongTermMemoryEntity>()
                        .eq(ChildLongTermMemoryEntity::getOpenid, openid)
                        .last("LIMIT 1"));
        if (memoryEntity == null) {
            return null;
        }
        return buildLongTermMemoryResponse(memoryEntity);
    }

    @Override
    public DailyActivitySummaryResponseDTO getTodayCompanionSummary(String deviceId) {
        String normalizedDeviceId = normalizeDeviceId(deviceId);
        LocalDate today = LocalDate.now();
        ChildDailyActivitySummaryEntity summaryEntity = childDailyActivitySummaryDao.selectOne(
                new LambdaQueryWrapper<ChildDailyActivitySummaryEntity>()
                        .eq(ChildDailyActivitySummaryEntity::getDeviceId, normalizedDeviceId)
                        .eq(ChildDailyActivitySummaryEntity::getSummaryDate, today)
                        .last("LIMIT 1"));
        if (summaryEntity == null) {
            return emptyDailyActivitySummary(today);
        }
        return buildDailyActivitySummaryResponse(summaryEntity);
    }

    @Override
    public List<DailyActivitySummaryResponseDTO> getTodayCompanionHistory(String deviceId, Integer days) {
        String normalizedDeviceId = normalizeDeviceId(deviceId);
        LocalDate today = LocalDate.now();
        int normalizedDays = MAX_DAILY_ACTIVITY_HISTORY_DAYS;
        LocalDate startDate = today.minusDays(normalizedDays - 1L);
        if (days != null && days > 0) {
            normalizedDays = Math.min(days, MAX_DAILY_ACTIVITY_HISTORY_DAYS);
            startDate = today.minusDays(normalizedDays - 1L);
        }

        List<ChildDailyActivitySummaryEntity> summaryEntities = childDailyActivitySummaryDao.selectList(
                new LambdaQueryWrapper<ChildDailyActivitySummaryEntity>()
                        .eq(ChildDailyActivitySummaryEntity::getDeviceId, normalizedDeviceId)
                        .ge(ChildDailyActivitySummaryEntity::getSummaryDate, startDate)
                        .le(ChildDailyActivitySummaryEntity::getSummaryDate, today)
                        .orderByDesc(ChildDailyActivitySummaryEntity::getSummaryDate));

        Map<LocalDate, ChildDailyActivitySummaryEntity> summariesByDate = new LinkedHashMap<>();
        for (ChildDailyActivitySummaryEntity summaryEntity : summaryEntities) {
            summariesByDate.put(summaryEntity.getSummaryDate(), summaryEntity);
        }

        List<DailyActivitySummaryResponseDTO> summaries = new ArrayList<>();
        for (int offset = 0; offset < normalizedDays; offset++) {
            LocalDate date = today.minusDays(offset);
            ChildDailyActivitySummaryEntity summaryEntity = summariesByDate.get(date);
            summaries.add(summaryEntity == null
                    ? emptyDailyActivitySummary(date)
                    : buildDailyActivitySummaryResponse(summaryEntity));
        }
        return summaries;
    }

    private String resolveActiveOpenid(String deviceId) {
        if (StringUtils.isBlank(deviceId)) {
            return "";
        }
        DeviceChildBindingEntity binding = deviceChildBindingDao.selectOne(
                new LambdaQueryWrapper<DeviceChildBindingEntity>()
                        .eq(DeviceChildBindingEntity::getDeviceId, deviceId)
                        .eq(DeviceChildBindingEntity::getIsActive, 1)
                        .last("LIMIT 1"));
        return binding == null ? "" : normalizeOpenid(binding.getOpenid());
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

    private ChildProfileResponseDTO buildProfileResponse(ChildProfileEntity profileEntity) {
        return new ChildProfileResponseDTO(
                StringUtils.trimToEmpty(profileEntity.getNickname()),
                profileEntity.getAge(),
                StringUtils.trimToEmpty(profileEntity.getAgeGroup()),
                buildRobotNamePreferenceForOpenid(profileEntity.getOpenid()),
                InterestKeyNormalizer.normalizeInterestList(parseStringListJson(profileEntity.getInterestsJson())));
    }

    private DailyActivitySummaryResponseDTO buildDailyActivitySummaryResponse(
            ChildDailyActivitySummaryEntity summaryEntity) {
        return new DailyActivitySummaryResponseDTO(
                String.valueOf(summaryEntity.getSummaryDate()),
                safeInteger(summaryEntity.getTotalDuration()),
                safeInteger(summaryEntity.getSessionCount()),
                parseIntegerMap(summaryEntity.getActivityDistributionJson()),
                parseIntegerMap(summaryEntity.getSceneDistributionJson()),
                StringUtils.defaultIfBlank(summaryEntity.getPrimaryActivity(), "other"),
                StringUtils.defaultIfBlank(summaryEntity.getPrimaryScene(), "relationship_building"),
                parseBooleanMap(summaryEntity.getActivePeriodsJson()),
                parseObjectMap(summaryEntity.getHighlightMetadataJson()));
    }

    private void upsertLongTermMemory(
            String openid,
            String nickname,
            String robotNamePreference,
            Integer age,
            String ageGroup,
            List<String> interests) {
        ChildLongTermMemoryEntity memoryEntity = childLongTermMemoryDao.selectOne(
                new LambdaQueryWrapper<ChildLongTermMemoryEntity>()
                        .eq(ChildLongTermMemoryEntity::getOpenid, openid)
                        .last("LIMIT 1"));

        Map<String, Object> profile = memoryEntity == null
                ? new LinkedHashMap<>()
                : parseProfileJson(memoryEntity.getProfileJson());
        profile.put("nickname_preference", nickname);
        profile.put("age", age);
        profile.put("age_group", ageGroup);
        profile.put("robot_name_preference", robotNamePreference);
        profile.put("interests", interests);
        ensureProfileDefaults(profile);

        if (memoryEntity == null) {
            memoryEntity = new ChildLongTermMemoryEntity();
            memoryEntity.setOpenid(openid);
        }

        memoryEntity.setNicknamePreference(nickname);
        memoryEntity.setAge(age);
        memoryEntity.setAgeGroup(ageGroup);
        memoryEntity.setProfileVersion(LONG_TERM_MEMORY_PROFILE_VERSION);
        memoryEntity.setProfileJson(writeProfileJson(profile));

        if (memoryEntity.getId() == null) {
            childLongTermMemoryDao.insert(memoryEntity);
        } else {
            childLongTermMemoryDao.updateById(memoryEntity);
        }
    }

    private DailyActivitySummaryResponseDTO emptyDailyActivitySummary(LocalDate date) {
        Map<String, Boolean> activePeriods = new LinkedHashMap<>();
        activePeriods.put("morning", false);
        activePeriods.put("afternoon", false);
        activePeriods.put("evening", false);
        Map<String, Object> highlightMetadata = new LinkedHashMap<>();
        highlightMetadata.put("primary_activity", "other");
        highlightMetadata.put("primary_scene", "relationship_building");
        highlightMetadata.put("interaction_style", "companionship");
        return new DailyActivitySummaryResponseDTO(
                String.valueOf(date),
                0,
                0,
                new LinkedHashMap<>(),
                new LinkedHashMap<>(),
                "other",
                "relationship_building",
                activePeriods,
                highlightMetadata);
    }

    private Integer safeInteger(Integer value) {
        return value == null ? 0 : value;
    }

    private Map<String, Integer> parseIntegerMap(String json) {
        if (StringUtils.isBlank(json)) {
            return new LinkedHashMap<>();
        }
        try {
            Map<String, Object> raw = objectMapper.readValue(json, new TypeReference<Map<String, Object>>() {});
            Map<String, Integer> out = new LinkedHashMap<>();
            for (Map.Entry<String, Object> entry : raw.entrySet()) {
                Object value = entry.getValue();
                int numberValue = value instanceof Number
                        ? ((Number) value).intValue()
                        : Integer.parseInt(String.valueOf(value));
                out.put(entry.getKey(), numberValue);
            }
            return out;
        } catch (Exception e) {
            return new LinkedHashMap<>();
        }
    }

    private Map<String, Boolean> parseBooleanMap(String json) {
        Map<String, Boolean> defaults = new LinkedHashMap<>();
        defaults.put("morning", false);
        defaults.put("afternoon", false);
        defaults.put("evening", false);
        if (StringUtils.isBlank(json)) {
            return defaults;
        }
        try {
            Map<String, Object> raw = objectMapper.readValue(json, new TypeReference<Map<String, Object>>() {});
            for (Map.Entry<String, Object> entry : raw.entrySet()) {
                defaults.put(entry.getKey(), Boolean.parseBoolean(String.valueOf(entry.getValue())));
            }
            return defaults;
        } catch (Exception e) {
            return defaults;
        }
    }

    private Map<String, Object> parseObjectMap(String json) {
        if (StringUtils.isBlank(json)) {
            return new LinkedHashMap<>();
        }
        try {
            return objectMapper.readValue(json, new TypeReference<Map<String, Object>>() {});
        } catch (Exception e) {
            return new LinkedHashMap<>();
        }
    }

    private ChildLongTermMemoryResponseDTO buildLongTermMemoryResponse(ChildLongTermMemoryEntity entity) {
        Map<String, Object> profile = parseProfileJson(entity.getProfileJson());
        ensureProfileDefaults(profile);
        return new ChildLongTermMemoryResponseDTO(
                entity.getNicknamePreference(),
                entity.getAge(),
                entity.getAgeGroup(),
                normalizeString(profile.get("robot_name_preference")),
                InterestKeyNormalizer.normalizeInterestList(normalizeStringList(profile.get("interests"))),
                normalizeStringList(profile.get("favorite_dog_types")),
                normalizeStringList(profile.get("desired_activities")),
                normalizeStringList(profile.get("parent_goals")),
                normalizeObjectMap(profile.get("extra_attributes")),
                entity.getProfileVersion(),
                entity.getUpdatedAt());
    }

    private String buildRobotNamePreferenceForOpenid(String openid) {
        if (StringUtils.isBlank(openid)) {
            return "";
        }
        ChildLongTermMemoryEntity memoryEntity = childLongTermMemoryDao.selectOne(
                new LambdaQueryWrapper<ChildLongTermMemoryEntity>()
                        .eq(ChildLongTermMemoryEntity::getOpenid, openid)
                        .last("LIMIT 1"));
        if (memoryEntity == null) {
            return "";
        }
        Map<String, Object> profile = parseProfileJson(memoryEntity.getProfileJson());
        ensureProfileDefaults(profile);
        return normalizeString(profile.get("robot_name_preference"));
    }

    private Map<String, Object> parseProfileJson(String profileJson) {
        if (StringUtils.isBlank(profileJson)) {
            return new LinkedHashMap<>();
        }
        try {
            return objectMapper.readValue(profileJson, new TypeReference<LinkedHashMap<String, Object>>() {
            });
        } catch (Exception e) {
            throw new RenException("child long term memory json invalid");
        }
    }

    private List<String> parseStringListJson(String rawJson) {
        if (StringUtils.isBlank(rawJson)) {
            return new ArrayList<>();
        }
        try {
            List<String> parsed = objectMapper.readValue(rawJson, new TypeReference<List<String>>() {
            });
            return normalizeStringList(parsed);
        } catch (Exception e) {
            throw new RenException("child profile interests json invalid");
        }
    }

    private String writeProfileJson(Map<String, Object> profile) {
        try {
            return objectMapper.writeValueAsString(profile);
        } catch (Exception e) {
            throw new RenException("child long term memory json serialize failed");
        }
    }

    private String writeStringListJson(List<String> values) {
        try {
            return objectMapper.writeValueAsString(values == null ? new ArrayList<>() : values);
        } catch (Exception e) {
            throw new RenException("child profile interests json serialize failed");
        }
    }

    private void ensureProfileDefaults(Map<String, Object> profile) {
        profile.putIfAbsent("robot_name_preference", "");
        profile.put("interests", InterestKeyNormalizer.normalizeInterestList(normalizeStringList(profile.get("interests"))));
        profile.put("favorite_dog_types", normalizeStringList(profile.get("favorite_dog_types")));
        profile.put("desired_activities", normalizeStringList(profile.get("desired_activities")));
        profile.put("parent_goals", normalizeStringList(profile.get("parent_goals")));
        profile.put("extra_attributes", normalizeObjectMap(profile.get("extra_attributes")));
    }

    private String normalizeString(Object value) {
        return StringUtils.trimToEmpty(value == null ? null : String.valueOf(value));
    }

    private String normalizeOptionalName(String value) {
        String normalized = normalizeString(value);
        if (normalized.length() > 32) {
            throw new RenException("robotNamePreference too long");
        }
        return normalized;
    }

    private List<String> normalizeStringList(Object value) {
        List<String> items = new ArrayList<>();
        if (value instanceof Iterable<?> iterable) {
            for (Object item : iterable) {
                String normalized = normalizeString(item);
                if (StringUtils.isNotBlank(normalized)) {
                    items.add(normalized);
                }
            }
        }
        return items;
    }

    private List<String> normalizeLimitedStringList(Object value, int maxSize) {
        List<String> normalized = normalizeStringList(value);
        if (normalized.size() > maxSize) {
            throw new RenException("interests can include at most " + maxSize + " items");
        }
        return normalized;
    }

    private Map<String, Object> normalizeObjectMap(Object value) {
        if (value instanceof Map<?, ?> rawMap) {
            Map<String, Object> normalized = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : rawMap.entrySet()) {
                String key = normalizeString(entry.getKey());
                if (StringUtils.isBlank(key)) {
                    continue;
                }
                normalized.put(key, entry.getValue());
            }
            return normalized;
        }
        return new LinkedHashMap<>();
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
