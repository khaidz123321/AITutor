package re.edu.ai_elearning.mapper;

import org.springframework.stereotype.Component;
import re.edu.ai_elearning.dto.response.UserProfileResponse;
import re.edu.ai_elearning.entity.UserProfile;

@Component
public class UserProfileMapper {

    public UserProfileResponse toResponse(UserProfile profile) {
        if (profile == null) {
            return null;
        }

        return UserProfileResponse.builder()
                .id(profile.getId())
                .userId(profile.getUser() != null ? profile.getUser().getId() : null)
                .avatarUrl(profile.getAvatarUrl())
                .dateOfBirth(profile.getDateOfBirth())
                .gender(profile.getGender())
                .phone(profile.getPhone())
                .address(profile.getAddress())
                .city(profile.getCity())
                .country(profile.getCountry())
                .bio(profile.getBio())
                .updatedAt(profile.getUpdatedAt())
                .build();
    }
}
