package xiaozhi.modules.device.entity;

import java.util.Date;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

import lombok.Data;

/**
 * Tracks an OTA request independently from the version currently running on a device.
 */
@Data
@TableName("ai_device_ota_job")
public class DeviceOtaJobEntity {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String deviceId;
    private String fromVersion;
    private String targetVersion;
    private String firmwareUrl;
    private String status;
    private Date requestedAt;
    private Date acknowledgedAt;
    private Date completedAt;
    private String lastReportedVersion;
    private String failureReason;
    private Date updateDate;
    private Date createDate;
}
