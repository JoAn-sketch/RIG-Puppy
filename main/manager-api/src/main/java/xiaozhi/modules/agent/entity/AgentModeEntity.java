package xiaozhi.modules.agent.entity;

import java.util.Date;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@TableName("ai_agent_mode")
@Schema(description = "智能体对话模式")
public class AgentModeEntity {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    @Schema(description = "智能体ID")
    private String agentId;

    @Schema(description = "模式名称")
    private String modeName;

    @Schema(description = "模式代码")
    private String modeCode;

    @Schema(description = "系统提示词")
    private String systemPrompt;

    @Schema(description = "是否默认 0否 1是")
    private Integer isDefault;

    @Schema(description = "排序")
    private Integer sort;

    @Schema(description = "创建者")
    private Long creator;

    @Schema(description = "创建时间")
    private Date createDate;

    @Schema(description = "更新者")
    private Long updater;

    @Schema(description = "更新时间")
    private Date updateDate;
}

