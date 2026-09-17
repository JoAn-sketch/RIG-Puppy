package xiaozhi.modules.agent.service.impl;

import java.util.Date;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import lombok.AllArgsConstructor;
import xiaozhi.common.service.impl.BaseServiceImpl;
import xiaozhi.modules.agent.dao.AgentModeDao;
import xiaozhi.modules.agent.entity.AgentModeEntity;
import xiaozhi.modules.agent.service.AgentModeService;

@Service
@AllArgsConstructor
public class AgentModeServiceImpl extends BaseServiceImpl<AgentModeDao, AgentModeEntity> implements AgentModeService {

    @Override
    public List<AgentModeEntity> listByAgentId(String agentId) {
        return baseDao.selectByAgentId(agentId);
    }

    @Override
    public AgentModeEntity getDefaultMode(String agentId) {
        return baseDao.selectDefaultByAgentId(agentId);
    }

    @Override
    public void saveMode(AgentModeEntity entity) {
        entity.setId(UUID.randomUUID().toString().replace("-", ""));
        entity.setCreateDate(new Date());
        entity.setUpdateDate(new Date());
        if (entity.getIsDefault() == null) entity.setIsDefault(0);
        if (entity.getSort() == null) entity.setSort(0);
        if (entity.getIsDefault() == 1) {
            baseDao.clearDefaultByAgentId(entity.getAgentId());
        }
        baseDao.insert(entity);
    }

    @Override
    public void updateMode(AgentModeEntity entity) {
        entity.setUpdateDate(new Date());
        if (entity.getIsDefault() != null && entity.getIsDefault() == 1) {
            baseDao.clearDefaultByAgentId(entity.getAgentId());
        }
        baseDao.updateById(entity);
    }

    @Override
    public void deleteMode(String id) {
        baseDao.deleteById(id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void setDefault(String agentId, String modeId) {
        baseDao.clearDefaultByAgentId(agentId);
        AgentModeEntity entity = baseDao.selectById(modeId);
        if (entity != null) {
            entity.setIsDefault(1);
            entity.setUpdateDate(new Date());
            baseDao.updateById(entity);
        }
    }

    @Override
    public void deleteByAgentId(String agentId) {
        baseDao.deleteByAgentId(agentId);
    }
}

