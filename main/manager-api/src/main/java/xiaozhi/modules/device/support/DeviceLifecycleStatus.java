package xiaozhi.modules.device.support;

import java.util.Date;
import java.util.EnumMap;
import java.util.EnumSet;
import java.util.Map;
import java.util.Set;

import org.apache.commons.lang3.StringUtils;

import xiaozhi.common.exception.RenException;
import xiaozhi.modules.device.entity.DeviceEntity;

public enum DeviceLifecycleStatus {
    NEW,
    REGISTERED,
    UNBOUND,
    BOUND,
    PROFILE_INITIALIZED,
    READY,
    SUSPENDED,
    RESETTING,
    RETIRED;

    private static final Map<DeviceLifecycleStatus, Set<DeviceLifecycleStatus>> ALLOWED_TRANSITIONS =
            new EnumMap<>(DeviceLifecycleStatus.class);

    static {
        ALLOWED_TRANSITIONS.put(NEW, EnumSet.of(REGISTERED));
        ALLOWED_TRANSITIONS.put(REGISTERED, EnumSet.of(UNBOUND));
        ALLOWED_TRANSITIONS.put(UNBOUND, EnumSet.of(BOUND));
        ALLOWED_TRANSITIONS.put(BOUND, EnumSet.of(PROFILE_INITIALIZED, UNBOUND));
        ALLOWED_TRANSITIONS.put(PROFILE_INITIALIZED, EnumSet.of(READY, UNBOUND));
        ALLOWED_TRANSITIONS.put(READY, EnumSet.of(SUSPENDED, RESETTING, RETIRED));
        ALLOWED_TRANSITIONS.put(SUSPENDED, EnumSet.of(READY, UNBOUND));
        ALLOWED_TRANSITIONS.put(RESETTING, EnumSet.of(UNBOUND));
        ALLOWED_TRANSITIONS.put(RETIRED, EnumSet.noneOf(DeviceLifecycleStatus.class));
    }

    public static DeviceLifecycleStatus from(String value) {
        String normalized = StringUtils.trimToEmpty(value);
        if (StringUtils.isBlank(normalized)) {
            return NEW;
        }
        if ("DISABLED".equalsIgnoreCase(normalized)) {
            return SUSPENDED;
        }
        for (DeviceLifecycleStatus status : values()) {
            if (status.name().equalsIgnoreCase(normalized)) {
                return status;
            }
        }
        throw new RenException("unknown device lifecycle status: " + value);
    }

    public static boolean canTransition(DeviceLifecycleStatus from, DeviceLifecycleStatus to) {
        if (from == null) {
            from = NEW;
        }
        if (to == null || from == to) {
            return true;
        }
        return ALLOWED_TRANSITIONS.getOrDefault(from, Set.of()).contains(to);
    }

    public static void transition(DeviceEntity device, DeviceLifecycleStatus target) {
        if (device == null || target == null) {
            return;
        }
        DeviceLifecycleStatus current = from(device.getLifecycleStatus());
        if (current == target) {
            stamp(device, target);
            return;
        }
        if (!canTransition(current, target)) {
            throw new RenException("invalid device lifecycle transition: " + current + " -> " + target);
        }
        device.setLifecycleStatus(target.name());
        stamp(device, target);
    }

    public static boolean deniesAuthentication(String value) {
        DeviceLifecycleStatus status = from(value);
        return status == NEW
                || status == REGISTERED
                || status == UNBOUND
                || status == SUSPENDED
                || status == RESETTING
                || status == RETIRED;
    }

    private static void stamp(DeviceEntity device, DeviceLifecycleStatus status) {
        Date now = new Date();
        if (status == REGISTERED && device.getRegisteredAt() == null) {
            device.setRegisteredAt(now);
        } else if (status == BOUND && device.getBoundAt() == null) {
            device.setBoundAt(now);
        } else if (status == PROFILE_INITIALIZED && device.getProfileInitializedAt() == null) {
            device.setProfileInitializedAt(now);
        } else if (status == READY && device.getReadyAt() == null) {
            device.setReadyAt(now);
        } else if (status == SUSPENDED) {
            device.setSuspendedAt(now);
        } else if (status == RESETTING) {
            device.setResettingAt(now);
        } else if (status == RETIRED) {
            device.setRetiredAt(now);
        }
    }
}
