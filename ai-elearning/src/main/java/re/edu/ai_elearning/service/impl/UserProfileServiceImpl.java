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

import org.springframework.web.multipart.MultipartFile;
import re.edu.ai_elearning.exception.BadRequestException;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.UUID;

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

        if (request.getAvatarUrl() != null && !request.getAvatarUrl().isBlank()) {
            profile.setAvatarUrl(request.getAvatarUrl());
        }
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

    @Override
    @Transactional
    public UserProfileResponse uploadAvatar(Long userId, MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new BadRequestException("Tập tin ảnh tải lên không được để trống");
        }

        UserProfile profile = userProfileRepository.findByUserId(userId)
                .orElseGet(() -> {
                    User user = userRepository.findById(userId)
                            .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));
                    UserProfile newProfile = UserProfile.builder()
                            .user(user)
                            .build();
                    return userProfileRepository.save(newProfile);
                });

        try {
            String uploadDirSrc = "src/main/resources/static/uploads/avatars/";
            String uploadDirBuild = "build/resources/main/static/uploads/avatars/";

            File dirSrc = new File(uploadDirSrc);
            if (!dirSrc.exists()) dirSrc.mkdirs();

            File dirBuild = new File(uploadDirBuild);
            if (!dirBuild.exists()) dirBuild.mkdirs();

            String originalName = file.getOriginalFilename();
            String ext = (originalName != null && originalName.contains("."))
                    ? originalName.substring(originalName.lastIndexOf("."))
                    : ".jpg";

            String fileName = "avatar_" + userId + "_" + System.currentTimeMillis() + ext;

            Path targetSrc = Paths.get(uploadDirSrc + fileName);
            Files.copy(file.getInputStream(), targetSrc, StandardCopyOption.REPLACE_EXISTING);

            try {
                Path targetBuild = Paths.get(uploadDirBuild + fileName);
                Files.copy(targetSrc, targetBuild, StandardCopyOption.REPLACE_EXISTING);
            } catch (Exception ignored) {}

            String fileUrl = "/uploads/avatars/" + fileName;
            profile.setAvatarUrl(fileUrl);
            profile = userProfileRepository.save(profile);

            return userProfileMapper.toResponse(profile);
        } catch (Exception e) {
            throw new RuntimeException("Không thể lưu ảnh đại diện: " + e.getMessage(), e);
        }
    }
}
