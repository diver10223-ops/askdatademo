package com.askdata.platform.flow;

import com.askdata.platform.audit.AuditLogService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
public class FlowManagementService {
    private final JdbcTemplate jdbc;
    private final AuditLogService audit;

    public FlowManagementService(JdbcTemplate jdbc, AuditLogService audit) { this.jdbc=jdbc; this.audit=audit; }

    @Transactional
    public ScenarioView create(ScenarioCommand command, long actorId) {
        jdbc.update("insert into flow_scenario(code,name,description,terminal_layer,fallback_policy,sort_no,status) values (?,?,?,?,?,?, 'DRAFT')",
                command.code, command.name, command.description, command.terminalLayer, command.fallbackPolicy, command.sortNo);
        var value=find(command.code);
        audit.append(new AuditLogService.AuditEvent("flow-"+UUID.randomUUID(),actorId==0?null:actorId,"user-"+actorId,"CREATE_SCENARIO","FLOW_SCENARIO",String.valueOf(value.id),null,"{\"code\":\""+command.code+"\",\"status\":\"DRAFT\"}",null,null,"SUCCEEDED",null));
        return value;
    }
    public List<ScenarioView> list(){return jdbc.query("select id,code,name,terminal_layer,fallback_policy,sort_no,status,version_no from flow_scenario order by sort_no,code",(rs,row)->view(rs));}
    private ScenarioView find(String code){return jdbc.query("select id,code,name,terminal_layer,fallback_policy,sort_no,status,version_no from flow_scenario where code=?",(rs,row)->view(rs),code).stream().findFirst().orElseThrow();}
    private ScenarioView view(java.sql.ResultSet rs)throws java.sql.SQLException{return new ScenarioView(rs.getLong(1),rs.getString(2),rs.getString(3),rs.getString(4),rs.getString(5),rs.getInt(6),rs.getString(7),rs.getInt(8));}
    public record ScenarioCommand(String code,String name,String description,String terminalLayer,String fallbackPolicy,int sortNo){}
    public record ScenarioView(long id,String code,String name,String terminalLayer,String fallbackPolicy,int sortNo,String status,int versionNo){}
}
