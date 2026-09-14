package com.bankpulse.split;

import jakarta.persistence.LockModeType;
import java.util.Optional;
import org.springframework.data.jpa.repository.*;
import org.springframework.data.repository.query.Param;

public interface SplitSessionRepository extends JpaRepository<SplitSession, String> {
  @Lock(LockModeType.PESSIMISTIC_WRITE)
  @Query("select s from SplitSession s where s.id=:id")
  Optional<SplitSession> findLocked(@Param("id") String id);
}
