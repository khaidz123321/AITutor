package re.edu.ai_elearning.service;

import re.edu.ai_elearning.dto.request.UpdateLearningProgressRequest;
import re.edu.ai_elearning.dto.response.CourseResponse;
import re.edu.ai_elearning.dto.response.LearningProfileResponse;
import re.edu.ai_elearning.dto.response.PagedResponse;

import java.util.List;

public interface LearningProfileService {
    LearningProfileResponse getProfile(Long userId, Long courseId);
    PagedResponse<LearningProfileResponse> getProfilesByCourse(Long courseId, int page, int size);
    LearningProfileResponse updateProgress(Long userId, UpdateLearningProgressRequest request);
    List<CourseResponse> getLearningPath(Long userId);
}
