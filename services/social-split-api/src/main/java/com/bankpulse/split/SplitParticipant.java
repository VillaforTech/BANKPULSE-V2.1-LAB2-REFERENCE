package com.bankpulse.split;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.util.UUID;

@Entity
@Table(
    name = "split_participants",
    uniqueConstraints = @UniqueConstraint(columnNames = {"session_id", "memberId"}))
public class SplitParticipant {
  @Id private String id;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "session_id")
  @JsonIgnore
  private SplitSession session;

  private String memberId;

  @Column(precision = 19, scale = 2, nullable = false)
  private BigDecimal shareAmount;

  private boolean authorized;
  private String paymentReference;

  protected SplitParticipant() {}

  SplitParticipant(SplitSession session, String member, BigDecimal amount) {
    this.id = UUID.randomUUID().toString();
    this.session = session;
    this.memberId = member;
    this.shareAmount = amount;
  }

  void authorize(String reference) {
    this.authorized = true;
    this.paymentReference = reference;
  }

  public String getId() {
    return id;
  }

  public String getMemberId() {
    return memberId;
  }

  public BigDecimal getShareAmount() {
    return shareAmount;
  }

  public boolean isAuthorized() {
    return authorized;
  }

  public String getPaymentReference() {
    return paymentReference;
  }
}
