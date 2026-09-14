package com.bankpulse.split;

import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SplitOutboxRepository extends JpaRepository<SplitOutbox, Long> {
  List<SplitOutbox> findTop100ByPublishedFalseOrderBySequenceAsc();

  long countByPublishedFalse();
}
