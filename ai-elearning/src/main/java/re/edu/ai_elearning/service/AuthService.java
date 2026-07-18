package re.edu.ai_elearning.service;

import re.edu.ai_elearning.dto.request.LoginRequest;
import re.edu.ai_elearning.dto.request.RegisterRequest;
import re.edu.ai_elearning.dto.request.RefreshTokenRequest;
import re.edu.ai_elearning.dto.request.ForgotPasswordRequest;
import re.edu.ai_elearning.dto.request.ResetPasswordRequest;
import re.edu.ai_elearning.dto.response.AuthResponse;
import re.edu.ai_elearning.dto.response.UserResponse;

public interface AuthService {
    UserResponse register(RegisterRequest request);
    AuthResponse login(LoginRequest request);
    AuthResponse refresh(RefreshTokenRequest request);
    void logout(String token);
    void forgotPassword(ForgotPasswordRequest request);
    void resetPassword(ResetPasswordRequest request);
    UserResponse getMe(Long userId);
}
