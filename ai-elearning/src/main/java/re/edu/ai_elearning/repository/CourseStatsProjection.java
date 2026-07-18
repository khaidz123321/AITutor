package re.edu.ai_elearning.repository;

public interface CourseStatsProjection {
    Long getCourseId();
    Long getChapterCount();
    Long getStudentCount();
    Double getAvgRating();
}
