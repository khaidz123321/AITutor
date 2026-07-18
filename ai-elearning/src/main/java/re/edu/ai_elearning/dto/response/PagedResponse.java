package re.edu.ai_elearning.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import org.springframework.data.domain.Page;

import java.util.List;
import java.util.function.Function;
import java.util.stream.Collectors;

@Getter
@Builder
public class PagedResponse<T> {

    private List<T> items;
    private PaginationMeta pagination;

    /**
     * Tiện ích tạo PagedResponse từ Spring Data Page object
     */
    public static <E, T> PagedResponse<T> of(Page<E> page, Function<E, T> mapper) {
        List<T> items = page.getContent().stream()
                .map(mapper)
                .collect(Collectors.toList());

        PaginationMeta meta = PaginationMeta.builder()
                .currentPage(page.getNumber() + 1)  // Spring Data bắt đầu từ 0, trả về từ 1
                .pageSize(page.getSize())
                .totalPages(page.getTotalPages())
                .totalItems(page.getTotalElements())
                .build();

        return PagedResponse.<T>builder()
                .items(items)
                .pagination(meta)
                .build();
    }

    @Getter
    @Builder
    @AllArgsConstructor
    public static class PaginationMeta {
        private int currentPage;
        private int pageSize;
        private int totalPages;
        private long totalItems;
    }
}
