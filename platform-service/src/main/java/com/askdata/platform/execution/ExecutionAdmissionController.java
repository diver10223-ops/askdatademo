package com.askdata.platform.execution;

import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

@Component
public class ExecutionAdmissionController {
    private final Semaphore global;private final int perUserLimit;private final Semaphore queue;private final long maxWaitMs;private final JdbcTemplate jdbc;
    private final Map<Long,Semaphore> users=new ConcurrentHashMap<>();private final Map<String,Permit> active=new ConcurrentHashMap<>();
    private final AtomicInteger waiting=new AtomicInteger();
    public ExecutionAdmissionController(@Value("${askdata.execution.max-concurrency:30}")int globalLimit,
                                        @Value("${askdata.execution.per-user-concurrency:2}")int perUserLimit,
                                        @Value("${askdata.execution.queue-capacity:50}")int queueCapacity,
                                        @Value("${askdata.execution.max-queue-wait-ms:5000}")long maxWaitMs,JdbcTemplate jdbc){
        if(globalLimit<1||perUserLimit<1||queueCapacity<0||maxWaitMs<1)throw new IllegalArgumentException("执行准入参数无效");
        this.global=new Semaphore(globalLimit,true);this.perUserLimit=perUserLimit;this.queue=new Semaphore(queueCapacity,true);this.maxWaitMs=maxWaitMs;this.jdbc=jdbc;
    }
    @PostConstruct
    void restoreActivePermits(){
        for(var row:jdbc.query("select r.public_id,r.user_id from run_request r where r.status in ('PENDING','RUNNING','CANCELLATION_REQUESTED') and r.admitted_at is not null",(rs,n)->Map.entry(rs.getString(1),rs.getLong(2)))){
            boolean acquired=global.tryAcquire();if(acquired){if(user(row.getValue()).tryAcquire())active.put(row.getKey(),new Permit(row.getValue(),0,false));else global.release();}
        }
    }
    public Permit acquire(long userId){
        long started=System.nanoTime();boolean queued=false;
        if(!queue.tryAcquire())throw new OverloadedException("EXECUTION_QUEUE_FULL","执行队列已满，请稍后重试");
        try{
            queued=true;waiting.incrementAndGet();long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(maxWaitMs);var user=user(userId);
            do{
                long remaining=deadline-System.nanoTime();if(remaining<=0)break;
                try{
                    if(global.tryAcquire(Math.min(TimeUnit.NANOSECONDS.toMillis(remaining)+1,50),TimeUnit.MILLISECONDS)){
                        if(user.tryAcquire())return new Permit(userId,Duration.ofNanos(System.nanoTime()-started).toMillis(),queued);
                        global.release();
                    }
                }catch(InterruptedException exception){Thread.currentThread().interrupt();throw new OverloadedException("EXECUTION_QUEUE_INTERRUPTED","执行排队被中断");}
            }while(true);
            throw new OverloadedException("EXECUTION_QUEUE_TIMEOUT","执行排队超过最大等待时间");
        }finally{if(queued){waiting.decrementAndGet();queue.release();}}
    }
    public void activate(String requestId,Permit permit){active.put(requestId,permit);}
    public void complete(String requestId){var permit=active.remove(requestId);if(permit!=null)permit.close();}
    public int activeCount(){return active.size();}public int queueDepth(){return waiting.get();}
    private Semaphore user(long id){return users.computeIfAbsent(id,key->new Semaphore(perUserLimit,true));}
    public final class Permit implements AutoCloseable{
        private final long userId;private final long waitMs;private final boolean queued;private final AtomicBoolean closed=new AtomicBoolean();
        private Permit(long userId,long waitMs,boolean queued){this.userId=userId;this.waitMs=waitMs;this.queued=queued;}
        public long waitMs(){return waitMs;}public boolean queued(){return queued&&waitMs>0;}
        @Override public void close(){if(closed.compareAndSet(false,true)){user(userId).release();global.release();}}
    }
    public static class OverloadedException extends RuntimeException{private final String code;public OverloadedException(String code,String message){super(message);this.code=code;}public String code(){return code;}}
}
