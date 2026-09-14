package com.bankpulse.split;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class SplitService {
  private final SplitSessionRepository sessions;
  private final SplitOutboxRepository outbox;
  private final ObjectMapper mapper;

  SplitService(SplitSessionRepository sessions, SplitOutboxRepository outbox, ObjectMapper mapper) {
    this.sessions = sessions;
    this.outbox = outbox;
    this.mapper = mapper;
  }

  @Transactional
  public SplitSession create(
      String host,
      java.math.BigDecimal amount,
      String currency,
      String fixture,
      String correlation) {
    var s = sessions.saveAndFlush(new SplitSession(host, amount, currency, fixture, Instant.now()));
    event(s, "SPLIT_CREATED", correlation);
    return s;
  }

  @Transactional
  public SplitSession change(
      String id,
      String member,
      java.math.BigDecimal amount,
      String participant,
      String reference,
      String correlation) {
    var s =
        sessions.findLocked(id).orElseThrow(() -> new NoSuchElementException("session not found"));
    boolean changed;
    String type;
    if (member != null) {
      changed = s.addParticipant(member, amount);
      type = "PARTICIPANT_ADDED";
    } else if (participant != null) {
      changed = s.authorize(participant, reference);
      type = "PARTICIPANT_AUTHORIZED";
    } else {
      changed = s.closeIfAuthorized();
      type = "SPLIT_COMPLETED";
    }
    if (changed) {
      sessions.saveAndFlush(s);
      event(s, type, correlation);
    }
    return s;
  }

  private void event(SplitSession s, String type, String correlation) {
    String eventId = UUID.randomUUID().toString();
    s.markEvent(eventId);
    sessions.saveAndFlush(s);
    var event = new LinkedHashMap<String, Object>();
    var data = mapper.convertValue(s, Map.class);
    data.put("totalAmount", s.getTotalAmount().toPlainString());
    data.put(
        "participants",
        s.getParticipants().stream()
            .map(
                p -> {
                  var v = new LinkedHashMap<String, Object>();
                  v.put("id", p.getId());
                  v.put("memberId", p.getMemberId());
                  v.put("shareAmount", p.getShareAmount().toPlainString());
                  v.put("authorized", p.isAuthorized());
                  v.put("paymentReference", p.getPaymentReference());
                  return v;
                })
            .toList());
    event.put("schemaVersion", 1);
    event.put("eventId", eventId);
    event.put("eventType", type);
    event.put("aggregateType", "SplitSession");
    event.put("aggregateId", s.getId());
    event.put("aggregateVersion", s.getAggregateVersion());
    event.put("occurredAt", s.getUpdatedAt());
    event.put(
        "correlationId", correlation == null || correlation.isBlank() ? eventId : correlation);
    event.put("fixtureRunId", s.getFixtureRunId());
    event.put("data", data);
    try {
      outbox.save(
          new SplitOutbox(
              eventId, s.getId(), s.getAggregateVersion(), mapper.writeValueAsString(event)));
    } catch (Exception e) {
      throw new IllegalStateException("event serialization failed", e);
    }
  }
}
