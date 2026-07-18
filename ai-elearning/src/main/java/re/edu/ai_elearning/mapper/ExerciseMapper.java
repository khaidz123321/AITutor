package re.edu.ai_elearning.mapper;

import org.springframework.stereotype.Component;
import re.edu.ai_elearning.dto.response.ExerciseResponse;
import re.edu.ai_elearning.entity.Exercise;

@Component
public class ExerciseMapper {

    public ExerciseResponse toResponse(Exercise exercise) {
        if (exercise == null) {
            return null;
        }

        return ExerciseResponse.builder()
                .id(exercise.getId())
                .chapterId(exercise.getChapter() != null ? exercise.getChapter().getId() : null)
                .exerciseCode(exercise.getExerciseCode())
                .exerciseName(exercise.getExerciseName())
                .difficulty(exercise.getDifficulty())
                .bloomLevel(exercise.getBloomLevel())
                .question(exercise.getQuestion())
                .createdAt(exercise.getCreatedAt())
                .build();
    }
}
