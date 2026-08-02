package re.edu.ai_elearning.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import re.edu.ai_elearning.entity.News;

import java.util.List;
import java.util.Optional;

@Repository
public interface NewsRepository extends JpaRepository<News, Long> {
    List<News> findAllByOrderByCreatedAtDesc();
    List<News> findByCategoryOrderByCreatedAtDesc(String category);
    Optional<News> findFirstByIsSpotlightTrueOrderByCreatedAtDesc();
}
