package re.edu.ai_elearning.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;

@Entity
@Table(name = "learning_profiles",
        uniqueConstraints = @UniqueConstraint(columnNames = {"user_id", "course_id"}))
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class LearningProfile {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "course_id", nullable = false)
    private Course course;

    /**
     * Tiến độ học tập (0-100)
     */
    @Column(name = "progress_percent")
    @Builder.Default
    private Integer progressPercent = 0;

    /**
     * JSON lưu trạng thái thành thạo theo BloomLevel
     * Ví dụ: {"REMEMBERING":80,"UNDERSTANDING":60}
     */
    @Column(name = "bloom_mastery", columnDefinition = "TEXT")
    private String bloomMastery;

    /**
     * Thời điểm đăng ký khóa học (thay thế CourseEnrollment)
     */
    @CreationTimestamp
    @Column(name = "enrolled_at", updatable = false)
    private LocalDateTime enrolledAt;

    @Column(name = "last_studied")
    private LocalDateTime lastStudied;

    @UpdateTimestamp
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;
}
