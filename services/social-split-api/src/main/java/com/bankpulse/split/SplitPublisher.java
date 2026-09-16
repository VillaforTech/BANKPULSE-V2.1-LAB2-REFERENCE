package com.bankpulse.split;

import java.util.concurrent.TimeUnit;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class SplitPublisher {
  private final SplitOutboxRepository outbox;
  private final KafkaTemplate<String, String> kafka;

  SplitPublisher(SplitOutboxRepository outbox, KafkaTemplate<String, String> kafka) {
    this.outbox = outbox;
    this.kafka = kafka;
  }

  @Scheduled(fixedDelayString = "${split.publish-delay-ms:100}")
  @Transactional
  public void publish() {
    for (var event : outbox.findTop100ByPublishedFalseOrderBySequenceAsc())
      try {
        kafka
            .send("bankpulse.social-split.events.v1", event.getAggregateId(), event.getPayload())
            .get(5, TimeUnit.SECONDS);
        event.sent();
      } catch (Exception e) {
        event.failed();
        break;
      }
  }
}
