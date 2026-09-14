package com.bankpulse.split;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import java.math.BigDecimal;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;

@SpringBootTest(
    properties = {
      "spring.datasource.url=jdbc:h2:mem:split-contract;DB_CLOSE_DELAY=-1",
      "spring.datasource.username=sa",
      "spring.datasource.password=",
      "spring.jpa.hibernate.ddl-auto=create-drop",
      "spring.kafka.bootstrap-servers=localhost:1"
    })
class SplitTransactionTest {
  @Autowired SplitService service;
  @Autowired SplitSessionRepository sessions;
  @MockitoSpyBean SplitOutboxRepository outbox;

  @BeforeEach
  void clear() {
    reset(outbox);
    outbox.deleteAll();
    sessions.deleteAll();
  }

  @Test
  void failedOutboxInsertRollsBackNewAggregate() {
    doThrow(new IllegalStateException("injected outbox failure"))
        .when(outbox)
        .save(any(SplitOutbox.class));
    assertThrows(
        IllegalStateException.class,
        () -> service.create("DEMO", new BigDecimal("100.00"), "USD", "rollback", "test"));
    assertEquals(0, sessions.count());
    assertEquals(0, outbox.count());
  }

  @Test
  void failedOutboxInsertRollsBackParticipantAndVersion() {
    var created = service.create("DEMO", new BigDecimal("100.00"), "USD", "rollback", "test");
    long before = created.getAggregateVersion();
    doThrow(new IllegalStateException("injected outbox failure"))
        .when(outbox)
        .save(any(SplitOutbox.class));
    assertThrows(
        IllegalStateException.class,
        () ->
            service.change(created.getId(), "GUEST", new BigDecimal("60.00"), null, null, "test"));
    var persisted = sessions.findById(created.getId()).orElseThrow();
    assertEquals(before, persisted.getAggregateVersion());
    assertTrue(persisted.getParticipants().isEmpty());
    assertEquals(1, outbox.count());
  }
}
