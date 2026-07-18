package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import re.edu.ai_elearning.dto.request.AnswerSubmitRequest;
import re.edu.ai_elearning.dto.request.ExerciseRequest;
import re.edu.ai_elearning.dto.response.ExerciseResponse;
import re.edu.ai_elearning.dto.response.ExerciseResultResponse;
import re.edu.ai_elearning.dto.response.ExerciseStatsResponse;
import re.edu.ai_elearning.entity.*;
import re.edu.ai_elearning.entity.enums.NotificationType;
import re.edu.ai_elearning.exception.ConflictException;
import re.edu.ai_elearning.exception.ForbiddenException;
import re.edu.ai_elearning.exception.ResourceNotFoundException;
import re.edu.ai_elearning.mapper.ExerciseMapper;
import re.edu.ai_elearning.repository.*;
import re.edu.ai_elearning.service.ExerciseService;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ExerciseServiceImpl implements ExerciseService {

    private final ExerciseRepository exerciseRepository;
    private final UserRepository userRepository;
    private final ChapterRepository chapterRepository;
    private final ExerciseAttemptRepository exerciseAttemptRepository;
    private final LearningProfileRepository learningProfileRepository;
    private final NotificationRepository notificationRepository;
    private final ExerciseMapper exerciseMapper;
    private final re.edu.ai_elearning.service.NotificationService notificationService;

    @Override
    @Transactional(readOnly = true)
    public ExerciseResponse getExerciseById(Long userId, Long id) {
        Exercise exercise = exerciseRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy bài tập"));

        // Kiểm tra xem chapter có bị khóa với user này không
        // (Nếu học viên được phép gọi API này tức là họ đã mở khóa chapter, nhưng để an toàn ta kiểm tra qua logic lock)
        // (Ta bỏ qua check phức tạp để tối ưu tốc độ, nhưng giữ check cơ bản xem họ có đăng ký học không)
        Long courseId = exercise.getChapter().getCourse().getId();
        if (!learningProfileRepository.existsByUserIdAndCourseId(userId, courseId)) {
            throw new ForbiddenException("Bạn chưa đăng ký khóa học này");
        }

        return exerciseMapper.toResponse(exercise);
    }

    @Override
    @Transactional
    public ExerciseResultResponse submitAnswer(Long userId, Long id, AnswerSubmitRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));
        Exercise exercise = exerciseRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy bài tập"));

        Chapter chapter = exercise.getChapter();
        Course course = chapter.getCourse();

        // Kiểm tra xem user có đăng ký khóa học không
        if (!learningProfileRepository.existsByUserIdAndCourseId(userId, course.getId())) {
            throw new ForbiddenException("Bạn chưa đăng ký khóa học này");
        }

        boolean isCorrect = exercise.getCorrectAnswer().trim().equalsIgnoreCase(request.getAnswer().trim());

        // Lưu lượt làm bài
        ExerciseAttempt attempt = ExerciseAttempt.builder()
                .user(user)
                .exercise(exercise)
                .submittedAnswer(request.getAnswer())
                .isCorrect(isCorrect)
                .attemptedAt(LocalDateTime.now())
                .build();
        exerciseAttemptRepository.save(attempt);

        boolean chapterJustUnlocked = false;
        String nextChapterName = null;

        if (isCorrect) {
            // Cập nhật thời điểm học lần cuối
            learningProfileRepository.findByUserIdAndCourseId(userId, course.getId())
                    .ifPresent(lp -> {
                        lp.setLastStudied(LocalDateTime.now());
                        learningProfileRepository.save(lp);
                    });

            // Kiểm tra xem đã hoàn thành toàn bộ bài tập trong chapter này chưa
            boolean isChapterComplete = exerciseAttemptRepository.allExercisesCorrect(userId, chapter.getId());
            if (isChapterComplete) {
                // Tìm chương tiếp theo để mở khóa
                List<Chapter> chapters = chapterRepository.findByCourseIdOrdered(course.getId());
                int currentChapterIndex = -1;
                for (int i = 0; i < chapters.size(); i++) {
                    if (chapters.get(i).getId().equals(chapter.getId())) {
                        currentChapterIndex = i;
                        break;
                    }
                }

                if (currentChapterIndex != -1 && currentChapterIndex < chapters.size() - 1) {
                    Chapter nextChapter = chapters.get(currentChapterIndex + 1);
                    if (Boolean.TRUE.equals(nextChapter.getIsLocked())) {
                        nextChapter.setIsLocked(false);
                        chapterRepository.save(nextChapter);

                        chapterJustUnlocked = true;
                        nextChapterName = nextChapter.getChapterName();

                        // Tạo thông báo cho học viên
                        notificationService.createAndSendNotification(user,
                                "Chúc mừng! Bạn đã hoàn thành tất cả bài tập chương '" + 
                                        chapter.getChapterName() + "' và mở khóa chương mới '" + 
                                        nextChapterName + "'!",
                                NotificationType.CHAPTER_UNLOCKED);
                    }
                }

                // Cập nhật tiến độ của LearningProfile
                updateCourseProgress(userId, course, chapters);
            }
        }

        // Tìm bài tập tiếp theo chưa làm đúng trong chương
        Long nextExerciseId = findNextUnsolvedExercise(userId, chapter.getId(), exercise.getId());

        String feedbackMsg = isCorrect ? "Đáp án chính xác!" : "Đáp án chưa chính xác. Hãy thử lại hoặc hỏi Chat AI trợ giúp.";

        return ExerciseResultResponse.builder()
                .isCorrect(isCorrect)
                .message(feedbackMsg)
                .nextExerciseId(nextExerciseId)
                .chapterUnlocked(chapterJustUnlocked)
                .chapterUnlockedName(nextChapterName)
                .build();
    }

    private void updateCourseProgress(Long userId, Course course, List<Chapter> chapters) {
        learningProfileRepository.findByUserIdAndCourseId(userId, course.getId())
                .ifPresent(lp -> {
                    long totalChapters = chapters.size();
                    if (totalChapters == 0) return;

                    long completedChapters = 0;
                    for (Chapter ch : chapters) {
                        long exerciseCount = exerciseRepository.countByChapterId(ch.getId());
                        if (exerciseCount == 0) {
                            completedChapters++; // Không có bài tập coi như hoàn thành chương
                        } else if (exerciseAttemptRepository.allExercisesCorrect(userId, ch.getId())) {
                            completedChapters++;
                        }
                    }

                    int progress = (int) ((completedChapters * 100) / totalChapters);
                    lp.setProgressPercent(progress);
                    learningProfileRepository.save(lp);
                });
    }

    private Long findNextUnsolvedExercise(Long userId, Long chapterId, Long currentExerciseId) {
        List<Exercise> exercises = exerciseRepository.findByChapterIdOrdered(chapterId);
        int currentIndex = -1;
        for (int i = 0; i < exercises.size(); i++) {
            if (exercises.get(i).getId().equals(currentExerciseId)) {
                currentIndex = i;
                break;
            }
        }

        // Kiểm tra từ phần tử tiếp theo
        for (int i = currentIndex + 1; i < exercises.size(); i++) {
            Exercise ex = exercises.get(i);
            // Xem có attempt đúng nào chưa
            List<ExerciseAttempt> attempts = exerciseAttemptRepository.findByUserIdAndExerciseId(userId, ex.getId());
            boolean correct = attempts.stream().anyMatch(ExerciseAttempt::getIsCorrect);
            if (!correct) {
                return ex.getId();
            }
        }

        // Nếu đi đến cuối mà vẫn có câu chưa giải ở đầu
        for (int i = 0; i < currentIndex; i++) {
            Exercise ex = exercises.get(i);
            List<ExerciseAttempt> attempts = exerciseAttemptRepository.findByUserIdAndExerciseId(userId, ex.getId());
            boolean correct = attempts.stream().anyMatch(ExerciseAttempt::getIsCorrect);
            if (!correct) {
                return ex.getId();
            }
        }

        return null; // Đã giải đúng hết
    }

    @Override
    @Transactional(readOnly = true)
    public ExerciseResponse getNextExercise(Long userId, Long chapterId) {
        // Tìm câu hỏi đầu tiên chưa làm đúng trong chương
        List<Exercise> exercises = exerciseRepository.findByChapterIdOrdered(chapterId);
        for (Exercise ex : exercises) {
            List<ExerciseAttempt> attempts = exerciseAttemptRepository.findByUserIdAndExerciseId(userId, ex.getId());
            boolean correct = attempts.stream().anyMatch(ExerciseAttempt::getIsCorrect);
            if (!correct) {
                return exerciseMapper.toResponse(ex);
            }
        }
        // Nếu đã giải hết, trả về câu cuối hoặc câu đầu
        if (!exercises.isEmpty()) {
            return exerciseMapper.toResponse(exercises.get(0));
        }
        throw new ResourceNotFoundException("Chương này chưa có bài tập nào");
    }

    @Override
    @Transactional(readOnly = true)
    public List<ExerciseResponse> getExercisesByChapter(Long userId, Long chapterId) {
        if (!chapterRepository.existsById(chapterId)) {
            throw new ResourceNotFoundException("Không tìm thấy chương học");
        }
        return exerciseRepository.findByChapterIdOrdered(chapterId).stream()
                .map(exerciseMapper::toResponse)
                .collect(Collectors.toList());
    }

    @Override
    @Transactional
    public ExerciseResponse createExercise(Long chapterId, ExerciseRequest request) {
        Chapter chapter = chapterRepository.findById(chapterId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy chương học"));

        if (exerciseRepository.existsByChapterIdAndCode(chapterId, request.getExerciseCode())) {
            throw new ConflictException("Mã bài tập đã tồn tại trong chương này");
        }

        Exercise exercise = Exercise.builder()
                .chapter(chapter)
                .exerciseCode(request.getExerciseCode())
                .exerciseName(request.getExerciseName())
                .difficulty(request.getDifficulty())
                .bloomLevel(request.getBloomLevel())
                .question(request.getQuestion())
                .correctAnswer(request.getCorrectAnswer())
                .build();

        exercise = exerciseRepository.save(exercise);
        return exerciseMapper.toResponse(exercise);
    }

    @Override
    @Transactional
    public ExerciseResponse updateExercise(Long id, ExerciseRequest request) {
        Exercise exercise = exerciseRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy bài tập"));

        if (exerciseRepository.existsByChapterIdAndCodeExcluding(exercise.getChapter().getId(), request.getExerciseCode(), id)) {
            throw new ConflictException("Mã bài tập đã tồn tại trong chương này");
        }

        exercise.setExerciseCode(request.getExerciseCode());
        exercise.setExerciseName(request.getExerciseName());
        exercise.setDifficulty(request.getDifficulty());
        exercise.setBloomLevel(request.getBloomLevel());
        exercise.setQuestion(request.getQuestion());
        exercise.setCorrectAnswer(request.getCorrectAnswer());

        exercise = exerciseRepository.save(exercise);
        return exerciseMapper.toResponse(exercise);
    }

    @Override
    @Transactional
    public void deleteExercise(Long id) {
        Exercise exercise = exerciseRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy bài tập"));
        exerciseRepository.delete(exercise);
    }

    @Override
    @Transactional(readOnly = true)
    public ExerciseStatsResponse getExerciseStats(Long id) {
        Exercise exercise = exerciseRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy bài tập"));

        long total = exerciseAttemptRepository.countTotalAttempts(id);
        long correct = exerciseAttemptRepository.countCorrectAttempts(id);
        long incorrect = total - correct;
        double rate = total == 0 ? 0.0 : ((double) correct / total) * 100;

        return ExerciseStatsResponse.builder()
                .exerciseId(id)
                .exerciseCode(exercise.getExerciseCode())
                .exerciseName(exercise.getExerciseName())
                .totalAttempts(total)
                .correctCount(correct)
                .incorrectCount(incorrect)
                .successRate(rate)
                .build();
    }
}
