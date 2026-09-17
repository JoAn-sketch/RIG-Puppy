package xiaozhi.modules.childprofile.dto;

import java.io.Serializable;
import java.util.Map;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "每日陪伴活动聚合摘要")
public class DailyActivitySummaryResponseDTO implements Serializable {

    @Schema(description = "日期")
    private String date;

    @Schema(description = "总陪伴时长，分钟")
    private Integer totalDuration;

    @Schema(description = "互动 session 数")
    private Integer sessionCount;

    @Schema(description = "活动分布")
    private Map<String, Integer> activityDistribution;

    @Schema(description = "场景分布")
    private Map<String, Integer> sceneDistribution;

    @Schema(description = "主要活动")
    private String primaryActivity;

    @Schema(description = "主要场景")
    private String primaryScene;

    @Schema(description = "活跃时间段")
    private Map<String, Boolean> activePeriods;

    @Schema(description = "高光生成元数据，不包含对话原文")
    private Map<String, Object> highlightMetadata;
}
