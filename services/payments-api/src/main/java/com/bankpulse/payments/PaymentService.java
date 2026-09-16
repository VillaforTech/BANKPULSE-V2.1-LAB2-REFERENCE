package com.bankpulse.payments;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class PaymentService {
  private final PaymentRepository payments;
  private final OutboxRepository outbox;
  private final ObjectMapper objectMapper;
  private final org.springframework.transaction.support.TransactionTemplate transactions;

  public PaymentService(
      PaymentRepository payments,
      OutboxRepository outbox,
      ObjectMapper objectMapper,
      org.springframework.transaction.PlatformTransactionManager manager) {
    this.payments = payments;
    this.outbox = outbox;
    this.objectMapper = objectMapper;
    this.transactions = new org.springframework.transaction.support.TransactionTemplate(manager);
  }

  public synchronized Payment create(
      String idempotencyKey, PaymentController.PaymentRequest request) {
    if (idempotencyKey == null || idempotencyKey.isBlank() || idempotencyKey.length() > 100)
      throw new IllegalArgumentException("invalid idempotency key");
    try {
      return transactions.execute(
          status ->
              payments
                  .findByIdempotencyKey(idempotencyKey)
                  .map(p -> same(p, request))
                  .orElseGet(() -> persist(idempotencyKey, request)));
    } catch (org.springframework.dao.DataIntegrityViolationException conflict) {
      return transactions.execute(
          status ->
              same(
                  payments.findByIdempotencyKey(idempotencyKey).orElseThrow(() -> conflict),
                  request));
    }
  }

  private Payment same(Payment p, PaymentController.PaymentRequest r) {
    if (!p.getAccount().equals(r.account())
        || p.getAmount().compareTo(r.amount()) != 0
        || !p.getCurrency().equalsIgnoreCase(r.currency()))
      throw new IllegalStateException("idempotency key reused with different payload");
    return p;
  }

  private Payment persist(String idempotencyKey, PaymentController.PaymentRequest request) {
    Instant now = Instant.now().truncatedTo(java.time.temporal.ChronoUnit.MILLIS);
    Payment payment =
        new Payment(
            UUID.randomUUID().toString(),
            idempotencyKey,
            request.account(),
            request.amount().setScale(2),
            request.currency().toUpperCase(java.util.Locale.ROOT),
            "ACCEPTED",
            now);
    payments.save(payment);

    String eventId = UUID.randomUUID().toString();
    Map<String, Object> event = new LinkedHashMap<>();
    event.put("eventId", eventId);
    event.put("eventType", "PAYMENT_CREATED");
    event.put("aggregateId", payment.getId());
    event.put("occurredAt", now);
    event.put("account", payment.getAccount());
    event.put("amount", payment.getAmount());
    event.put("currency", payment.getCurrency());
    try {
      outbox.save(
          new OutboxEvent(
              eventId,
              payment.getId(),
              "PAYMENT_CREATED",
              objectMapper.writeValueAsString(event),
              now));
    } catch (JsonProcessingException e) {
      throw new IllegalStateException("Could not serialize payment event", e);
    }
    return payment;
  }
}
