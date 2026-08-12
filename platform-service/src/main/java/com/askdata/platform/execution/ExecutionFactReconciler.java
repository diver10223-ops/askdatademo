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
        var rows=jdbc.query("select public_id,trace_id,cancel_requested,cancel_propagated_at from run_request where status in ('PENDING','RUNNING','CANCELLATION_REQUESTED') order by created_at fetch first 100 rows only",(rs,n)->new Pending(rs.getString(1),rs.getString(2),rs.getBoolean(3),rs.getObject(4)!=null));
        for(var row:rows)try{var id=UUID.fromString(row.publicId);if(row.cancelRequested&&!row.cancelPropagated)service.propagateCancellation(id,row.traceId,"cancel-"+row.publicId);service.detail(id,row.traceId);}catch(RuntimeException ignored){}
    }
    private record Pending(String publicId,String traceId,boolean cancelRequested,boolean cancelPropagated){}
}
