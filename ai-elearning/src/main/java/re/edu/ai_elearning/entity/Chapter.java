package re.edu.ai_elearning.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "chapters")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Chapter {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "course_id", nullable = false)
    private Course course;

    @Column(name = "subject_name", length = 255)
    private String subjectName;

    // Slug dùng để gọi Python AI Service (ví dụ: "giai_tich_1", "triet_hoc_maclenin")
    // Được set khi Admin tạo chapter. Nếu null, Spring Boot sẽ tự sinh từ subjectName.
    @Column(name = "subject_slug", length = 100)
    private String subjectSlug;

    // Slug chương (ví dụ: "chuong_1", "chuong_2")
    // Nếu null, Spring Boot fallback về "chuong_" + chapterNumber.
    @Column(name = "chapter_slug", length = 100)
    private String chapterSlug;

    @Column(name = "chapter_number", nullable = false)
    private Integer chapterNumber;

    @Column(name = "chapter_name", nullable = false, length = 500)
    private String chapterName;

    @Column(columnDefinition = "TEXT")
    private String content;

    @Column(name = "order_index", nullable = false)
    @Builder.Default
    private Integer orderIndex = 0;

    @Column(name = "is_locked")
    @Builder.Default
    private Boolean isLocked = true;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @OneToMany(mappedBy = "chapter", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    @Builder.Default
    private List<Exercise> exercises = new ArrayList<>();
}
