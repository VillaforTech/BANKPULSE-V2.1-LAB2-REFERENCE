package com.bankpulse.split;

import static org.junit.jupiter.api.Assertions.*;

import java.math.BigDecimal;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class SplitSessionTest {
  SplitSession session(String... shares) {
    var s = new SplitSession("host", new BigDecimal("100.00"), "USD");
    for (int i = 0; i < shares.length; i++)
      s.addParticipant("member" + i, new BigDecimal(shares[i]));
    return s;
  }

  void authorize(SplitSession s) {
    for (var p : s.getParticipants()) s.authorize(p.getId(), "DEMO-" + p.getId());
  }

  @Test
  void exactSumClosesOnce() {
    var s = session("60.00", "40.00");
    authorize(s);
    assertTrue(s.closeIfAuthorized());
    Instant closed = s.getClosedAt();
    long v = s.getAggregateVersion();
    assertFalse(s.closeIfAuthorized());
    assertEquals(closed, s.getClosedAt());
    assertEquals(v, s.getAggregateVersion());
    assertEquals("COMPLETED", s.getStatus());
  }

  @Test
  void underpaymentRemainsOpen() {
    var s = session("60.00", "30.00");
    authorize(s);
    assertThrows(IllegalStateException.class, s::closeIfAuthorized);
    assertEquals("OPEN", s.getStatus());
    assertNull(s.getClosedAt());
  }

  @Test
  void overpaymentRemainsOpen() {
    var s = session("60.00", "50.00");
    authorize(s);
    assertThrows(IllegalStateException.class, s::closeIfAuthorized);
    assertEquals("OPEN", s.getStatus());
  }

  @Test
  void emptyAndMissingConsentReject() {
    assertThrows(IllegalStateException.class, session()::closeIfAuthorized);
    assertThrows(IllegalStateException.class, session("100.00")::closeIfAuthorized);
  }

  @Test
  void blankReferenceAndNegativeShareReject() {
    var s = session("100.00");
    assertThrows(
        IllegalArgumentException.class, () -> s.authorize(s.getParticipants().get(0).getId(), " "));
    assertThrows(IllegalArgumentException.class, () -> s.addParticipant("x", new BigDecimal("-1")));
  }

  @Test
  void closedAggregateCannotChange() {
    var s = session("100.00");
    authorize(s);
    s.closeIfAuthorized();
    assertThrows(IllegalStateException.class, () -> s.addParticipant("x", BigDecimal.ONE));
    assertThrows(
        IllegalStateException.class,
        () -> s.authorize(s.getParticipants().get(0).getId(), "other"));
  }

  @Test
  void retriesDontAdvanceVersion() {
    var s = session("100.00");
    long v = s.getAggregateVersion();
    assertFalse(s.addParticipant("member0", new BigDecimal("100")));
    assertEquals(v, s.getAggregateVersion());
    authorize(s);
    v = s.getAggregateVersion();
    authorize(s);
    assertEquals(v, s.getAggregateVersion());
  }

  @Test
  void nullAndFractionalCentReject() {
    assertThrows(IllegalArgumentException.class, () -> new SplitSession("host", null, "USD"));
    assertThrows(IllegalArgumentException.class, () -> session("1.001"));
  }
}
