package re.edu.ai_elearning.dto.request;

import jakarta.validation.constraints.Past;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDate;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserProfileRequest {

    @Size(max = 500, message = "URL avatar quá dài")
    private String avatarUrl;

    @Past(message = "Ngày sinh phải ở trong quá khứ")
    private LocalDate dateOfBirth;

    @Size(max = 10, message = "Giới tính quá dài")
    private String gender;

    @Size(max = 20, message = "Số điện thoại quá dài")
    private String phone;

    @Size(max = 500, message = "Địa chỉ quá dài")
    private String address;

    @Size(max = 100, message = "Thành phố quá dài")
    private String city;

    @Size(max = 100, message = "Quốc gia quá dài")
    private String country;

    private String bio;
}
