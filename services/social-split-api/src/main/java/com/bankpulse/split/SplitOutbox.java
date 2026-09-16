package com.bankpulse.split;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "split_outbox")
public class SplitOutbox {
  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  private Long sequence;

  @Column(unique = true, nullable = false)
  private String eventId;

  private String aggregateId;
  private long aggregateVersion;

  @Column(columnDefinition = "text", nullable = false)
  private String payload;

  private boolean published;
  private int attempts;
  private Instant createdAt;
  private Instant publishedAt;

  protected SplitOutbox() {}

  SplitOutbox(String eventId, String aggregateId, long version, String payload) {
    this.eventId = eventId;
    this.aggregateId = aggregateId;
    this.aggregateVersion = version;
    this.payload = payload;
    this.createdAt = Instant.now();
  }

  public String getAggregateId() {
    return aggregateId;
  }

  public String getPayload() {
    return payload;
  }

  void sent() {
    published = true;
    publishedAt = Instant.now();
  }

  void failed() {
    attempts++;
  }
}
