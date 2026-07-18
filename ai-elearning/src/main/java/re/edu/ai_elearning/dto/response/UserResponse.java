package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.List;

@Getter
@Builder
public class UserResponse {
    private Long id;
    private String email;
    private String fullName;
    private Boolean isActive;
    private List<String> roles;
    private LocalDateTime createdAt;
}
