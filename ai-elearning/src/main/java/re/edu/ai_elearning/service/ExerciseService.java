package re.edu.ai_elearning.service;

import re.edu.ai_elearning.dto.request.AnswerSubmitRequest;
import re.edu.ai_elearning.dto.request.ExerciseRequest;
import re.edu.ai_elearning.dto.response.ExerciseResponse;
import re.edu.ai_elearning.dto.response.ExerciseResultResponse;
import re.edu.ai_elearning.dto.response.ExerciseStatsResponse;

import java.util.List;

public interface ExerciseService {
    ExerciseResponse getExerciseById(Long userId, Long id);
    ExerciseResultResponse submitAnswer(Long userId, Long id, AnswerSubmitRequest request);
    ExerciseResponse getNextExercise(Long userId, Long chapterId);
    List<ExerciseResponse> getExercisesByChapter(Long userId, Long chapterId);

    // Admin/Teacher functions
    ExerciseResponse createExercise(Long chapterId, ExerciseRequest request);
    ExerciseResponse updateExercise(Long id, ExerciseRequest request);
    void deleteExercise(Long id);
    ExerciseStatsResponse getExerciseStats(Long id);
}
