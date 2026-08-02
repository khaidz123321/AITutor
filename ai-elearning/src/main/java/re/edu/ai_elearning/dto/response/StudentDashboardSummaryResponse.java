package re.edu.ai_elearning.dto.response;

import lombok.*;
import java.util.List;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class StudentDashboardSummaryResponse {
    private Long studentId;
    private String studentName;
    private String email;
    private String role;
    
    private int totalCourses;
    private int avgProgress;
    private int hoursStudied;
    private String passedAttemptsRatio;

    private List<StudentCourseProgressDto> courses;
    private List<StudentAttemptDto> attempts;

    @Getter
    @Setter
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class StudentCourseProgressDto {
        private Long courseId;
        private String title;
        private String teacherName;
        private String level;
        private int totalChapters;
        private int completedChapters;
        private int progressPercent;
    }

    @Getter
    @Setter
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class StudentAttemptDto {
        private Long attemptId;
        private String exerciseTitle;
        private String courseName;
        private String attemptedAt;
        private String score;
        private String status;
        private Boolean isCorrect;
    }
}
