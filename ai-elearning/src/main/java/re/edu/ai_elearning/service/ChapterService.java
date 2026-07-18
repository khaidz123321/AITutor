package re.edu.ai_elearning.service;

import re.edu.ai_elearning.dto.request.ChapterRequest;
import re.edu.ai_elearning.dto.request.ReorderChapterRequest;
import re.edu.ai_elearning.dto.response.ChapterResponse;

public interface ChapterService {
    ChapterResponse getChapterById(Long userId, Long id);
    ChapterResponse createChapter(Long courseId, ChapterRequest request);
    ChapterResponse updateChapter(Long id, ChapterRequest request);
    void deleteChapter(Long id);
    ChapterResponse reorderChapter(Long id, ReorderChapterRequest request);
    void toggleChapterLock(Long id, Boolean isLocked);
}
