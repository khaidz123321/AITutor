package re.edu.ai_elearning.mapper;

import org.springframework.stereotype.Component;
import re.edu.ai_elearning.dto.response.ExerciseAiResponse;
import re.edu.ai_elearning.entity.ExerciseAi;

@Component
public class ExerciseAiMapper {

    public ExerciseAiResponse toResponse(ExerciseAi exercise) {
        if (exercise == null) {
            return null;
        }

        return ExerciseAiResponse.builder()
                .id(exercise.getId())
                .chapterId(exercise.getChapter() != null ? exercise.getChapter().getId() : null)
                .exerciseCode(exercise.getExerciseCode())
                .exerciseName(exercise.getExerciseName())
                .difficulty(exercise.getDifficulty())
                .bloomLevel(exercise.getBloomLevel())
                .question(exercise.getQuestion())
                .correctAnswer(exercise.getCorrectAnswer())
                .createdAt(exercise.getCreatedAt())
                .build();
    }
}
