package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.UUID;
import re.edu.ai_elearning.dto.request.CourseRequest;
import re.edu.ai_elearning.dto.response.ChapterResponse;
import re.edu.ai_elearning.dto.response.CourseResponse;
import re.edu.ai_elearning.dto.response.LearningProfileResponse;
import re.edu.ai_elearning.dto.response.PagedResponse;
import re.edu.ai_elearning.entity.Chapter;
import re.edu.ai_elearning.entity.Course;
import re.edu.ai_elearning.entity.LearningProfile;
import re.edu.ai_elearning.entity.User;
import re.edu.ai_elearning.entity.enums.Role;
import re.edu.ai_elearning.exception.BadRequestException;
import re.edu.ai_elearning.exception.ConflictException;
import re.edu.ai_elearning.exception.ForbiddenException;
import re.edu.ai_elearning.exception.ResourceNotFoundException;
import re.edu.ai_elearning.mapper.ChapterMapper;
import re.edu.ai_elearning.mapper.CourseMapper;
import re.edu.ai_elearning.mapper.LearningProfileMapper;
import re.edu.ai_elearning.repository.ChapterRepository;
import re.edu.ai_elearning.repository.CourseRepository;
import re.edu.ai_elearning.repository.ExerciseAttemptRepository;
import re.edu.ai_elearning.repository.ExerciseRepository;
import re.edu.ai_elearning.repository.LearningProfileRepository;
import re.edu.ai_elearning.repository.ReviewRepository;
import re.edu.ai_elearning.repository.UserRepository;
import re.edu.ai_elearning.service.CourseService;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class CourseServiceImpl implements CourseService {

    private final CourseRepository courseRepository;
    private final UserRepository userRepository;
    private final ChapterRepository chapterRepository;
    private final ExerciseRepository exerciseRepository;
    private final ExerciseAttemptRepository exerciseAttemptRepository;
    private final LearningProfileRepository learningProfileRepository;
    private final ReviewRepository reviewRepository;
    
    private final CourseMapper courseMapper;
    private final ChapterMapper chapterMapper;
    private final LearningProfileMapper learningProfileMapper;
    private final org.springframework.web.client.RestTemplate restTemplate;

    @org.springframework.beans.factory.annotation.Value("${ai.service.url}")
    private String aiServiceUrl;

    private java.util.Map<Long, re.edu.ai_elearning.repository.CourseStatsProjection> fetchStatsForCourses(List<Course> courses) {
        if (courses.isEmpty()) return java.util.Collections.emptyMap();
        List<Long> ids = courses.stream().map(Course::getId).collect(Collectors.toList());
        return courseRepository.findStatsByCourseIds(ids).stream()
                .collect(Collectors.toMap(re.edu.ai_elearning.repository.CourseStatsProjection::getCourseId, s -> s));
    }

    private CourseResponse buildCourseResponseWithStats(Course course, java.util.Map<Long, re.edu.ai_elearning.repository.CourseStatsProjection> statsMap) {
        re.edu.ai_elearning.repository.CourseStatsProjection stats = statsMap.get(course.getId());
        long chapters = stats != null ? stats.getChapterCount() : 0;
        long students = stats != null ? stats.getStudentCount() : 0;
        Double rating = stats != null ? stats.getAvgRating() : 0.0;
        return courseMapper.toResponse(course, chapters, students, rating);
    }

    private CourseResponse buildCourseResponse(Course course) {
        long chapterCount = chapterRepository.countByCourseId(course.getId());
        long studentCount = learningProfileRepository.countStudentsByCourseId(course.getId());
        Double avgRating = reviewRepository.findAvgRatingByCourseId(course.getId()).orElse(0.0);
        return courseMapper.toResponse(course, chapterCount, studentCount, avgRating);
    }

    @Override
    @Transactional(readOnly = true)
    public PagedResponse<CourseResponse> getAllPublicCourses(String keyword, int page, int size) {
        Pageable pageable = PageRequest.of(page - 1, size);
        Page<Course> coursePage;
        if (keyword != null && !keyword.isBlank()) {
            coursePage = courseRepository.searchByTitle(keyword, pageable);
        } else {
            coursePage = courseRepository.findAllVisible(pageable);
        }
        java.util.Map<Long, re.edu.ai_elearning.repository.CourseStatsProjection> statsMap = fetchStatsForCourses(coursePage.getContent());
        return PagedResponse.of(coursePage, course -> buildCourseResponseWithStats(course, statsMap));
    }

    @Override
    @Transactional(readOnly = true)
    public PagedResponse<CourseResponse> getAllCoursesForAdmin(int page, int size) {
        Pageable pageable = PageRequest.of(page - 1, size);
        Page<Course> coursePage = courseRepository.findAllCourses(pageable);
        java.util.Map<Long, re.edu.ai_elearning.repository.CourseStatsProjection> statsMap = fetchStatsForCourses(coursePage.getContent());
        return PagedResponse.of(coursePage, course -> buildCourseResponseWithStats(course, statsMap));
    }

    @Override
    @Transactional(readOnly = true)
    public CourseResponse getCourseById(Long id) {
        Course course = courseRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy khóa học"));
        java.util.Map<Long, re.edu.ai_elearning.repository.CourseStatsProjection> statsMap = fetchStatsForCourses(java.util.Collections.singletonList(course));
        return buildCourseResponseWithStats(course, statsMap);
    }

    @Override
    @Transactional(readOnly = true)
    public List<CourseResponse> getMyEnrolledCourses(Long userId) {
        List<LearningProfile> profiles = learningProfileRepository.findByUserId(userId);
        List<Course> courses = profiles.stream().map(LearningProfile::getCourse).collect(Collectors.toList());
        java.util.Map<Long, re.edu.ai_elearning.repository.CourseStatsProjection> statsMap = fetchStatsForCourses(courses);
        return courses.stream()
                .map(course -> buildCourseResponseWithStats(course, statsMap))
                .collect(Collectors.toList());
    }

    @Override
    @Transactional
    public LearningProfileResponse enrollCourse(Long userId, Long courseId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));
        Course course = courseRepository.findById(courseId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy khóa học"));

        if (!Boolean.TRUE.equals(course.getIsVisible())) {
            throw new BadRequestException("Khóa học này hiện không công khai");
        }

        if (learningProfileRepository.existsByUserIdAndCourseId(userId, courseId)) {
            throw new ConflictException("Bạn đã đăng ký khóa học này");
        }

        LearningProfile profile = LearningProfile.builder()
                .user(user)
                .course(course)
                .progressPercent(0)
                .enrolledAt(LocalDateTime.now())
                .lastStudied(LocalDateTime.now())
                .build();

        profile = learningProfileRepository.save(profile);
        return learningProfileMapper.toResponse(profile);
    }

    @Override
    @Transactional(readOnly = true)
    public List<ChapterResponse> getCourseChapters(Long userId, Long courseId) {
        // Kiểm tra quyền: Admin/Teacher được xem toàn bộ không bị khóa
        boolean isAdminOrTeacher = false;
        try {
            User user = userRepository.findById(userId).orElse(null);
            isAdminOrTeacher = user != null && (Role.ADMIN == user.getRole() || Role.TEACHER == user.getRole());
        } catch (Exception e) {
            // bỏ qua
        }

        if (!isAdminOrTeacher && !learningProfileRepository.existsByUserIdAndCourseId(userId, courseId)) {
            throw new ForbiddenException("Bạn chưa đăng ký khóa học này");
        }

        List<Chapter> chapters = chapterRepository.findByCourseIdOrdered(courseId);
        if (chapters.isEmpty()) {
            return Collections.emptyList();
        }

        List<ChapterResponse> responseList = new ArrayList<>();
        
        // Chương đầu tiên mặc định mở khóa
        responseList.add(chapterMapper.toResponse(chapters.get(0), false));

        boolean previousChapterUnlocked = true;
        for (int i = 1; i < chapters.size(); i++) {
            Chapter chapter = chapters.get(i);
            boolean currentLocked = true;

            if (isAdminOrTeacher) {
                currentLocked = false;
            } else if (previousChapterUnlocked) {
                // Kiểm tra chương trước đã hoàn thành bài tập chưa
                Chapter prevChapter = chapters.get(i - 1);
                long exerciseCount = exerciseRepository.countByChapterId(prevChapter.getId());
                
                boolean prevCompleted = false;
                if (exerciseCount == 0) {
                    prevCompleted = true; // Không có bài tập thì tự qua
                } else {
                    prevCompleted = exerciseAttemptRepository.allExercisesCorrect(userId, prevChapter.getId());
                }

                if (prevCompleted) {
                    currentLocked = false;
                } else {
                    previousChapterUnlocked = false; // Các chương sau chắc chắn khóa
                }
            }

            responseList.add(chapterMapper.toResponse(chapter, currentLocked));
        }

        return responseList;
    }

    @Override
    @Transactional
    public CourseResponse createCourse(Long userId, CourseRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));

        Course course = Course.builder()
                .title(request.getTitle())
                .description(request.getDescription())
                .level(request.getLevel())
                .thumbnailUrl(request.getThumbnailUrl())
                .lecturePdf(request.getLecturePdf())
                .aiPersona(request.getAiPersona())
                .isVisible(request.getIsVisible() != null ? request.getIsVisible() : true)
                .createdBy(user)
                .build();

        course = courseRepository.save(course);
        
        try {
            org.springframework.http.HttpHeaders headers = new org.springframework.http.HttpHeaders();
            headers.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
            
            java.util.Map<String, Object> requestBody = new java.util.HashMap<>();
            requestBody.put("courseTitle", course.getTitle());
            requestBody.put("courseCode", "course_" + course.getId());
            requestBody.put("personaContent", course.getAiPersona());
            
            org.springframework.http.HttpEntity<java.util.Map<String, Object>> entity = new org.springframework.http.HttpEntity<>(requestBody, headers);
            String url = aiServiceUrl + "/v1/courses/init-folder";
            
            org.springframework.http.ResponseEntity<java.util.Map> response = restTemplate.postForEntity(url, entity, java.util.Map.class);
            if (!response.getStatusCode().is2xxSuccessful()) {
                log.warn("Tạo thư mục môn học thất bại");
            }
        } catch (Exception e) {
            log.error("Lỗi tạo thư mục: ", e);
        }
        
        return buildCourseResponse(course);
    }

    @Override
    @Transactional
    public CourseResponse updateCourse(Long id, CourseRequest request) {
        Course course = courseRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy khóa học"));

        course.setTitle(request.getTitle());
        course.setDescription(request.getDescription());
        course.setLevel(request.getLevel());
        course.setThumbnailUrl(request.getThumbnailUrl());
        course.setLecturePdf(request.getLecturePdf());
        course.setAiPersona(request.getAiPersona());
        if (request.getIsVisible() != null) {
            course.setIsVisible(request.getIsVisible());
        }

        course = courseRepository.save(course);
        return buildCourseResponse(course);
    }

    @Override
    @Transactional
    public void deleteCourse(Long id) {
        Course course = courseRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy khóa học"));
        courseRepository.delete(course);
    }

    @Override
    @Transactional
    public void toggleCourseVisibility(Long id, Boolean isVisible) {
        Course course = courseRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy khóa học"));
        course.setIsVisible(isVisible);
        courseRepository.save(course);
    }

    @Override
    @Transactional
    public CourseResponse uploadLecturePdf(Long id, MultipartFile file) {
        Course course = courseRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy khóa học"));

        if (file.isEmpty()) {
            throw new BadRequestException("Tập tin tải lên trống");
        }

        try {
            String uploadDirStr = "src/main/resources/static/uploads/";
            File uploadDir = new File(uploadDirStr);
            if (!uploadDir.exists()) {
                uploadDir.mkdirs();
            }

            String originalFileName = file.getOriginalFilename();
            String newFileName = UUID.randomUUID().toString() + "_" + (originalFileName != null ? originalFileName : "document");

            Path targetPath = Paths.get(uploadDirStr + newFileName);
            Files.copy(file.getInputStream(), targetPath, StandardCopyOption.REPLACE_EXISTING);

            String fileUrl = "/uploads/" + newFileName;
            course.setLecturePdf(fileUrl);
            course.setOcrStatus("PENDING");
            course = courseRepository.save(course);

            // Gửi file sang FastAPI để chạy luồng OCR ngầm
            try {
                org.springframework.http.HttpHeaders headers = new org.springframework.http.HttpHeaders();
                headers.setContentType(org.springframework.http.MediaType.MULTIPART_FORM_DATA);
                headers.set("x-user-id", course.getCreatedBy().getId().toString());

                org.springframework.util.MultiValueMap<String, Object> body = new org.springframework.util.LinkedMultiValueMap<>();
                body.add("subject", "course_" + course.getId());
                body.add("file", new org.springframework.core.io.FileSystemResource(targetPath.toFile()));

                org.springframework.http.HttpEntity<org.springframework.util.MultiValueMap<String, Object>> requestEntity = new org.springframework.http.HttpEntity<>(body, headers);
                String url = aiServiceUrl + "/documents/";
                
                org.springframework.http.ResponseEntity<String> response = restTemplate.postForEntity(url, requestEntity, String.class);
                if (!response.getStatusCode().is2xxSuccessful()) {
                    log.warn("Gọi FastAPI xử lý RAG thất bại: " + response.getBody());
                } else {
                    log.info("Đã gửi file cho AI OCR thành công. CourseID: {}", course.getId());
                }
            } catch (Exception e) {
                log.error("Lỗi giao tiếp với AI service: ", e);
            }

            return buildCourseResponse(course);
        } catch (Exception e) {
            log.error("Lỗi khi tải lên file PDF: ", e);
            throw new BadRequestException("Không thể lưu tập tin tải lên: " + e.getMessage());
        }
    }
}
