package re.edu.ai_elearning.service;

import re.edu.ai_elearning.dto.request.AnswerSubmitRequest;
import re.edu.ai_elearning.dto.request.ExerciseAiRequest;
import re.edu.ai_elearning.dto.response.ExerciseAiResponse;
import re.edu.ai_elearning.dto.response.ExerciseAiResultResponse;
import re.edu.ai_elearning.dto.response.ExerciseAiStatsResponse;

import java.util.List;

public interface ExerciseAiService {
    ExerciseAiResponse getExerciseById(Long userId, Long id);
    ExerciseAiResultResponse submitAnswer(Long userId, Long id, AnswerSubmitRequest request);
    ExerciseAiResponse getNextExercise(Long userId, Long chapterId);
    List<ExerciseAiResponse> getExercisesByChapter(Long userId, Long chapterId);

    // Admin/Teacher functions
    ExerciseAiResponse createExercise(Long chapterId, ExerciseAiRequest request);
    ExerciseAiResponse updateExercise(Long id, ExerciseAiRequest request);
    void deleteExercise(Long id);
    ExerciseAiStatsResponse getExerciseStats(Long id);
    List<ExerciseAiResponse> importExercisesFromPdf(Long chapterId, org.springframework.web.multipart.MultipartFile file);
    List<ExerciseAiResponse> generateAutoExercises(Long chapterId);
    void syncExercisesToAITutor(Long chapterId);
}
