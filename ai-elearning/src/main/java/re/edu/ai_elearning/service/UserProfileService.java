package re.edu.ai_elearning.service;

import re.edu.ai_elearning.dto.request.UserProfileRequest;
import re.edu.ai_elearning.dto.response.UserProfileResponse;

public interface UserProfileService {
    UserProfileResponse getProfile(Long userId);
    UserProfileResponse updateProfile(Long userId, UserProfileRequest request);
}
