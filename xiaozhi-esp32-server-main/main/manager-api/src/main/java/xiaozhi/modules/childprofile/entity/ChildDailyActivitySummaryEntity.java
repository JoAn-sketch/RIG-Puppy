package xiaozhi.modules.childprofile.entity;

import java.time.LocalDate;
import java.util.Date;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

import lombok.Data;

@Data
@TableName("child_daily_activity_summary")
public class ChildDailyActivitySummaryEntity {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String deviceId;

    private LocalDate summaryDate;

    private Integer totalDuration;

    private Integer totalDurationSeconds;

    private Integer sessionCount;

    private String activityDistributionJson;

    private String sceneDistributionJson;

    private String primaryActivity;

    private String primaryScene;

    private String activePeriodsJson;

    private String highlightMetadataJson;

    private String sessionStateJson;

    private Integer finalized;

    @TableField(fill = FieldFill.INSERT)
    private Date createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private Date updatedAt;
}
