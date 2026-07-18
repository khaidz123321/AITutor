package re.edu.ai_elearning.dto.request;

import jakarta.validation.constraints.NotEmpty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.List;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UpdateRolesRequest {

    @NotEmpty(message = "Danh sách role ID không được để trống")
    private List<Long> roleIds;
}
