package com.askdata.platform.execution;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.UUID;

@Component
public class ExecutionFactReconciler {
    private final JdbcTemplate jdbc;private final PlatformExecutionService service;
    public ExecutionFactReconciler(JdbcTemplate jdbc,PlatformExecutionService service){this.jdbc=jdbc;this.service=service;}
    @Scheduled(fixedDelayString="${askdata.execution.reconcile-delay-ms:1000}")
    public void reconcile(){
        var rows=jdbc.query("select public_id,trace_id from run_request where status in ('PENDING','RUNNING','CANCELLATION_REQUESTED') order by created_at fetch first 100 rows only",(rs,n)->new Pending(rs.getString(1),rs.getString(2)));
        for(var row:rows)try{service.detail(UUID.fromString(row.publicId),row.traceId);}catch(RuntimeException ignored){}
    }
    private record Pending(String publicId,String traceId){}
}
