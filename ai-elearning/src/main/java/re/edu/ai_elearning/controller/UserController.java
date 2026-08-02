package re.edu.ai_elearning.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import re.edu.ai_elearning.dto.request.*;
import re.edu.ai_elearning.dto.response.*;
import re.edu.ai_elearning.security.UserPrincipal;
import re.edu.ai_elearning.service.UserProfileService;
import re.edu.ai_elearning.service.UserService;
import re.edu.ai_elearning.entity.enums.Role;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;
    private final UserProfileService userProfileService;

    @GetMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<PagedResponse<UserResponse>>> getAllUsers(
            @RequestParam(required = false) Boolean isActive,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        PagedResponse<UserResponse> response = userService.getAllUsers(isActive, page, size);
        return ResponseEntity.ok(ApiResponse.success("Lấy danh sách người dùng thành công", response));
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<UserResponse>> getUserById(@PathVariable Long id) {
        UserResponse response = userService.getUserById(id);
        return ResponseEntity.ok(ApiResponse.success("Lấy thông tin người dùng thành công", response));
    }

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<UserResponse>> createUser(
            @Valid @RequestBody RegisterRequest request,
            @RequestParam List<Long> roleIds) {
        UserResponse response = userService.createUser(request, roleIds);
        return ResponseEntity.ok(ApiResponse.success("Tạo tài khoản thành công", response));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<UserResponse>> updateUser(
            @PathVariable Long id,
            @Valid @RequestBody UpdateUserRequest request) {
        UserResponse response = userService.updateUser(id, request);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật thông tin người dùng thành công", response));
    }

    @PatchMapping("/{id}/status")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<Void>> toggleUserStatus(
            @PathVariable Long id,
            @RequestParam Boolean isActive) {
        userService.toggleUserStatus(id, isActive);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật trạng thái tài khoản thành công"));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<Void>> deleteUser(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal) {
        userService.deleteUser(id, principal.getId());
        return ResponseEntity.ok(ApiResponse.success("Xóa người dùng thành công"));
    }

    @PutMapping("/{id}/roles")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<Void>> assignRoles(
            @PathVariable Long id,
            @Valid @RequestBody UpdateRolesRequest request) {
        userService.assignRoles(id, request);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật vai trò người dùng thành công"));
    }

    @DeleteMapping("/{id}/roles/{roleId}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<Void>> revokeRole(
            @PathVariable Long id,
            @PathVariable Long roleId) {
        userService.revokeRole(id, roleId);
        return ResponseEntity.ok(ApiResponse.success("Thu hồi vai trò người dùng thành công"));
    }

    @PutMapping("/me")
    public ResponseEntity<ApiResponse<UserResponse>> updateSelf(
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody UpdateUserRequest request) {
        UserResponse response = userService.updateSelf(principal.getId(), request);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật thông tin cá nhân thành công", response));
    }

    @PutMapping("/me/password")
    public ResponseEntity<ApiResponse<Void>> changePassword(
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody ChangePasswordRequest request) {
        userService.changePassword(principal.getId(), request);
        return ResponseEntity.ok(ApiResponse.success("Đổi mật khẩu thành công"));
    }

    @GetMapping("/me/profile")
    public ResponseEntity<ApiResponse<UserProfileResponse>> getMyProfile(
            @AuthenticationPrincipal UserPrincipal principal) {
        UserProfileResponse response = userProfileService.getProfile(principal.getId());
        return ResponseEntity.ok(ApiResponse.success("Lấy hồ sơ cá nhân thành công", response));
    }

    @PutMapping("/me/profile")
    public ResponseEntity<ApiResponse<UserProfileResponse>> updateMyProfile(
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody UserProfileRequest request) {
        UserProfileResponse response = userProfileService.updateProfile(principal.getId(), request);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật hồ sơ cá nhân thành công", response));
    }

    @PostMapping("/me/avatar")
    public ResponseEntity<ApiResponse<UserProfileResponse>> uploadAvatar(
            @AuthenticationPrincipal UserPrincipal principal,
            @RequestParam("file") org.springframework.web.multipart.MultipartFile file) {
        UserProfileResponse response = userProfileService.uploadAvatar(principal.getId(), file);
        return ResponseEntity.ok(ApiResponse.success("Tải ảnh đại diện lên thành công", response));
    }

    @GetMapping("/{id}/profile")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<UserProfileResponse>> getUserProfile(@PathVariable Long id) {
        UserProfileResponse response = userProfileService.getProfile(id);
        return ResponseEntity.ok(ApiResponse.success("Lấy hồ sơ cá nhân của người dùng thành công", response));
    }

    @PutMapping("/{id}/profile")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<UserProfileResponse>> updateUserProfile(
            @PathVariable Long id,
            @Valid @RequestBody UserProfileRequest request) {
        UserProfileResponse response = userProfileService.updateProfile(id, request);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật hồ sơ cá nhân của người dùng thành công", response));
    }

    @GetMapping("/roles")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<List<RoleResponse>>> getAllRoles() {
        List<RoleResponse> response = userService.getAllRoles();
        return ResponseEntity.ok(ApiResponse.success("Lấy danh sách vai trò hệ thống thành công", response));
    }

    @GetMapping("/{id}/roles")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<List<RoleResponse>>> getUserRoles(@PathVariable Long id) {
        // Lấy danh sách vai trò của người dùng từ UserService
        UserResponse user = userService.getUserById(id);
        List<RoleResponse> response = user.getRoles().stream()
                .map(roleName -> {
                    try {
                        Role r = Role.valueOf(roleName);
                        return RoleResponse.builder()
                                .id((long) r.ordinal())
                                .name(r.name())
                                .description(r == Role.ADMIN ? "Quản trị viên hệ thống"
                                        : (r == Role.TEACHER ? "Giảng viên" : "Học viên"))
                                .build();
                    } catch (Exception e) {
                        return RoleResponse.builder().name(roleName).build();
                    }
                })
                .collect(Collectors.toList());
        return ResponseEntity.ok(ApiResponse.success("Lấy danh sách vai trò của người dùng thành công", response));
    }
}
