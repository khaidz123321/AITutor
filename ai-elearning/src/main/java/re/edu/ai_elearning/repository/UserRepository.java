package re.edu.ai_elearning.repository;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import re.edu.ai_elearning.entity.User;

import re.edu.ai_elearning.entity.enums.Role;

import java.util.Optional;
import java.util.Set;

public interface UserRepository extends JpaRepository<User, Long> {

    @Query("SELECT u FROM User u WHERE u.email = :email")
    Optional<User> findByEmail(@Param("email") String email);

    @Query("SELECT COUNT(u) > 0 FROM User u WHERE u.email = :email")
    boolean existsByEmail(@Param("email") String email);

    @Query("SELECT u FROM User u WHERE u.isActive = :isActive ORDER BY u.createdAt DESC")
    Page<User> findAllByStatus(@Param("isActive") Boolean isActive, Pageable pageable);

    @Query("SELECT u FROM User u ORDER BY u.createdAt DESC")
    Page<User> findAllUsers(Pageable pageable);

    @Query("SELECT COUNT(u) FROM User u WHERE u.role = :roleName")
    long countByRoleName(@Param("roleName") Role roleName);
}
