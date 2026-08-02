package re.edu.ai_elearning.dto.response;

import lombok.*;

import java.time.LocalDateTime;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class NewsResponse {

    private Long id;
    private String title;
    private String category;
    private String summary;
    private String content;
    private String imageUrl;
    private Boolean isSpotlight;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
