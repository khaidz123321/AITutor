package re.edu.ai_elearning.mapper;

import org.springframework.stereotype.Component;
import re.edu.ai_elearning.dto.response.UserResponse;
import re.edu.ai_elearning.entity.User;

import java.util.Collections;
import java.util.stream.Collectors;

@Component
public class UserMapper {

    public UserResponse toResponse(User user) {
        if (user == null) {
            return null;
        }

        return UserResponse.builder()
                .id(user.getId())
                .email(user.getEmail())
                .fullName(user.getFullName())
                .isActive(user.getIsActive())
                .roles(user.getRole() == null ? Collections.emptyList() :
                        Collections.singletonList(user.getRole().name()))
                .createdAt(user.getCreatedAt())
                .build();
    }
}
