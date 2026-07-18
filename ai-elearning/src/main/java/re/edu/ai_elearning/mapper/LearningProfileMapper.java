package re.edu.ai_elearning.mapper;

import org.springframework.stereotype.Component;
import re.edu.ai_elearning.dto.response.LearningProfileResponse;
import re.edu.ai_elearning.entity.LearningProfile;

@Component
public class LearningProfileMapper {

    public LearningProfileResponse toResponse(LearningProfile profile) {
        if (profile == null) {
            return null;
        }

        return LearningProfileResponse.builder()
                .id(profile.getId())
                .userId(profile.getUser() != null ? profile.getUser().getId() : null)
                .userFullName(profile.getUser() != null ? profile.getUser().getFullName() : null)
                .courseId(profile.getCourse() != null ? profile.getCourse().getId() : null)
                .courseTitle(profile.getCourse() != null ? profile.getCourse().getTitle() : null)
                .progressPercent(profile.getProgressPercent())
                .bloomMastery(profile.getBloomMastery())
                .enrolledAt(profile.getEnrolledAt())
                .lastStudied(profile.getLastStudied())
                .build();
    }
}
