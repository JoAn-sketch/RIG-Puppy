package xiaozhi.modules.agent.service;

import java.util.List;
import xiaozhi.common.service.BaseService;
import xiaozhi.modules.agent.entity.AgentModeEntity;

public interface AgentModeService extends BaseService<AgentModeEntity> {

    List<AgentModeEntity> listByAgentId(String agentId);

    AgentModeEntity getDefaultMode(String agentId);

    void saveMode(AgentModeEntity entity);

    void updateMode(AgentModeEntity entity);

    void deleteMode(String id);

    void setDefault(String agentId, String modeId);

    void deleteByAgentId(String agentId);
}

