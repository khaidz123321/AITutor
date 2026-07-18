package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import re.edu.ai_elearning.dto.response.CourseSummaryResponse;
import re.edu.ai_elearning.dto.response.ReportDifficultyResponse;
import re.edu.ai_elearning.dto.response.ReportProgressResponse;
import re.edu.ai_elearning.entity.Course;
import re.edu.ai_elearning.entity.Exercise;
import re.edu.ai_elearning.entity.LearningProfile;
import re.edu.ai_elearning.entity.enums.BloomLevel;
import re.edu.ai_elearning.repository.*;
import re.edu.ai_elearning.service.ReportService;

import java.util.ArrayList;
import java.util.List;

@Service
@RequiredArgsConstructor
public class ReportServiceImpl implements ReportService {

    private final CourseRepository courseRepository;
    private final LearningProfileRepository learningProfileRepository;
    private final ReviewRepository reviewRepository;
    private final ExerciseRepository exerciseRepository;
    private final ExerciseAttemptRepository exerciseAttemptRepository;

    @Override
    @Transactional(readOnly = true)
    public List<ReportProgressResponse> getProgressReport() {
        List<Course> courses = courseRepository.findAll();
        List<ReportProgressResponse> report = new ArrayList<>();

        for (Course course : courses) {
            long totalStudents = learningProfileRepository.countStudentsByCourseId(course.getId());
            Double avgProgress = learningProfileRepository.findAvgProgressByCourseId(course.getId());
            
            // Lấy danh sách profiles để đếm người hoàn thành
            List<LearningProfile> profiles = learningProfileRepository.findByCourseId(course.getId(), org.springframework.data.domain.Pageable.unpaged()).getContent();
            long completedCount = profiles.stream()
                    .filter(lp -> lp.getProgressPercent() != null && lp.getProgressPercent() >= 100)
                    .count();

            report.add(ReportProgressResponse.builder()
                    .courseId(course.getId())
                    .courseTitle(course.getTitle())
                    .totalStudents((int) totalStudents)
                    .avgProgress(avgProgress != null ? avgProgress : 0.0)
                    .completedCount((int) completedCount)
                    .build());
        }

        return report;
    }

    @Override
    @Transactional(readOnly = true)
    public List<ReportDifficultyResponse> getDifficultyReport() {
        List<ReportDifficultyResponse> report = new ArrayList<>();

        for (BloomLevel bloomLevel : BloomLevel.values()) {
            // Lấy tất cả exercise thuộc BloomLevel này
            List<Exercise> exercises = exerciseRepository.findAll().stream()
                    .filter(e -> e.getBloomLevel() == bloomLevel)
                    .toList();

            long totalExercises = exercises.size();
            long totalAttempts = 0;
            long correctAttempts = 0;

            for (Exercise ex : exercises) {
                totalAttempts += exerciseAttemptRepository.countTotalAttempts(ex.getId());
                correctAttempts += exerciseAttemptRepository.countCorrectAttempts(ex.getId());
            }

            double avgSuccessRate = totalAttempts == 0 ? 0.0 : ((double) correctAttempts / totalAttempts) * 100;

            report.add(ReportDifficultyResponse.builder()
                    .bloomLevel(bloomLevel.name())
                    .exerciseCount((int) totalExercises)
                    .avgSuccessRate(avgSuccessRate)
                    .build());
        }

        return report;
    }

    @Override
    @Transactional(readOnly = true)
    public CourseSummaryResponse getCourseSummary() {
        long totalCourses = courseRepository.countTotalCourses();
        long totalStudents = learningProfileRepository.countTotalStudents();
        long totalReviews = reviewRepository.countTotalReviews();
        double avgRating = reviewRepository.findOverallAvgRating().orElse(0.0);

        return CourseSummaryResponse.builder()
                .totalCourses((int) totalCourses)
                .totalStudents((int) totalStudents)
                .totalReviews((int) totalReviews)
                .avgRating(avgRating)
                .build();
    }
}
