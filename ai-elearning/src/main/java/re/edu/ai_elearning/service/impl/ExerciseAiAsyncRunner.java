package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import re.edu.ai_elearning.service.ExerciseAiService;

import java.util.concurrent.CompletableFuture;

/**
 * Lớp trung gian để kích hoạt @Async đúng cách (tránh Spring AOP self-invocation bypass).
 * Được gọi từ ExerciseAiController, sau đó gọi lại ExerciseAiService qua Spring proxy.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ExerciseAiAsyncRunner {

    private final ExerciseAiService exerciseAiService;

    @Async("aiTaskExecutor")
    public CompletableFuture<Void> runGenerateAutoExercises(Long chapterId) {
        try {
            log.info("[AsyncRunner] Bat dau sinh bai tap nen cho chapterId={}", chapterId);
            exerciseAiService.generateAutoExercises(chapterId);
            log.info("[AsyncRunner] THANH CONG sinh bai tap nen cho chapterId={}", chapterId);
        } catch (Exception e) {
            log.error("[AsyncRunner] THAT BAI sinh bai tap nen cho chapterId={}: {}", chapterId, e.getMessage(), e);
        }
        return CompletableFuture.completedFuture(null);
    }
}
