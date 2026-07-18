package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import re.edu.ai_elearning.dto.request.ChangePasswordRequest;
import re.edu.ai_elearning.dto.request.RegisterRequest;
import re.edu.ai_elearning.dto.request.UpdateUserRequest;
import re.edu.ai_elearning.dto.response.PagedResponse;
import re.edu.ai_elearning.dto.response.UserResponse;
import re.edu.ai_elearning.dto.request.UpdateRolesRequest;
import re.edu.ai_elearning.dto.response.RoleResponse;
import re.edu.ai_elearning.entity.User;
import re.edu.ai_elearning.entity.UserProfile;
import re.edu.ai_elearning.entity.enums.Role;
import re.edu.ai_elearning.exception.BadRequestException;
import re.edu.ai_elearning.exception.ConflictException;
import re.edu.ai_elearning.exception.ResourceNotFoundException;
import re.edu.ai_elearning.mapper.UserMapper;
import re.edu.ai_elearning.repository.UserProfileRepository;
import re.edu.ai_elearning.repository.UserRepository;
import re.edu.ai_elearning.service.UserService;

import java.util.Set;
import java.util.stream.Collectors;

import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class UserServiceImpl implements UserService {

    private final UserRepository userRepository;
    private final UserProfileRepository userProfileRepository;
    private final PasswordEncoder passwordEncoder;
    private final UserMapper userMapper;

    @Override
    @Transactional(readOnly = true)
    public PagedResponse<UserResponse> getAllUsers(Boolean isActive, int page, int size) {
        Pageable pageable = PageRequest.of(page - 1, size);
        Page<User> userPage;
        if (isActive != null) {
            userPage = userRepository.findAllByStatus(isActive, pageable);
        } else {
            userPage = userRepository.findAllUsers(pageable);
        }
        return PagedResponse.of(userPage, userMapper::toResponse);
    }

    @Override
    @Transactional(readOnly = true)
    public UserResponse getUserById(Long id) {
        User user = userRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));
        return userMapper.toResponse(user);
    }

    @Override
    @Transactional
    public UserResponse createUser(RegisterRequest request, List<Long> roleIds) {
        if (userRepository.existsByEmail(request.getEmail())) {
            throw new ConflictException("Email đã được sử dụng");
        }

        User user = User.builder()
                .email(request.getEmail())
                .passwordHash(passwordEncoder.encode(request.getPassword()))
                .fullName(request.getFullName())
                .isActive(true)
                .build();
        user = userRepository.save(user);

        // Tạo UserProfile trống
        UserProfile profile = UserProfile.builder()
                .user(user)
                .build();
        userProfileRepository.save(profile);

        if (roleIds != null && !roleIds.isEmpty()) {
            Long roleId = roleIds.get(0);
            Role role = (roleId != null && roleId >= 0 && roleId < Role.values().length)
                    ? Role.values()[roleId.intValue()]
                    : Role.STUDENT;
            user.setRole(role);
            user = userRepository.save(user);
        } else {
            user.setRole(Role.STUDENT);
            user = userRepository.save(user);
        }

        return userMapper.toResponse(user);
    }

    @Override
    @Transactional
    public UserResponse updateUser(Long id, UpdateUserRequest request) {
        User user = userRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));

        if (!user.getEmail().equalsIgnoreCase(request.getEmail()) && userRepository.existsByEmail(request.getEmail())) {
            throw new ConflictException("Email đã được sử dụng");
        }

        user.setEmail(request.getEmail());
        user.setFullName(request.getFullName());
        user = userRepository.save(user);

        return userMapper.toResponse(user);
    }

    @Override
    @Transactional
    public void toggleUserStatus(Long id, Boolean isActive) {
        User user = userRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));

        // Bảo vệ ADMIN cuối cùng không bị khóa
        if (Boolean.FALSE.equals(isActive)) {
            boolean isAdmin = Role.ADMIN == user.getRole();
            if (isAdmin && userRepository.countByRoleName(Role.ADMIN) <= 1) {
                throw new BadRequestException("Hệ thống phải có ít nhất 1 quản trị viên đang hoạt động");
            }
        }

        user.setIsActive(isActive);
        userRepository.save(user);
    }

    @Override
    @Transactional
    public void deleteUser(Long id, Long currentUserId) {
        if (id.equals(currentUserId)) {
            throw new BadRequestException("Không thể tự xóa tài khoản của chính mình");
        }

        User user = userRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));

        // Bảo vệ ADMIN cuối cùng không bị xóa
        boolean isAdmin = Role.ADMIN == user.getRole();
        if (isAdmin && userRepository.countByRoleName(Role.ADMIN) <= 1) {
            throw new BadRequestException("Hệ thống phải có ít nhất 1 quản trị viên");
        }

        // Xóa profile
        userProfileRepository.findByUserId(id).ifPresent(userProfileRepository::delete);

        // Xóa user
        userRepository.delete(user);
    }

    @Override
    @Transactional
    public void changePassword(Long userId, ChangePasswordRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));

        if (!passwordEncoder.matches(request.getOldPassword(), user.getPasswordHash())) {
            throw new BadRequestException("Mật khẩu cũ không đúng");
        }

        user.setPasswordHash(passwordEncoder.encode(request.getNewPassword()));
        userRepository.save(user);
    }

    @Override
    @Transactional
    public UserResponse updateSelf(Long userId, UpdateUserRequest request) {
        return updateUser(userId, request);
    }

    private String getRoleDescription(Role role) {
        if (role == null)
            return "";
        switch (role) {
            case ADMIN:
                return "Quản trị viên hệ thống";
            case TEACHER:
                return "Giảng viên";
            case STUDENT:
                return "Học viên";
            default:
                return "";
        }
    }

    private Role fromId(Long id) {
        if (id == null || id < 0 || id >= Role.values().length) {
            return null;
        }
        return Role.values()[id.intValue()];
    }

    @Override
    @Transactional(readOnly = true)
    public List<RoleResponse> getAllRoles() {
        return java.util.Arrays.stream(Role.values())
                .map(role -> RoleResponse.builder()
                        .id((long) role.ordinal())
                        .name(role.name())
                        .description(getRoleDescription(role))
                        .build())
                .collect(Collectors.toList());
    }

    @Override
    @Transactional
    public void assignRoles(Long userId, UpdateRolesRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));

        Role currentRole = user.getRole();
        boolean wasAdmin = Role.ADMIN == currentRole;

        if (request.getRoleIds() == null || request.getRoleIds().isEmpty()) {
            throw new BadRequestException("Danh sách vai trò không được để trống");
        }

        Long newRoleId = request.getRoleIds().get(0);
        Role newRole = fromId(newRoleId);
        if (newRole == null) {
            throw new ResourceNotFoundException("Không tìm thấy vai trò với ID: " + newRoleId);
        }

        if (wasAdmin && newRole != Role.ADMIN) {
            long totalAdmins = userRepository.countByRoleName(Role.ADMIN);
            if (totalAdmins <= 1) {
                throw new BadRequestException(
                        "Không thể thu hồi quyền ADMIN của quản trị viên duy nhất trong hệ thống");
            }
        }

        user.setRole(newRole);
        userRepository.save(user);
    }

    @Override
    @Transactional
    public void revokeRole(Long userId, Long roleId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));

        Role roleName = fromId(roleId);
        if (roleName == null) {
            throw new ResourceNotFoundException("Không tìm thấy vai trò");
        }

        if (user.getRole() != roleName) {
            throw new BadRequestException("Người dùng không có vai trò này");
        }

        if (Role.ADMIN == roleName) {
            long totalAdmins = userRepository.countByRoleName(Role.ADMIN);
            if (totalAdmins <= 1) {
                throw new BadRequestException(
                        "Không thể thu hồi quyền ADMIN của quản trị viên duy nhất trong hệ thống");
            }
        }

        user.setRole(Role.STUDENT);
        userRepository.save(user);
    }
}
