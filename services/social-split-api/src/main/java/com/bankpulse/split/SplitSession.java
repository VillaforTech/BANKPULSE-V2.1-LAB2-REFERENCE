package com.bankpulse.split;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;

@Entity
@Table(name = "split_sessions")
public class SplitSession {
  @Id private String id;
  @Version private long lockVersion;
  private long aggregateVersion;
  private String hostMemberId;

  @Column(precision = 19, scale = 2, nullable = false)
  private BigDecimal totalAmount;

  private String currency;
  private String status;
  private String fixtureRunId;
  private String lastEventId;
  private Instant createdAt;
  private Instant closedAt;
  private Instant updatedAt;

  @OneToMany(
      mappedBy = "session",
      cascade = CascadeType.ALL,
      orphanRemoval = true,
      fetch = FetchType.EAGER)
  private List<SplitParticipant> participants = new ArrayList<>();

  protected SplitSession() {}

  public SplitSession(String host, BigDecimal total, String currency) {
    this(host, total, currency, null, Instant.now());
  }

  public SplitSession(String host, BigDecimal total, String currency, String fixture, Instant now) {
    if (host == null || host.isBlank() || currency == null || !currency.matches("[A-Z]{3}"))
      throw new IllegalArgumentException("host and ISO-style currency required");
    this.id = UUID.randomUUID().toString();
    this.hostMemberId = host;
    this.totalAmount = money(total);
    this.currency = currency;
    this.fixtureRunId = fixture;
    this.status = "OPEN";
    this.createdAt = now.truncatedTo(ChronoUnit.MILLIS);
    this.updatedAt = createdAt;
    this.aggregateVersion = 1;
  }

  static BigDecimal money(BigDecimal value) {
    if (value == null
        || value.signum() <= 0
        || value.scale() > 2
        || value.precision() - value.scale() > 17)
      throw new IllegalArgumentException(
          "positive amount with at most two decimal places required");
    return value.setScale(2);
  }

  void open() {
    if (!"OPEN".equals(status)) throw new IllegalStateException("completed session is immutable");
  }

  void changed() {
    aggregateVersion++;
    updatedAt = Instant.now().truncatedTo(ChronoUnit.MILLIS);
  }

  public boolean addParticipant(String member, BigDecimal share) {
    open();
    if (member == null || member.isBlank()) throw new IllegalArgumentException("member required");
    BigDecimal amount = money(share);
    for (var participant : participants)
      if (participant.getMemberId().equals(member)) {
        if (participant.getShareAmount().compareTo(amount) == 0) return false;
        throw new IllegalStateException("member already has a different share");
      }
    participants.add(new SplitParticipant(this, member, amount));
    changed();
    return true;
  }

  public boolean authorize(String participantId, String reference) {
    open();
    if (reference == null || reference.isBlank())
      throw new IllegalArgumentException("payment reference required");
    var participant =
        participants.stream()
            .filter(x -> x.getId().equals(participantId))
            .findFirst()
            .orElseThrow(() -> new NoSuchElementException("participant not found"));
    if (participant.isAuthorized()) {
      if (reference.equals(participant.getPaymentReference())) return false;
      throw new IllegalStateException("authorization reference cannot change");
    }
    participant.authorize(reference);
    changed();
    return true;
  }

  public boolean closeIfAuthorized() {
    if ("COMPLETED".equals(status)) return false;
    if (participants.isEmpty()
        || participants.stream()
            .anyMatch(
                x ->
                    !x.isAuthorized()
                        || x.getPaymentReference() == null
                        || x.getPaymentReference().isBlank()
                        || x.getShareAmount().signum() <= 0))
      throw new IllegalStateException("all positive shares need authorization references");
    BigDecimal sum =
        participants.stream()
            .map(SplitParticipant::getShareAmount)
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    if (sum.compareTo(totalAmount) != 0)
      throw new IllegalStateException(
          "authorized shares must equal session total"); // MUTATION_TARGET_SUM
    status = "COMPLETED";
    closedAt = Instant.now().truncatedTo(ChronoUnit.MILLIS);
    changed();
    return true;
  }

  void markEvent(String id) {
    lastEventId = id;
  }

  public String getLastEventId() {
    return lastEventId;
  }

  public String getId() {
    return id;
  }

  public String getHostMemberId() {
    return hostMemberId;
  }

  public BigDecimal getTotalAmount() {
    return totalAmount;
  }

  public String getCurrency() {
    return currency;
  }

  public String getStatus() {
    return status;
  }

  public Instant getCreatedAt() {
    return createdAt;
  }

  public Instant getClosedAt() {
    return closedAt;
  }

  public Instant getUpdatedAt() {
    return updatedAt;
  }

  public String getFixtureRunId() {
    return fixtureRunId;
  }

  public long getAggregateVersion() {
    return aggregateVersion;
  }

  public List<SplitParticipant> getParticipants() {
    return Collections.unmodifiableList(participants);
  }
}
