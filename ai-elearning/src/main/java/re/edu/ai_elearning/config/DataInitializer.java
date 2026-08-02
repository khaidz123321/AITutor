package re.edu.ai_elearning.config;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import re.edu.ai_elearning.entity.User;
import re.edu.ai_elearning.entity.UserProfile;
import re.edu.ai_elearning.entity.enums.Role;
import re.edu.ai_elearning.repository.UserProfileRepository;
import re.edu.ai_elearning.repository.UserRepository;

@Slf4j
@Component
@RequiredArgsConstructor
public class DataInitializer implements CommandLineRunner {

    private final UserRepository userRepository;
    private final UserProfileRepository userProfileRepository;
    private final PasswordEncoder passwordEncoder;

    @Override
    public void run(String... args) {
        createDefaultUserIfNotExist("admin@elearning.com", "password123", "Quản trị viên PTIT", Role.ADMIN);
        createDefaultUserIfNotExist("admin@ptit.edu.vn", "password123", "Quản trị viên PTIT", Role.ADMIN);
        createDefaultUserIfNotExist("admin2@elearning.com", "password123", "Quản trị viên PTIT Cao Cấp", Role.ADMIN);
        createDefaultUserIfNotExist("teacher1@elearning.com", "password123", "TS. Nguyễn Văn A (Giảng viên)", Role.TEACHER);
        createDefaultUserIfNotExist("student1@elearning.com", "password123", "Nguyễn Văn B (Sinh viên)", Role.STUDENT);
        createDefaultUserIfNotExist("student@ptit.edu.vn", "password123", "Trần Thị C (Sinh viên)", Role.STUDENT);
    }

    private void createDefaultUserIfNotExist(String email, String rawPassword, String fullName, Role role) {
        User user = userRepository.findByEmail(email).orElse(null);

        if (user == null) {
            user = User.builder()
                    .email(email)
                    .passwordHash(passwordEncoder.encode(rawPassword))
                    .fullName(fullName)
                    .role(role)
                    .isActive(true)
                    .build();

            User saved = userRepository.save(user);

            UserProfile profile = UserProfile.builder()
                    .user(saved)
                    .build();
            userProfileRepository.save(profile);

            log.info("Created default user: email={}, role={}", email, role);
        } else {
            user.setPasswordHash(passwordEncoder.encode(rawPassword));
            user.setRole(role);
            user.setIsActive(true);
            userRepository.save(user);
            log.info("Reset password, role & active status for existing user: email={}, role={}", email, role);
        }
    }
}
