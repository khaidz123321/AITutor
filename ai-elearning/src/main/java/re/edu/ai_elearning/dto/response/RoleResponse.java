package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class RoleResponse {
    private Long id;
    private String name;
    private String description;
}
