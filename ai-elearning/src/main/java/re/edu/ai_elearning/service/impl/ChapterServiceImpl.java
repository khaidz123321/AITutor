package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import re.edu.ai_elearning.dto.request.ChapterRequest;
import re.edu.ai_elearning.dto.request.ReorderChapterRequest;
import re.edu.ai_elearning.dto.response.ChapterResponse;
import re.edu.ai_elearning.entity.Chapter;
import re.edu.ai_elearning.entity.Course;
import re.edu.ai_elearning.entity.User;
import re.edu.ai_elearning.entity.enums.Role;
import re.edu.ai_elearning.exception.ConflictException;
import re.edu.ai_elearning.exception.ForbiddenException;
import re.edu.ai_elearning.exception.ResourceNotFoundException;
import re.edu.ai_elearning.mapper.ChapterMapper;
import re.edu.ai_elearning.repository.ChapterRepository;
import re.edu.ai_elearning.repository.CourseRepository;
import re.edu.ai_elearning.repository.ExerciseAttemptRepository;
import re.edu.ai_elearning.repository.ExerciseRepository;
import re.edu.ai_elearning.repository.LearningProfileRepository;
import re.edu.ai_elearning.repository.UserRepository;
import re.edu.ai_elearning.service.ChapterService;

import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class ChapterServiceImpl implements ChapterService {

    private final ChapterRepository chapterRepository;
    private final CourseRepository courseRepository;
    private final ExerciseRepository exerciseRepository;
    private final ExerciseAttemptRepository exerciseAttemptRepository;
    private final LearningProfileRepository learningProfileRepository;
    private final UserRepository userRepository;
    private final ChapterMapper chapterMapper;

    private boolean isChapterLockedForUser(Long userId, Chapter chapter) {
        // Kiểm tra quyền Admin/Teacher
        try {
            User user = userRepository.findById(userId).orElse(null);
            if (user != null && (Role.ADMIN == user.getRole() || Role.TEACHER == user.getRole())) {
                return false;
            }
        } catch (Exception e) {
            // bỏ qua
        }

        Long courseId = chapter.getCourse().getId();
        if (!learningProfileRepository.existsByUserIdAndCourseId(userId, courseId)) {
            throw new ForbiddenException("Bạn chưa đăng ký khóa học này");
        }

        List<Chapter> chapters = chapterRepository.findByCourseIdOrdered(courseId);
        int index = -1;
        for (int i = 0; i < chapters.size(); i++) {
            if (chapters.get(i).getId().equals(chapter.getId())) {
                index = i;
                break;
            }
        }

        if (index <= 0) {
            return false; // Chương đầu tiên
        }

        // Kiểm tra tất cả chương trước đó
        for (int j = 0; j < index; j++) {
            Chapter prevChapter = chapters.get(j);
            long exerciseCount = exerciseRepository.countByChapterId(prevChapter.getId());
            boolean completed = false;
            if (exerciseCount == 0) {
                completed = true;
            } else {
                completed = exerciseAttemptRepository.allExercisesCorrect(userId, prevChapter.getId());
            }

            if (!completed) {
                return true; // Bị khóa vì có chương trước chưa hoàn thành
            }
        }

        return false;
    }

    @Override
    @Transactional(readOnly = true)
    public ChapterResponse getChapterById(Long userId, Long id) {
        Chapter chapter = chapterRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy chương học"));

        boolean locked = isChapterLockedForUser(userId, chapter);
        if (locked) {
            throw new ForbiddenException("Chương học này chưa được mở khóa");
        }

        return chapterMapper.toResponse(chapter, false);
    }

    @Override
    @Transactional
    public ChapterResponse createChapter(Long courseId, ChapterRequest request) {
        Course course = courseRepository.findById(courseId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy khóa học"));

        if (chapterRepository.existsByOrderIndex(courseId, request.getOrderIndex())) {
            throw new ConflictException("Vị trí sắp xếp đã tồn tại");
        }

        Chapter chapter = Chapter.builder()
                .course(course)
                .subjectName(request.getSubjectName())
                .chapterNumber(request.getChapterNumber())
                .chapterName(request.getChapterName())
                .content(request.getContent())
                .orderIndex(request.getOrderIndex())
                .isLocked(request.getIsLocked() != null ? request.getIsLocked() : true)
                .build();

        chapter = chapterRepository.save(chapter);
        return chapterMapper.toResponse(chapter);
    }

    @Override
    @Transactional
    public ChapterResponse updateChapter(Long id, ChapterRequest request) {
        Chapter chapter = chapterRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy chương học"));

        // Kiểm tra order index conflict loại trừ chính nó
        chapterRepository.findByOrderIndexExcluding(chapter.getCourse().getId(), request.getOrderIndex(), id)
                .ifPresent(c -> {
                    throw new ConflictException("Vị trí sắp xếp đã tồn tại");
                });

        chapter.setSubjectName(request.getSubjectName());
        chapter.setChapterNumber(request.getChapterNumber());
        chapter.setChapterName(request.getChapterName());
        chapter.setContent(request.getContent());
        chapter.setOrderIndex(request.getOrderIndex());
        if (request.getIsLocked() != null) {
            chapter.setIsLocked(request.getIsLocked());
        }

        chapter = chapterRepository.save(chapter);
        return chapterMapper.toResponse(chapter);
    }

    @Override
    @Transactional
    public void deleteChapter(Long id) {
        Chapter chapter = chapterRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy chương học"));
        chapterRepository.delete(chapter);
    }

    @Override
    @Transactional
    public ChapterResponse reorderChapter(Long id, ReorderChapterRequest request) {
        Chapter chapter = chapterRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy chương học"));

        chapterRepository.findByOrderIndexExcluding(chapter.getCourse().getId(), request.getOrderIndex(), id)
                .ifPresent(c -> {
                    throw new ConflictException("Vị trí sắp xếp đã tồn tại");
                });

        chapter.setOrderIndex(request.getOrderIndex());
        chapter = chapterRepository.save(chapter);
        return chapterMapper.toResponse(chapter);
    }

    @Override
    @Transactional
    public void toggleChapterLock(Long id, Boolean isLocked) {
        Chapter chapter = chapterRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy chương học"));
        chapter.setIsLocked(isLocked);
        chapterRepository.save(chapter);
    }
}
