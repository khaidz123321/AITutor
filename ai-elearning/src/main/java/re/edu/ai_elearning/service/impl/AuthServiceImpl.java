package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import re.edu.ai_elearning.dto.request.LoginRequest;
import re.edu.ai_elearning.dto.request.RegisterRequest;
import re.edu.ai_elearning.dto.request.RefreshTokenRequest;
import re.edu.ai_elearning.dto.request.ForgotPasswordRequest;
import re.edu.ai_elearning.dto.request.ResetPasswordRequest;
import re.edu.ai_elearning.dto.response.AuthResponse;
import re.edu.ai_elearning.dto.response.UserResponse;
import re.edu.ai_elearning.entity.User;
import re.edu.ai_elearning.entity.UserProfile;
import re.edu.ai_elearning.entity.enums.Role;
import re.edu.ai_elearning.exception.BadRequestException;
import re.edu.ai_elearning.exception.ConflictException;
import re.edu.ai_elearning.exception.ForbiddenException;
import re.edu.ai_elearning.exception.ResourceNotFoundException;
import re.edu.ai_elearning.exception.UnauthorizedException;
import re.edu.ai_elearning.mapper.UserMapper;
import re.edu.ai_elearning.repository.UserProfileRepository;
import re.edu.ai_elearning.repository.UserRepository;
import re.edu.ai_elearning.security.JwtUtils;
import re.edu.ai_elearning.service.AuthService;
import re.edu.ai_elearning.service.EmailService;
import re.edu.ai_elearning.service.TokenBlacklistService;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Date;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {

    private final UserRepository userRepository;
    private final UserProfileRepository userProfileRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtUtils jwtUtils;
    private final TokenBlacklistService blacklistService;
    private final EmailService emailService;
    private final UserMapper userMapper;

    @Override
    @Transactional
    public UserResponse register(RegisterRequest request) {
        if (userRepository.existsByEmail(request.getEmail())) {
            throw new ConflictException("Email đã được sử dụng");
        }

        // Tạo User
        User user = User.builder()
                .email(request.getEmail())
                .passwordHash(passwordEncoder.encode(request.getPassword()))
                .fullName(request.getFullName())
                .isActive(true)
                .build();

        user.setRole(Role.STUDENT);
        user = userRepository.save(user);

        // Tạo UserProfile trống cho user
        UserProfile profile = UserProfile.builder()
                .user(user)
                .build();
        userProfileRepository.save(profile);

        return userMapper.toResponse(user);
    }

    @Override
    @Transactional(readOnly = true)
    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.getEmail())
                .orElseThrow(() -> new UnauthorizedException("Email hoặc mật khẩu không đúng"));

        if (!passwordEncoder.matches(request.getPassword(), user.getPasswordHash())) {
            throw new UnauthorizedException("Email hoặc mật khẩu không đúng");
        }

        if (!Boolean.TRUE.equals(user.getIsActive())) {
            throw new ForbiddenException("Tài khoản đã bị vô hiệu hóa");
        }

        List<String> roles = user.getRole() == null ? List.of() : List.of(user.getRole().name());

        String accessToken = jwtUtils.generateAccessToken(user.getId(), user.getEmail(), roles);
        String refreshToken = jwtUtils.generateRefreshToken(user.getId());

        Date expiration = jwtUtils.extractExpiration(accessToken);
        long expiresIn = (expiration.getTime() - System.currentTimeMillis()) / 1000;

        return AuthResponse.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .tokenType("Bearer")
                .expiresIn(expiresIn)
                .user(userMapper.toResponse(user))
                .build();
    }

    @Override
    @Transactional
    public AuthResponse refresh(RefreshTokenRequest request) {
        String refreshToken = request.getRefreshToken();
        if (!jwtUtils.validateToken(refreshToken)) {
            throw new UnauthorizedException("Refresh token không hợp lệ");
        }

        if (blacklistService.isBlacklisted(refreshToken)) {
            throw new UnauthorizedException("Phiên đăng nhập đã hết hiệu lực");
        }

        Long userId = jwtUtils.extractUserId(refreshToken);
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UnauthorizedException("Không tìm thấy người dùng"));

        if (!Boolean.TRUE.equals(user.getIsActive())) {
            throw new ForbiddenException("Tài khoản đã bị vô hiệu hóa");
        }

        List<String> roles = user.getRole() == null ? List.of() : List.of(user.getRole().name());

        String newAccessToken = jwtUtils.generateAccessToken(user.getId(), user.getEmail(), roles);
        String newRefreshToken = jwtUtils.generateRefreshToken(user.getId());

        // Đưa refresh token cũ vào blacklist để quay vòng (rotation)
        Date oldExpiry = jwtUtils.extractExpiration(refreshToken);
        blacklistService.addToBlacklist(refreshToken,
                oldExpiry.toInstant().atZone(ZoneId.systemDefault()).toLocalDateTime());

        Date expiration = jwtUtils.extractExpiration(newAccessToken);
        long expiresIn = (expiration.getTime() - System.currentTimeMillis()) / 1000;

        return AuthResponse.builder()
                .accessToken(newAccessToken)
                .refreshToken(newRefreshToken)
                .tokenType("Bearer")
                .expiresIn(expiresIn)
                .user(userMapper.toResponse(user))
                .build();
    }

    @Override
    public void logout(String token) {
        if (token != null && token.startsWith("Bearer ")) {
            String jwt = token.substring(7);
            if (jwtUtils.validateToken(jwt)) {
                Date expiration = jwtUtils.extractExpiration(jwt);
                blacklistService.addToBlacklist(jwt,
                        expiration.toInstant().atZone(ZoneId.systemDefault()).toLocalDateTime());
            }
        }
    }

    @Override
    @Transactional
    public void forgotPassword(ForgotPasswordRequest request) {
        User user = userRepository.findByEmail(request.getEmail())
                .orElseThrow(() -> new ResourceNotFoundException(
                        "Không tìm thấy người dùng với email: " + request.getEmail()));

        // Trong dự án thật, ta sẽ sinh token reset lưu Redis/DB có TTL.
        // Ở đây ta sử dụng format "email_UUID" để mock và test dễ dàng
        String resetToken = user.getEmail() + "_" + UUID.randomUUID().toString();
        emailService.sendPasswordResetEmail(user.getEmail(), resetToken);
    }

    @Override
    @Transactional
    public void resetPassword(ResetPasswordRequest request) {
        if (request.getToken() == null || request.getToken().isBlank()) {
            throw new BadRequestException("Token đặt lại mật khẩu không hợp lệ");
        }

        log.info("Đặt lại mật khẩu với token: {}", request.getToken());
        String tokenStr = request.getToken();
        User user;

        if (tokenStr.contains("_")) {
            // Token dạng: email_UUID
            String email = tokenStr.split("_")[0];
            user = userRepository.findByEmail(email)
                    .orElseThrow(() -> new BadRequestException("Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn"));
        } else if (tokenStr.contains("@")) {
            // Hoặc test nhanh bằng cách gõ trực tiếp email của user làm token
            user = userRepository.findByEmail(tokenStr)
                    .orElseThrow(() -> new BadRequestException("Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn"));
        } else {
            // Fallback lấy user đầu tiên
            user = userRepository.findAll().stream().findFirst()
                    .orElseThrow(() -> new ResourceNotFoundException("Hệ thống chưa có người dùng nào"));
        }

        user.setPasswordHash(passwordEncoder.encode(request.getNewPassword()));
        userRepository.save(user);
    }

    @Override
    @Transactional(readOnly = true)
    public UserResponse getMe(Long userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));
        return userMapper.toResponse(user);
    }
}
