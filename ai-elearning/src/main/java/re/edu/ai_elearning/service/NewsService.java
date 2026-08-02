package re.edu.ai_elearning.service;

import re.edu.ai_elearning.dto.request.NewsRequest;
import re.edu.ai_elearning.dto.response.NewsResponse;

import java.util.List;

public interface NewsService {
    List<NewsResponse> getAllNews(String category);
    NewsResponse getNewsById(Long id);
    NewsResponse createNews(NewsRequest request);
    NewsResponse updateNews(Long id, NewsRequest request);
    void deleteNews(Long id);
}
