package xiaozhi.modules.agent.dao;

import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import xiaozhi.modules.agent.entity.AgentModeEntity;

@Mapper
public interface AgentModeDao extends BaseMapper<AgentModeEntity> {

    List<AgentModeEntity> selectByAgentId(@Param("agentId") String agentId);

    AgentModeEntity selectDefaultByAgentId(@Param("agentId") String agentId);

    void clearDefaultByAgentId(@Param("agentId") String agentId);

    void deleteByAgentId(@Param("agentId") String agentId);
}

