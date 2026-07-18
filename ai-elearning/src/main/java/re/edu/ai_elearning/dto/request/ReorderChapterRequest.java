package re.edu.ai_elearning.dto.request;

import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ReorderChapterRequest {

    @NotNull(message = "Vị trí orderIndex mới không được để trống")
    private Integer orderIndex;
}
