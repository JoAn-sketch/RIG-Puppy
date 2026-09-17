package xiaozhi.modules.agent.controller;

import java.util.List;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.AllArgsConstructor;
import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.springframework.web.bind.annotation.*;
import xiaozhi.common.utils.Result;
import xiaozhi.common.user.UserDetail;
import xiaozhi.modules.agent.entity.AgentModeEntity;
import xiaozhi.modules.agent.service.AgentModeService;
import xiaozhi.modules.agent.service.AgentService;
import xiaozhi.modules.security.user.SecurityUser;

@Tag(name = "智能体对话模式")
@AllArgsConstructor
@RestController
@RequestMapping("/agent/{agentId}/modes")
public class AgentModeController {

    private final AgentModeService agentModeService;
    private final AgentService agentService;

    @GetMapping
    @Operation(summary = "获取模式列表")
    @RequiresPermissions("sys:role:normal")
    public Result<List<AgentModeEntity>> list(@PathVariable String agentId) {
        checkPermission(agentId);
        return new Result<List<AgentModeEntity>>().ok(agentModeService.listByAgentId(agentId));
    }

    @PostMapping
    @Operation(summary = "新增模式")
    @RequiresPermissions("sys:role:normal")
    public Result<Void> save(@PathVariable String agentId, @RequestBody @Valid AgentModeEntity entity) {
        checkPermission(agentId);
        entity.setAgentId(agentId);
        agentModeService.saveMode(entity);
        return new Result<>();
    }

    @PutMapping("/{id}")
    @Operation(summary = "修改模式")
    @RequiresPermissions("sys:role:normal")
    public Result<Void> update(@PathVariable String agentId, @PathVariable String id,
                               @RequestBody AgentModeEntity entity) {
        checkPermission(agentId);
        entity.setId(id);
        entity.setAgentId(agentId);
        agentModeService.updateMode(entity);
        return new Result<>();
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "删除模式")
    @RequiresPermissions("sys:role:normal")
    public Result<Void> delete(@PathVariable String agentId, @PathVariable String id) {
        checkPermission(agentId);
        agentModeService.deleteMode(id);
        return new Result<>();
    }

    @PutMapping("/{id}/default")
    @Operation(summary = "设为默认模式")
    @RequiresPermissions("sys:role:normal")
    public Result<Void> setDefault(@PathVariable String agentId, @PathVariable String id) {
        checkPermission(agentId);
        agentModeService.setDefault(agentId, id);
        return new Result<>();
    }

    private void checkPermission(String agentId) {
        UserDetail user = SecurityUser.getUser();
        if (!agentService.checkAgentPermission(agentId, user.getId())) {
            throw new RuntimeException("无权限操作该智能体");
        }
    }
}

