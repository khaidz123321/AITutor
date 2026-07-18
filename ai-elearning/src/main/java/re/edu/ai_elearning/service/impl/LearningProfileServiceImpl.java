package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import re.edu.ai_elearning.dto.request.UpdateLearningProgressRequest;
import re.edu.ai_elearning.dto.response.CourseResponse;
import re.edu.ai_elearning.dto.response.LearningProfileResponse;
import re.edu.ai_elearning.dto.response.PagedResponse;
import re.edu.ai_elearning.entity.Course;
import re.edu.ai_elearning.entity.LearningProfile;
import re.edu.ai_elearning.exception.ResourceNotFoundException;
import re.edu.ai_elearning.mapper.CourseMapper;
import re.edu.ai_elearning.mapper.LearningProfileMapper;
import re.edu.ai_elearning.repository.ChapterRepository;
import re.edu.ai_elearning.repository.CourseRepository;
import re.edu.ai_elearning.repository.LearningProfileRepository;
import re.edu.ai_elearning.repository.ReviewRepository;
import re.edu.ai_elearning.service.LearningProfileService;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class LearningProfileServiceImpl implements LearningProfileService {

    private final LearningProfileRepository learningProfileRepository;
    private final CourseRepository courseRepository;
    private final ChapterRepository chapterRepository;
    private final ReviewRepository reviewRepository;
    
    private final LearningProfileMapper learningProfileMapper;
    private final CourseMapper courseMapper;

    private CourseResponse buildCourseResponse(Course course) {
        long chapterCount = chapterRepository.countByCourseId(course.getId());
        long studentCount = learningProfileRepository.countStudentsByCourseId(course.getId());
        Double avgRating = reviewRepository.findAvgRatingByCourseId(course.getId()).orElse(0.0);
        return courseMapper.toResponse(course, chapterCount, studentCount, avgRating);
    }

    @Override
    @Transactional(readOnly = true)
    public LearningProfileResponse getProfile(Long userId, Long courseId) {
        LearningProfile profile = learningProfileRepository.findByUserIdAndCourseId(userId, courseId)
                .orElseThrow(() -> new ResourceNotFoundException("Hồ sơ học tập của bạn ở khóa học này chưa được tạo"));
        return learningProfileMapper.toResponse(profile);
    }

    @Override
    @Transactional(readOnly = true)
    public PagedResponse<LearningProfileResponse> getProfilesByCourse(Long courseId, int page, int size) {
        Pageable pageable = PageRequest.of(page - 1, size);
        Page<LearningProfile> profilePage = learningProfileRepository.findByCourseId(courseId, pageable);
        return PagedResponse.of(profilePage, learningProfileMapper::toResponse);
    }

    @Override
    @Transactional
    public LearningProfileResponse updateProgress(Long userId, UpdateLearningProgressRequest request) {
        LearningProfile profile = learningProfileRepository.findByUserIdAndCourseId(userId, request.getCourseId())
                .orElseThrow(() -> new ResourceNotFoundException("Hồ sơ học tập không tồn tại"));

        profile.setProgressPercent(request.getProgressPercent());
        profile.setLastStudied(LocalDateTime.now());
        profile = learningProfileRepository.save(profile);
        return learningProfileMapper.toResponse(profile);
    }

    @Override
    @Transactional(readOnly = true)
    public List<CourseResponse> getLearningPath(Long userId) {
        // Lấy tất cả khóa học đã đăng ký
        List<LearningProfile> enrolledProfiles = learningProfileRepository.findByUserId(userId);
        List<CourseResponse> path = new ArrayList<>();

        // Thêm các khóa học đã đăng ký
        for (LearningProfile lp : enrolledProfiles) {
            path.add(buildCourseResponse(lp.getCourse()));
        }

        // Gợi ý thêm các khóa học công khai chưa đăng ký (tối đa 5 khóa học)
        Set<Long> enrolledIds = enrolledProfiles.stream()
                .map(lp -> lp.getCourse().getId())
                .collect(Collectors.toSet());

        Pageable limit = PageRequest.of(0, 5);
        List<Course> visibleCourses = courseRepository.findAllVisible(limit).getContent();
        for (Course c : visibleCourses) {
            if (!enrolledIds.contains(c.getId())) {
                path.add(buildCourseResponse(c));
            }
        }

        return path;
    }
}
