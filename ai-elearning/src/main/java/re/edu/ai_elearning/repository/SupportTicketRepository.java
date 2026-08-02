package re.edu.ai_elearning.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import re.edu.ai_elearning.entity.SupportTicket;

import java.util.List;

public interface SupportTicketRepository extends JpaRepository<SupportTicket, Long> {
    List<SupportTicket> findAllByOrderByCreatedAtDesc();
}
