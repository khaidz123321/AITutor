package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Getter
@Builder
public class UserProfileResponse {
    private Long id;
    private Long userId;
    private String avatarUrl;
    private LocalDate dateOfBirth;
    private String gender;
    private String phone;
    private String address;
    private String city;
    private String country;
    private String bio;
    private LocalDateTime updatedAt;
}
