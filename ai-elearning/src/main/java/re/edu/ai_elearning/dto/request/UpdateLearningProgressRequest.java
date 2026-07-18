package re.edu.ai_elearning.dto.request;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
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
public class UpdateLearningProgressRequest {

    @NotNull(message = "ID khóa học không được để trống")
    private Long courseId;

    @NotNull(message = "Phần trăm tiến độ không được để trống")
    @Min(value = 0, message = "Tiến độ không được nhỏ hơn 0%")
    @Max(value = 100, message = "Tiến độ không được lớn hơn 100%")
    private Integer progressPercent;
}
