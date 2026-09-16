package com.bankpulse.split;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import java.util.*;
import org.springframework.http.*;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/splits")
public class SocialSplitController {
  private final SplitSessionRepository repo;
  private final SplitOutboxRepository outbox;
  private final SplitService service;

  SocialSplitController(
      SplitSessionRepository repo, SplitOutboxRepository outbox, SplitService service) {
    this.repo = repo;
    this.outbox = outbox;
    this.service = service;
  }

  @PostMapping
  @ResponseStatus(HttpStatus.CREATED)
  SplitSession create(
      @Valid @RequestBody CreateSplit r,
      @RequestHeader(value = "X-Correlation-Id", required = false) String c) {
    return service.create(r.hostMemberId(), r.totalAmount(), r.currency(), r.fixtureRunId(), c);
  }

  @GetMapping("/{id}")
  SplitSession get(@PathVariable String id) {
    return repo.findById(id).orElseThrow(() -> new NoSuchElementException("session not found"));
  }

  @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
  @GetMapping("/outbox-status")
  Map<String, Object> outbox() {
    return Map.of(
        "pending",
        outbox.countByPublishedFalse(),
        "total",
        outbox.count(),
        "aggregateCount",
        repo.count(),
        "versionSum",
        repo.findAll().stream().mapToLong(SplitSession::getAggregateVersion).sum());
  }

  @GetMapping("/snapshot")
  Map<String, Object> snapshot() {
    return Map.of("complete", true, "sessions", repo.findAll());
  }

  @PostMapping("/{id}/participants")
  SplitSession participant(
      @PathVariable String id,
      @Valid @RequestBody AddParticipant r,
      @RequestHeader(value = "X-Correlation-Id", required = false) String c) {
    return service.change(id, r.memberId(), r.shareAmount(), null, null, c);
  }

  @PostMapping("/{id}/participants/{participantId}/authorize")
  SplitSession authorize(
      @PathVariable String id,
      @PathVariable String participantId,
      @Valid @RequestBody Authorize r,
      @RequestHeader(value = "X-Correlation-Id", required = false) String c) {
    return service.change(id, null, null, participantId, r.paymentReference(), c);
  }

  @PostMapping("/{id}/close")
  SplitSession close(
      @PathVariable String id,
      @RequestHeader(value = "X-Correlation-Id", required = false) String c) {
    return service.change(id, null, null, null, null, c);
  }

  @ExceptionHandler(NoSuchElementException.class)
  @ResponseStatus(HttpStatus.NOT_FOUND)
  Map<String, String> missing(Exception e) {
    return Map.of("error", e.getMessage());
  }

  @ExceptionHandler(IllegalStateException.class)
  @ResponseStatus(HttpStatus.CONFLICT)
  Map<String, String> conflict(Exception e) {
    return Map.of("error", e.getMessage());
  }

  @ExceptionHandler(IllegalArgumentException.class)
  @ResponseStatus(HttpStatus.BAD_REQUEST)
  Map<String, String> invalid(Exception e) {
    return Map.of("error", e.getMessage());
  }

  public record CreateSplit(
      @NotBlank String hostMemberId,
      @NotNull @DecimalMin("0.01") @Digits(integer = 17, fraction = 2) BigDecimal totalAmount,
      @NotNull @Pattern(regexp = "[A-Z]{3}") String currency,
      @Size(max = 100) String fixtureRunId) {}

  public record AddParticipant(
      @NotBlank String memberId,
      @NotNull @DecimalMin("0.01") @Digits(integer = 17, fraction = 2) BigDecimal shareAmount) {}

  public record Authorize(@NotBlank String paymentReference) {}
}
