package re.edu.ai_elearning.service;

import re.edu.ai_elearning.dto.response.CourseSummaryResponse;
import re.edu.ai_elearning.dto.response.ReportDifficultyResponse;
import re.edu.ai_elearning.dto.response.ReportProgressResponse;

import java.util.List;

public interface ReportService {
    List<ReportProgressResponse> getProgressReport();
    List<ReportDifficultyResponse> getDifficultyReport();
    CourseSummaryResponse getCourseSummary();
}
