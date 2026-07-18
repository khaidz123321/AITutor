package re.edu.ai_elearning.service;

import re.edu.ai_elearning.dto.request.ChangePasswordRequest;
import re.edu.ai_elearning.dto.request.RegisterRequest;
import re.edu.ai_elearning.dto.request.UpdateUserRequest;
import re.edu.ai_elearning.dto.request.UpdateRolesRequest;
import re.edu.ai_elearning.dto.response.PagedResponse;
import re.edu.ai_elearning.dto.response.UserResponse;
import re.edu.ai_elearning.dto.response.RoleResponse;

import java.util.List;

public interface UserService {
    PagedResponse<UserResponse> getAllUsers(Boolean isActive, int page, int size);
    UserResponse getUserById(Long id);
    UserResponse createUser(RegisterRequest request, List<Long> roleIds);
    UserResponse updateUser(Long id, UpdateUserRequest request);
    void toggleUserStatus(Long id, Boolean isActive);
    void deleteUser(Long id, Long currentUserId);
    void changePassword(Long userId, ChangePasswordRequest request);
    UserResponse updateSelf(Long userId, UpdateUserRequest request);

    List<RoleResponse> getAllRoles();
    void assignRoles(Long userId, UpdateRolesRequest request);
    void revokeRole(Long userId, Long roleId);
}
