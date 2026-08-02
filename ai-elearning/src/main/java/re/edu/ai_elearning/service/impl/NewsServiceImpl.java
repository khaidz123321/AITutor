package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import re.edu.ai_elearning.dto.request.NewsRequest;
import re.edu.ai_elearning.dto.response.NewsResponse;
import re.edu.ai_elearning.entity.News;
import re.edu.ai_elearning.exception.ResourceNotFoundException;
import re.edu.ai_elearning.repository.NewsRepository;
import re.edu.ai_elearning.service.NewsService;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class NewsServiceImpl implements NewsService {

    private final NewsRepository newsRepository;

    @Override
    @Transactional(readOnly = true)
    public List<NewsResponse> getAllNews(String category) {
        List<News> newsList;
        if (category != null && !category.isBlank() && !"all".equalsIgnoreCase(category)) {
            newsList = newsRepository.findByCategoryOrderByCreatedAtDesc(category);
        } else {
            newsList = newsRepository.findAllByOrderByCreatedAtDesc();
        }
        return newsList.stream().map(this::mapToResponse).collect(Collectors.toList());
    }

    @Override
    @Transactional(readOnly = true)
    public NewsResponse getNewsById(Long id) {
        News news = newsRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy tin tức với ID: " + id));
        return mapToResponse(news);
    }

    @Override
    @Transactional
    public NewsResponse createNews(NewsRequest request) {
        News news = News.builder()
                .title(request.getTitle())
                .category(request.getCategory())
                .summary(request.getSummary())
                .content(request.getContent())
                .imageUrl(request.getImageUrl())
                .isSpotlight(request.getIsSpotlight() != null ? request.getIsSpotlight() : false)
                .build();
        News saved = newsRepository.save(news);
        return mapToResponse(saved);
    }

    @Override
    @Transactional
    public NewsResponse updateNews(Long id, NewsRequest request) {
        News news = newsRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy tin tức với ID: " + id));

        news.setTitle(request.getTitle());
        news.setCategory(request.getCategory());
        news.setSummary(request.getSummary());
        news.setContent(request.getContent());
        news.setImageUrl(request.getImageUrl());
        if (request.getIsSpotlight() != null) {
            news.setIsSpotlight(request.getIsSpotlight());
        }

        News updated = newsRepository.save(news);
        return mapToResponse(updated);
    }

    @Override
    @Transactional
    public void deleteNews(Long id) {
        News news = newsRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy tin tức với ID: " + id));
        newsRepository.delete(news);
    }

    private NewsResponse mapToResponse(News news) {
        return NewsResponse.builder()
                .id(news.getId())
                .title(news.getTitle())
                .category(news.getCategory())
                .summary(news.getSummary())
                .content(news.getContent())
                .imageUrl(news.getImageUrl())
                .isSpotlight(news.getIsSpotlight())
                .createdAt(news.getCreatedAt())
                .updatedAt(news.getUpdatedAt())
                .build();
    }
}
