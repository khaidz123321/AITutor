package re.edu.ai_elearning.service;

import re.edu.ai_elearning.dto.request.CourseRequest;
import re.edu.ai_elearning.dto.response.ChapterResponse;
import re.edu.ai_elearning.dto.response.CourseResponse;
import re.edu.ai_elearning.dto.response.LearningProfileResponse;
import re.edu.ai_elearning.dto.response.PagedResponse;

import java.util.List;

public interface CourseService {
    PagedResponse<CourseResponse> getAllPublicCourses(String keyword, int page, int size);
    PagedResponse<CourseResponse> getAllCoursesForAdmin(int page, int size);
    CourseResponse getCourseById(Long id);
    List<CourseResponse> getMyEnrolledCourses(Long userId);
    LearningProfileResponse enrollCourse(Long userId, Long courseId);
    List<ChapterResponse> getCourseChapters(Long userId, Long courseId);
    
    // Admin/Teacher functions
    CourseResponse createCourse(Long userId, CourseRequest request);
    CourseResponse updateCourse(Long id, CourseRequest request);
    void deleteCourse(Long id);
    void toggleCourseVisibility(Long id, Boolean isVisible);
    CourseResponse uploadLecturePdf(Long id, org.springframework.web.multipart.MultipartFile file);
}
