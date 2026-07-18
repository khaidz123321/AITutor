package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import re.edu.ai_elearning.dto.request.AnswerSubmitRequest;
import re.edu.ai_elearning.dto.request.ExerciseAiRequest;
import re.edu.ai_elearning.dto.response.ExerciseAiResponse;
import re.edu.ai_elearning.dto.response.ExerciseAiResultResponse;
import re.edu.ai_elearning.dto.response.ExerciseAiStatsResponse;
import re.edu.ai_elearning.entity.*;
import re.edu.ai_elearning.exception.ConflictException;
import re.edu.ai_elearning.exception.ForbiddenException;
import re.edu.ai_elearning.exception.ResourceNotFoundException;
import re.edu.ai_elearning.mapper.ExerciseAiMapper;
import re.edu.ai_elearning.repository.*;
import re.edu.ai_elearning.service.ExerciseAiService;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.core.io.ByteArrayResource;
import re.edu.ai_elearning.exception.BadRequestException;
import re.edu.ai_elearning.entity.enums.Difficulty;
import re.edu.ai_elearning.entity.enums.BloomLevel;
import java.util.Map;
import java.util.ArrayList;

@Slf4j
@Service
@RequiredArgsConstructor
public class ExerciseAiServiceImpl implements ExerciseAiService {

    private final ExerciseAiRepository exerciseAiRepository;
    private final UserRepository userRepository;
    private final ChapterRepository chapterRepository;
    private final ExerciseAiAttemptRepository exerciseAiAttemptRepository;
    private final LearningProfileRepository learningProfileRepository;
    private final ExerciseAiMapper exerciseAiMapper;
    private final RestTemplate restTemplate;

    @Value("${ai.service.url}")
    private String aiServiceUrl;

    @Value("${ai.service.api-key}")
    private String aiApiKey;

    @Override
    @Transactional(readOnly = true)
    public ExerciseAiResponse getExerciseById(Long userId, Long id) {
        ExerciseAi exercise = exerciseAiRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy bài tập AI"));

        Long courseId = exercise.getChapter().getCourse().getId();
        if (!learningProfileRepository.existsByUserIdAndCourseId(userId, courseId)) {
            throw new ForbiddenException("Bạn chưa đăng ký khóa học này");
        }

        return exerciseAiMapper.toResponse(exercise);
    }

    @Override
    @Transactional
    public ExerciseAiResultResponse submitAnswer(Long userId, Long id, AnswerSubmitRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));
        ExerciseAi exercise = exerciseAiRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy bài tập AI"));

        Chapter chapter = exercise.getChapter();
        Course course = chapter.getCourse();

        if (!learningProfileRepository.existsByUserIdAndCourseId(userId, course.getId())) {
            throw new ForbiddenException("Bạn chưa đăng ký khóa học này");
        }

        boolean isCorrect = exercise.getCorrectAnswer().trim().equalsIgnoreCase(request.getAnswer().trim());

        ExerciseAiAttempt attempt = ExerciseAiAttempt.builder()
                .user(user)
                .exerciseAi(exercise)
                .submittedAnswer(request.getAnswer())
                .isCorrect(isCorrect)
                .attemptedAt(LocalDateTime.now())
                .build();
        exerciseAiAttemptRepository.save(attempt);

        if (isCorrect) {
            learningProfileRepository.findByUserIdAndCourseId(userId, course.getId())
                    .ifPresent(lp -> {
                        lp.setLastStudied(LocalDateTime.now());
                        learningProfileRepository.save(lp);
                    });
        }

        Long nextExerciseId = findNextUnsolvedExercise(userId, chapter.getId(), exercise.getId());
        String feedbackMsg = isCorrect ? "Đáp án chính xác!" : "Đáp án chưa chính xác. Hãy thử lại hoặc hỏi Chat AI trợ giúp.";

        return ExerciseAiResultResponse.builder()
                .isCorrect(isCorrect)
                .message(feedbackMsg)
                .nextExerciseId(nextExerciseId)
                .chapterUnlocked(false)
                .chapterUnlockedName(null)
                .build();
    }

    private Long findNextUnsolvedExercise(Long userId, Long chapterId, Long currentExerciseId) {
        List<ExerciseAi> exercises = exerciseAiRepository.findByChapterIdOrdered(chapterId);
        int currentIndex = -1;
        for (int i = 0; i < exercises.size(); i++) {
            if (exercises.get(i).getId().equals(currentExerciseId)) {
                currentIndex = i;
                break;
            }
        }

        for (int i = currentIndex + 1; i < exercises.size(); i++) {
            ExerciseAi ex = exercises.get(i);
            List<ExerciseAiAttempt> attempts = exerciseAiAttemptRepository.findByUserIdAndExerciseId(userId, ex.getId());
            boolean correct = attempts.stream().anyMatch(ExerciseAiAttempt::getIsCorrect);
            if (!correct) {
                return ex.getId();
            }
        }

        for (int i = 0; i < currentIndex; i++) {
            ExerciseAi ex = exercises.get(i);
            List<ExerciseAiAttempt> attempts = exerciseAiAttemptRepository.findByUserIdAndExerciseId(userId, ex.getId());
            boolean correct = attempts.stream().anyMatch(ExerciseAiAttempt::getIsCorrect);
            if (!correct) {
                return ex.getId();
            }
        }

        return null;
    }

    @Override
    @Transactional(readOnly = true)
    public ExerciseAiResponse getNextExercise(Long userId, Long chapterId) {
        List<ExerciseAi> exercises = exerciseAiRepository.findByChapterIdOrdered(chapterId);
        for (ExerciseAi ex : exercises) {
            List<ExerciseAiAttempt> attempts = exerciseAiAttemptRepository.findByUserIdAndExerciseId(userId, ex.getId());
            boolean correct = attempts.stream().anyMatch(ExerciseAiAttempt::getIsCorrect);
            if (!correct) {
                return exerciseAiMapper.toResponse(ex);
            }
        }
        if (!exercises.isEmpty()) {
            return exerciseAiMapper.toResponse(exercises.get(0));
        }
        throw new ResourceNotFoundException("Chương này chưa có bài tập AI nào");
    }

    @Override
    @Transactional(readOnly = true)
    public List<ExerciseAiResponse> getExercisesByChapter(Long userId, Long chapterId) {
        if (!chapterRepository.existsById(chapterId)) {
            throw new ResourceNotFoundException("Không tìm thấy chương học");
        }
        return exerciseAiRepository.findByChapterIdOrdered(chapterId).stream()
                .map(exerciseAiMapper::toResponse)
                .collect(Collectors.toList());
    }

    @Override
    @Transactional
    public ExerciseAiResponse createExercise(Long chapterId, ExerciseAiRequest request) {
        Chapter chapter = chapterRepository.findById(chapterId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy chương học"));

        if (exerciseAiRepository.existsByChapterIdAndCode(chapterId, request.getExerciseCode())) {
            throw new ConflictException("Mã bài tập AI đã tồn tại trong chương này");
        }

        ExerciseAi exercise = ExerciseAi.builder()
                .chapter(chapter)
                .exerciseCode(request.getExerciseCode())
                .exerciseName(request.getExerciseName())
                .difficulty(request.getDifficulty())
                .bloomLevel(request.getBloomLevel())
                .question(request.getQuestion())
                .correctAnswer(request.getCorrectAnswer())
                .build();

        exercise = exerciseAiRepository.save(exercise);
        return exerciseAiMapper.toResponse(exercise);
    }

    @Override
    @Transactional
    public ExerciseAiResponse updateExercise(Long id, ExerciseAiRequest request) {
        ExerciseAi exercise = exerciseAiRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy bài tập AI"));

        if (exerciseAiRepository.existsByChapterIdAndCodeExcluding(exercise.getChapter().getId(), request.getExerciseCode(), id)) {
            throw new ConflictException("Mã bài tập AI đã tồn tại trong chương này");
        }

        exercise.setExerciseCode(request.getExerciseCode());
        exercise.setExerciseName(request.getExerciseName());
        exercise.setDifficulty(request.getDifficulty());
        exercise.setBloomLevel(request.getBloomLevel());
        exercise.setQuestion(request.getQuestion());
        exercise.setCorrectAnswer(request.getCorrectAnswer());

        exercise = exerciseAiRepository.save(exercise);
        return exerciseAiMapper.toResponse(exercise);
    }

    @Override
    @Transactional
    public void deleteExercise(Long id) {
        ExerciseAi exercise = exerciseAiRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy bài tập AI"));
        exerciseAiRepository.delete(exercise);
    }

    @Override
    @Transactional(readOnly = true)
    public ExerciseAiStatsResponse getExerciseStats(Long id) {
        ExerciseAi exercise = exerciseAiRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy bài tập AI"));

        long total = exerciseAiAttemptRepository.countTotalAttempts(id);
        long correct = exerciseAiAttemptRepository.countCorrectAttempts(id);
        long incorrect = total - correct;
        double rate = total == 0 ? 0.0 : ((double) correct / total) * 100;

        return ExerciseAiStatsResponse.builder()
                .exerciseId(id)
                .exerciseCode(exercise.getExerciseCode())
                .exerciseName(exercise.getExerciseName())
                .totalAttempts(total)
                .correctCount(correct)
                .incorrectCount(incorrect)
                .successRate(rate)
                .build();
    }

    @Override
    public List<ExerciseAiResponse> importExercisesFromPdf(Long chapterId, MultipartFile file) {
        Chapter chapter = chapterRepository.findById(chapterId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy chương học"));

        if (file.isEmpty()) {
            throw new BadRequestException("Tập tin PDF tải lên bị trống");
        }

        List<Map<String, Object>> rawExercises = null;

        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.MULTIPART_FORM_DATA);
            headers.set("Authorization", "Bearer " + aiApiKey);

            MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
            ByteArrayResource fileResource = new ByteArrayResource(file.getBytes()) {
                @Override
                public String getFilename() {
                    return file.getOriginalFilename() != null ? file.getOriginalFilename() : "document.pdf";
                }
            };
            body.add("file", fileResource);

            HttpEntity<MultiValueMap<String, Object>> entity = new HttpEntity<>(body, headers);
            String url = aiServiceUrl + "/v1/exercises/import-pdf";

            try {
                // Try reading as a Map first (for standard wrapped response)
                ResponseEntity<Map> responseMap = restTemplate.postForEntity(url, entity, Map.class);
                if (responseMap.getStatusCode().is2xxSuccessful() && responseMap.getBody() != null) {
                    Map<String, Object> bodyMap = responseMap.getBody();
                    if (bodyMap.containsKey("data")) {
                        rawExercises = (List<Map<String, Object>>) bodyMap.get("data");
                    } else if (bodyMap.containsKey("items")) {
                        rawExercises = (List<Map<String, Object>>) bodyMap.get("items");
                    }
                }
            } catch (Exception mapEx) {
                try {
                    // Try reading as direct List
                    ResponseEntity<List> responseList = restTemplate.postForEntity(url, entity, List.class);
                    if (responseList.getStatusCode().is2xxSuccessful() && responseList.getBody() != null) {
                        rawExercises = (List<Map<String, Object>>) responseList.getBody();
                    }
                } catch (Exception listEx) {
                    log.error("Failed to parse response from AI Service as List or Map: ", listEx);
                    throw new BadRequestException("Phản hồi từ AI Service không đúng định dạng JSON mong muốn");
                }
            }
        } catch (org.springframework.web.client.ResourceAccessException e) {
            log.error("Không thể kết nối đến AI Service (Python): ", e);
            throw new BadRequestException("Không thể kết nối đến AI Service (Python) tại " + aiServiceUrl 
                    + ". Vui lòng kiểm tra xem AI Service đã được khởi chạy chưa.");
        } catch (Exception e) {
            log.error("Lỗi khi kết nối/xử lý tại AI Service: ", e);
            throw new BadRequestException("Lỗi khi kết nối hoặc xử lý tại AI Service: " + e.getMessage());
        }

        if (rawExercises == null || rawExercises.isEmpty()) {
            throw new BadRequestException("AI Service không trích xuất được câu hỏi nào từ file PDF này");
        }

        List<ExerciseAi> savedExercises = new ArrayList<>();
        for (Map<String, Object> map : rawExercises) {
            String code = (String) map.getOrDefault("exerciseCode", "AI-PDF");
            if (code.length() > 15) {
                code = code.substring(0, 15);
            }
            String name = (String) map.getOrDefault("exerciseName", "Bài tập AI dịch từ PDF");
            
            // Convert string to Difficulty enum
            String diffStr = (String) map.getOrDefault("difficulty", "MEDIUM");
            Difficulty difficulty;
            try {
                difficulty = Difficulty.valueOf(diffStr.toUpperCase());
            } catch (Exception e) {
                difficulty = Difficulty.MEDIUM;
            }

            // Convert string to BloomLevel enum
            String bloomStr = (String) map.getOrDefault("bloomLevel", "UNDERSTANDING");
            BloomLevel bloomLevel;
            try {
                bloomLevel = BloomLevel.valueOf(bloomStr.toUpperCase());
            } catch (Exception e) {
                bloomLevel = BloomLevel.UNDERSTANDING;
            }

            String question = (String) map.get("question");
            String correctAnswer = (String) map.get("correctAnswer");

            if (question == null || question.trim().isEmpty()) {
                continue; // Skip invalid questions
            }
            if (correctAnswer == null || correctAnswer.trim().isEmpty()) {
                correctAnswer = "Chưa có đáp án";
            }

            // To avoid code duplication in the same chapter
            String finalCode = code;
            int count = 1;
            while (exerciseAiRepository.existsByChapterIdAndCode(chapterId, finalCode)) {
                finalCode = code + "_" + count++;
            }

            ExerciseAi exercise = ExerciseAi.builder()
                    .chapter(chapter)
                    .exerciseCode(finalCode)
                    .exerciseName(name)
                    .difficulty(difficulty)
                    .bloomLevel(bloomLevel)
                    .question(question)
                    .correctAnswer(correctAnswer)
                    .build();

            exercise = exerciseAiRepository.save(exercise);
            savedExercises.add(exercise);
        }

        return savedExercises.stream()
                .map(exerciseAiMapper::toResponse)
                .collect(Collectors.toList());
    }

    @Override
    public List<ExerciseAiResponse> generateAutoExercises(Long chapterId) {
        Chapter chapter = chapterRepository.findById(chapterId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy chương học"));

        List<Map<String, Object>> rawExercises = null;

        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.set("Authorization", "Bearer " + aiApiKey);

            Map<String, Object> requestBody = new java.util.HashMap<>();
            requestBody.put("subject", "course_" + chapter.getCourse().getId());
            requestBody.put("chapter", "chuong_" + chapter.getChapterNumber());

            HttpEntity<Map<String, Object>> entity = new HttpEntity<>(requestBody, headers);
            String url = aiServiceUrl + "/v1/exercises/generate-from-theory";

            ResponseEntity<Map> responseMap = restTemplate.postForEntity(url, entity, Map.class);
            if (responseMap.getStatusCode().is2xxSuccessful() && responseMap.getBody() != null) {
                Map<String, Object> bodyMap = responseMap.getBody();
                if (bodyMap.containsKey("data")) {
                    rawExercises = (List<Map<String, Object>>) bodyMap.get("data");
                }
            }
        } catch (org.springframework.web.client.ResourceAccessException e) {
            log.error("Khong the ket noi den AI Service (Python): ", e);
            throw new BadRequestException("Không thể kết nối đến AI Service (Python). Vui lòng kiểm tra server AI.");
        } catch (org.springframework.web.client.HttpClientErrorException | org.springframework.web.client.HttpServerErrorException e) {
            String detail = e.getResponseBodyAsString();
            log.error("Loi tu AI Service HTTP {}: {}", e.getStatusCode(), detail);
            throw new BadRequestException("Lỗi khi gọi AI Service sinh bài tập: " + e.getStatusCode() + " - " + detail);
        } catch (Exception e) {
            log.error("Loi khi ket noi/xu ly tai AI Service: ", e);
            throw new BadRequestException("Lỗi khi gọi AI Service sinh bài tập: " + e.getMessage());
        }

        if (rawExercises == null || rawExercises.isEmpty()) {
            throw new BadRequestException("AI Service không sinh được bài tập nào từ lý thuyết");
        }

        List<ExerciseAi> savedExercises = new ArrayList<>();
        for (Map<String, Object> map : rawExercises) {
            String code = (String) map.getOrDefault("exerciseCode", "AI-GEN");
            if (code.length() > 15) {
                code = code.substring(0, 15);
            }
            String name = (String) map.getOrDefault("exerciseName", "Bài tập AI Sinh");
            
            String diffStr = (String) map.getOrDefault("difficulty", "MEDIUM");
            Difficulty difficulty;
            try {
                difficulty = Difficulty.valueOf(diffStr.toUpperCase());
            } catch (Exception e) {
                difficulty = Difficulty.MEDIUM;
            }

            String bloomStr = (String) map.getOrDefault("bloomLevel", "UNDERSTANDING");
            BloomLevel bloomLevel;
            try {
                bloomLevel = BloomLevel.valueOf(bloomStr.toUpperCase());
            } catch (Exception e) {
                bloomLevel = BloomLevel.UNDERSTANDING;
            }

            String question = (String) map.get("question");
            String correctAnswer = (String) map.get("correctAnswer");

            if (question == null || question.trim().isEmpty()) {
                continue;
            }
            if (correctAnswer == null || correctAnswer.trim().isEmpty()) {
                correctAnswer = "Chưa có đáp án";
            }

            String finalCode = code;
            int count = 1;
            while (exerciseAiRepository.existsByChapterIdAndCode(chapterId, finalCode)) {
                finalCode = code + "_" + count++;
            }

            ExerciseAi exercise = ExerciseAi.builder()
                    .chapter(chapter)
                    .exerciseCode(finalCode)
                    .exerciseName(name)
                    .difficulty(difficulty)
                    .bloomLevel(bloomLevel)
                    .question(question)
                    .correctAnswer(correctAnswer)
                    .build();

            exercise = exerciseAiRepository.save(exercise);
            savedExercises.add(exercise);
        }

        return savedExercises.stream()
                .map(exerciseAiMapper::toResponse)
                .collect(Collectors.toList());
    }

    @Override
    @Transactional(readOnly = true)
    public void syncExercisesToAITutor(Long chapterId) {
        Chapter chapter = chapterRepository.findById(chapterId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy chương học"));
        
        List<ExerciseAi> exercises = exerciseAiRepository.findByChapterIdOrdered(chapterId);
        if (exercises.isEmpty()) {
            throw new BadRequestException("Không có bài tập AI nào trong chương này để đồng bộ");
        }

        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);

            Map<String, Object> requestBody = new java.util.HashMap<>();
            requestBody.put("subject", chapter.getCourse().getTitle());
            requestBody.put("chapter", chapter.getChapterName());
            
            List<Map<String, Object>> exercisesList = new ArrayList<>();
            for (ExerciseAi ex : exercises) {
                Map<String, Object> map = new java.util.HashMap<>();
                map.put("exerciseCode", ex.getExerciseCode());
                map.put("exerciseName", ex.getExerciseName());
                map.put("difficulty", ex.getDifficulty().name());
                map.put("bloomLevel", ex.getBloomLevel().name());
                map.put("question", ex.getQuestion());
                map.put("correctAnswer", ex.getCorrectAnswer());
                exercisesList.add(map);
            }
            requestBody.put("exercises", exercisesList);

            HttpEntity<Map<String, Object>> entity = new HttpEntity<>(requestBody, headers);
            String url = aiServiceUrl + "/v1/exercises/generate-scaffold-local";

            ResponseEntity<Map> response = restTemplate.postForEntity(url, entity, Map.class);
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new BadRequestException("Đồng bộ thất bại từ AI Service");
            }
        } catch (Exception e) {
            log.error("Lỗi khi đồng bộ bài tập sang AI Tutor: ", e);
            throw new BadRequestException("Lỗi kết nối tới AI Service để đồng bộ: " + e.getMessage());
        }
    }
}
