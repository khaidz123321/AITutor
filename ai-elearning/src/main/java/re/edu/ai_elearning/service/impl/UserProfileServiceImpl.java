package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import re.edu.ai_elearning.dto.request.UserProfileRequest;
import re.edu.ai_elearning.dto.response.UserProfileResponse;
import re.edu.ai_elearning.entity.User;
import re.edu.ai_elearning.entity.UserProfile;
import re.edu.ai_elearning.exception.ResourceNotFoundException;
import re.edu.ai_elearning.mapper.UserProfileMapper;
import re.edu.ai_elearning.repository.UserProfileRepository;
import re.edu.ai_elearning.repository.UserRepository;
import re.edu.ai_elearning.service.UserProfileService;

@Service
@RequiredArgsConstructor
public class UserProfileServiceImpl implements UserProfileService {

    private final UserProfileRepository userProfileRepository;
    private final UserRepository userRepository;
    private final UserProfileMapper userProfileMapper;

    @Override
    @Transactional(readOnly = true)
    public UserProfileResponse getProfile(Long userId) {
        UserProfile profile = userProfileRepository.findByUserId(userId)
                .orElseThrow(() -> new ResourceNotFoundException("Hồ sơ cá nhân chưa được tạo"));
        return userProfileMapper.toResponse(profile);
    }

    @Override
    @Transactional
    public UserProfileResponse updateProfile(Long userId, UserProfileRequest request) {
        UserProfile profile = userProfileRepository.findByUserId(userId)
                .orElseGet(() -> {
                    User user = userRepository.findById(userId)
                            .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));
                    UserProfile newProfile = UserProfile.builder()
                            .user(user)
                            .build();
                    return userProfileRepository.save(newProfile);
                });

        profile.setAvatarUrl(request.getAvatarUrl());
        profile.setDateOfBirth(request.getDateOfBirth());
        profile.setGender(request.getGender());
        profile.setPhone(request.getPhone());
        profile.setAddress(request.getAddress());
        profile.setCity(request.getCity());
        profile.setCountry(request.getCountry());
        profile.setBio(request.getBio());

        profile = userProfileRepository.save(profile);
        return userProfileMapper.toResponse(profile);
    }
}
