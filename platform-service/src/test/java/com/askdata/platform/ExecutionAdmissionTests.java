package com.askdata.platform;

import com.askdata.platform.execution.ExecutionAdmissionController;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.Duration;
import java.util.concurrent.Executors;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(properties={"spring.datasource.url=jdbc:h2:mem:admission-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1","spring.task.scheduling.enabled=false"})
class ExecutionAdmissionTests {
    @Autowired JdbcTemplate jdbc;

    @Test
    void enforcesGlobalQueueCapacityFastRejectionAndAdmissionAfterRelease()throws Exception{
        var gate=new ExecutionAdmissionController(1,1,1,1000,jdbc);var first=gate.acquire(1);gate.activate("first",first);
        try(var executor=Executors.newVirtualThreadPerTaskExecutor()){
            var waiting=executor.submit(()->gate.acquire(2));
            for(int i=0;i<100&&gate.queueDepth()==0;i++)Thread.sleep(2);
            assertThat(gate.queueDepth()).isEqualTo(1);
            var started=System.nanoTime();
            assertThatThrownBy(()->gate.acquire(3)).isInstanceOf(ExecutionAdmissionController.OverloadedException.class).hasMessageContaining("队列已满");
            assertThat(Duration.ofNanos(System.nanoTime()-started)).isLessThan(Duration.ofSeconds(1));
            gate.complete("first");var second=waiting.get();assertThat(second.waitMs()).isGreaterThanOrEqualTo(0);second.close();
        }
    }

    @Test
    void enforcesPerUserLimitAndFiveSecondPolicyIsConfigurable(){
        var gate=new ExecutionAdmissionController(2,1,2,80,jdbc);var first=gate.acquire(7);var otherUser=gate.acquire(8);var started=System.nanoTime();
        assertThatThrownBy(()->gate.acquire(7)).isInstanceOf(ExecutionAdmissionController.OverloadedException.class).extracting("code").isEqualTo("EXECUTION_QUEUE_TIMEOUT");
        assertThat(Duration.ofNanos(System.nanoTime()-started)).isBetween(Duration.ofMillis(50),Duration.ofSeconds(1));first.close();otherUser.close();
    }
}
