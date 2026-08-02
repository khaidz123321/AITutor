-- Dữ liệu mẫu kiểm thử API (AI E-learning System)
-- Hệ quản trị cơ sở dữ liệu: PostgreSQL
-- Kịch bản dữ liệu kiểm thử đầy đủ các vai trò: Admin, Teacher, Active/Inactive Student, và các trạng thái học tập.

-- ==========================================
-- 1. LÀM SẠCH DỮ LIỆU CŨ (TRUNCATE)
-- ==========================================
TRUNCATE TABLE chat_messages CASCADE;
TRUNCATE TABLE chat_sessions CASCADE;
TRUNCATE TABLE exercise_attempts CASCADE;
TRUNCATE TABLE exercises CASCADE;
TRUNCATE TABLE chapters CASCADE;
TRUNCATE TABLE learning_profiles CASCADE;
TRUNCATE TABLE reviews CASCADE;
TRUNCATE TABLE notifications CASCADE;
TRUNCATE TABLE user_profiles CASCADE;
TRUNCATE TABLE users CASCADE;
TRUNCATE TABLE courses CASCADE;

-- Reset sequence cho các khóa chính tự tăng
SELECT setval(pg_get_serial_sequence('users', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('user_profiles', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('courses', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('chapters', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('exercises', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('learning_profiles', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('reviews', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('notifications', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('chat_sessions', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('chat_messages', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('exercise_attempts', 'id'), 1, false);


-- ==========================================
-- 2. DỮ LIỆU BẢNG `users`
-- ==========================================
-- Mật khẩu mặc định cho tất cả user: "password123"
-- Mã băm BCrypt chuẩn: $2a$10$71TGIQmOb5dhaoSMoEKDVuGH.sMYo55j3ALNIHQcFAy.b.fMxdsHi
INSERT INTO users (id, email, password_hash, full_name, is_active, role, created_at, updated_at) VALUES
(1, 'admin@elearning.com', '$2a$10$71TGIQmOb5dhaoSMoEKDVuGH.sMYo55j3ALNIHQcFAy.b.fMxdsHi', 'Hệ Thống Admin', true, 'ADMIN', NOW() - INTERVAL '30 days', NOW()),
(2, 'teacher1@elearning.com', '$2a$10$71TGIQmOb5dhaoSMoEKDVuGH.sMYo55j3ALNIHQcFAy.b.fMxdsHi', 'Giảng viên Nguyễn Văn A (Java/AI)', true, 'TEACHER', NOW() - INTERVAL '25 days', NOW()),
(3, 'student1@elearning.com', '$2a$10$71TGIQmOb5dhaoSMoEKDVuGH.sMYo55j3ALNIHQcFAy.b.fMxdsHi', 'Học viên Trần Thị B (Học giỏi)', true, 'STUDENT', NOW() - INTERVAL '20 days', NOW()),
(4, 'student2@elearning.com', '$2a$10$71TGIQmOb5dhaoSMoEKDVuGH.sMYo55j3ALNIHQcFAy.b.fMxdsHi', 'Học viên Lê Văn C (Bình thường)', true, 'STUDENT', NOW() - INTERVAL '15 days', NOW()),
(5, 'teacher2@elearning.com', '$2a$10$71TGIQmOb5dhaoSMoEKDVuGH.sMYo55j3ALNIHQcFAy.b.fMxdsHi', 'Giảng viên Trần Đức B (Python/Web)', true, 'TEACHER', NOW() - INTERVAL '25 days', NOW()),
(6, 'student_new@elearning.com', '$2a$10$71TGIQmOb5dhaoSMoEKDVuGH.sMYo55j3ALNIHQcFAy.b.fMxdsHi', 'Học viên Mới Đăng Ký', true, 'STUDENT', NOW() - INTERVAL '1 days', NOW()),
(7, 'student_inactive@elearning.com', '$2a$10$71TGIQmOb5dhaoSMoEKDVuGH.sMYo55j3ALNIHQcFAy.b.fMxdsHi', 'Tài Khoản Bị Khóa', false, 'STUDENT', NOW() - INTERVAL '10 days', NOW());

SELECT setval(pg_get_serial_sequence('users', 'id'), (SELECT MAX(id) FROM users));


-- ==========================================
-- 4. DỮ LIỆU BẢNG `user_profiles`
-- ==========================================
INSERT INTO user_profiles (id, user_id, avatar_url, date_of_birth, gender, phone, address, city, country, bio, updated_at) VALUES
(1, 1, 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde', '1990-01-01', 'Nam', '0901234567', '123 Đường Láng', 'Hà Nội', 'Việt Nam', 'Hệ thống quản trị viên tối cao.', NOW()),
(2, 2, 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2', '1985-05-15', 'Nữ', '0907654321', '456 Điện Biên Phủ', 'Hồ Chí Minh', 'Việt Nam', 'Giảng viên khoa Công nghệ thông tin chuyên ngành OOP và AI.', NOW()),
(3, 3, 'https://images.unsplash.com/photo-1494790108377-be9c29b29330', '2002-09-20', 'Nữ', '0912345678', '789 Nguyễn Lương Bằng', 'Đà Nẵng', 'Việt Nam', 'Học viên đam mê lập trình Java và phát triển web.', NOW()),
(4, 4, 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d', '2001-11-12', 'Nam', '0987654321', '321 Lê Lợi', 'Huế', 'Việt Nam', 'Sinh viên năm 3 khoa CNTT.', NOW()),
(5, 5, 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e', '1988-08-08', 'Nam', '0905555555', '12 Đường Trần Phú', 'Nha Trang', 'Việt Nam', 'Giảng viên Python và Web Fullstack.', NOW()),
(6, 6, NULL, NULL, 'Nam', NULL, NULL, NULL, 'Việt Nam', 'Học viên mới gia nhập cộng đồng.', NOW()),
(7, 7, NULL, '2000-02-02', 'Nữ', '0999999999', 'Vi phạm điều khoản', 'Hải Phòng', 'Việt Nam', 'Tài khoản tạm thời bị khóa do vi phạm nội quy.', NOW());

SELECT setval(pg_get_serial_sequence('user_profiles', 'id'), (SELECT MAX(id) FROM user_profiles));


-- ==========================================
-- 5. DỮ LIỆU BẢNG `courses`
-- ==========================================
-- Level: BEGINNER, INTERMEDIATE, ADVANCED
INSERT INTO courses (id, title, description, level, is_visible, thumbnail_url, created_by, created_at, updated_at) VALUES
(1, 'Lập trình Java căn bản đến nâng cao', 'Khóa học lập trình Java từ OOP cơ bản đến nâng cao (Collection, Generics, Stream API, Concurrency).', 'BEGINNER', true, 'https://images.unsplash.com/photo-1517694712202-14dd9538aa97', 2, NOW() - INTERVAL '15 days', NOW()),
(2, 'Trí tuệ nhân tạo và Ứng dụng thực tế', 'Tìm hiểu về Machine Learning, Deep Learning, mạng Nơ-ron và các ứng dụng AI trong đời sống thực tế với Python.', 'ADVANCED', true, 'https://images.unsplash.com/photo-1677442136019-21780efad99a', 2, NOW() - INTERVAL '14 days', NOW()),
(3, 'Lập trình Python cho Khoa học dữ liệu', 'Nắm vững ngôn ngữ Python và các thư viện phân tích dữ liệu nổi tiếng: NumPy, Pandas, Matplotlib, Seaborn.', 'INTERMEDIATE', true, 'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5', 5, NOW() - INTERVAL '10 days', NOW()),
(4, 'Lập trình Web Frontend với ReactJS', 'Khóa học phát triển giao diện Web hiện đại sử dụng ReactJS, Redux Toolkit và tối ưu hiệu suất ứng dụng.', 'BEGINNER', true, 'https://images.unsplash.com/photo-1633356122544-f134324a6cee', 5, NOW() - INTERVAL '8 days', NOW()),
(5, 'Thiết kế hệ thống phân tán (System Design - DRAFT)', 'Khóa học cao cấp về thiết kế hệ thống có tính chịu tải cao (Scalability, Sharding, Caching, Load Balancing).', 'ADVANCED', false, 'https://images.unsplash.com/photo-1451187580459-43490279c0fa', 2, NOW() - INTERVAL '2 days', NOW());

SELECT setval(pg_get_serial_sequence('courses', 'id'), (SELECT MAX(id) FROM courses));


-- ==========================================
-- 6. DỮ LIỆU BẢNG `chapters`
-- ==========================================
-- Các chương cho Course 1 (Java)
INSERT INTO chapters (id, course_id, subject_name, chapter_number, chapter_name, content, order_index, is_locked, created_at, updated_at) VALUES
(1, 1, 'Java', 1, 'Giới thiệu về Java và JVM', 'Java là một ngôn ngữ lập trình OOP phổ biến. Máy ảo Java (JVM) chịu trách nhiệm thực thi mã bytecode...', 1, false, NOW() - INTERVAL '15 days', NOW()),
(2, 1, 'Java', 2, 'Biến, Kiểu dữ liệu và Toán tử', 'Trong Java, biến là vùng nhớ dùng để lưu trữ dữ liệu. Gồm kiểu dữ liệu nguyên thủy và tham chiếu...', 2, false, NOW() - INTERVAL '14 days', NOW()),
(3, 1, 'Java', 3, 'Cấu trúc điều khiển và Vòng lặp', 'Cấu trúc điều khiển bao gồm rẽ nhánh (if, switch) và lặp (for, while, do-while)...', 3, true, NOW() - INTERVAL '13 days', NOW());

-- Các chương cho Course 2 (AI)
INSERT INTO chapters (id, course_id, subject_name, chapter_number, chapter_name, content, order_index, is_locked, created_at, updated_at) VALUES
(4, 2, 'AI', 1, 'Tổng quan về Trí tuệ nhân tạo', 'Lịch sử phát triển của AI, các khái niệm Học máy (Machine Learning) và Học sâu (Deep Learning)...', 1, false, NOW() - INTERVAL '14 days', NOW()),
(5, 2, 'AI', 2, 'Học có giám sát (Supervised Learning)', 'Tìm hiểu về hồi quy tuyến tính (Linear Regression) và phân loại (Classification)...', 2, true, NOW() - INTERVAL '13 days', NOW());

-- Các chương cho Course 3 (Python)
INSERT INTO chapters (id, course_id, subject_name, chapter_number, chapter_name, content, order_index, is_locked, created_at, updated_at) VALUES
(6, 3, 'Python', 1, 'Cú pháp căn bản của Python', 'Python sử dụng thụt lề (indentation) để xác định khối mã nguồn thay cho cặp ngoặc nhọn. Kiểu dữ liệu động...', 1, false, NOW() - INTERVAL '10 days', NOW()),
(7, 3, 'Python', 2, 'Cấu trúc dữ liệu List, Tuple, Dict', 'Cách thao tác với List, Tuple, Set, Dictionary và List Comprehension trong Python...', 2, false, NOW() - INTERVAL '9 days', NOW()),
(8, 3, 'Python', 3, 'Hàm và Lập trình Hàm', 'Khai báo hàm với def, tham số mặc định (*args, **kwargs) và biểu thức lambda...', 3, true, NOW() - INTERVAL '8 days', NOW());

-- Các chương cho Course 4 (ReactJS)
INSERT INTO chapters (id, course_id, subject_name, chapter_number, chapter_name, content, order_index, is_locked, created_at, updated_at) VALUES
(9, 4, 'ReactJS', 1, 'Giới thiệu React & JSX', 'ReactJS là thư viện JavaScript dùng để xây dựng giao diện người dùng. JSX cho phép viết code HTML trong JS...', 1, false, NOW() - INTERVAL '8 days', NOW());

SELECT setval(pg_get_serial_sequence('chapters', 'id'), (SELECT MAX(id) FROM chapters));


-- ==========================================
-- 7. DỮ LIỆU BẢNG `exercises`
-- ==========================================
-- BloomLevel: REMEMBERING, UNDERSTANDING, APPLYING, ANALYZING, EVALUATING
-- Difficulty: EASY, MEDIUM, HARD

-- Exercises cho Java Chapter 1 (JVM)
INSERT INTO exercises (id, chapter_id, exercise_code, exercise_name, difficulty, bloom_level, question, correct_answer, created_at, updated_at) VALUES
(1, 1, 'Java-1.1', 'Lịch sử phát triển Java', 'EASY', 'REMEMBERING', 'Ngôn ngữ lập trình Java được phát hành lần đầu tiên bởi Sun Microsystems vào năm nào?', '1995', NOW(), NOW()),
(2, 1, 'Java-1.2', 'Thành phần JVM', 'MEDIUM', 'UNDERSTANDING', 'JVM là viết tắt của cụm từ tiếng Anh nào (viết hoa chữ cái đầu mỗi từ)?', 'Java Virtual Machine', NOW(), NOW());

-- Exercises cho Java Chapter 2 (Biến & Kiểu dữ liệu)
INSERT INTO exercises (id, chapter_id, exercise_code, exercise_name, difficulty, bloom_level, question, correct_answer, created_at, updated_at) VALUES
(3, 2, 'Java-2.1', 'Kiểu dữ liệu số thực', 'EASY', 'REMEMBERING', 'Trong Java, kiểu dữ liệu nguyên thủy nào chiếm 8 byte và được dùng để biểu diễn số thực có độ chính xác kép?', 'double', NOW(), NOW()),
(4, 2, 'Java-2.2', 'Cú pháp khai báo hằng số', 'MEDIUM', 'APPLYING', 'Từ khóa nào trong Java được dùng để khai báo một hằng số (không thể thay đổi giá trị sau khi gán)?', 'final', NOW(), NOW());

-- Exercises cho AI Chapter 1 (Tổng quan)
INSERT INTO exercises (id, chapter_id, exercise_code, exercise_name, difficulty, bloom_level, question, correct_answer, created_at, updated_at) VALUES
(5, 4, 'AI-1.1', 'Định nghĩa Machine Learning', 'EASY', 'UNDERSTANDING', 'Thuật ngữ nào dùng để chỉ một nhánh của AI cho phép máy tính tự học hỏi từ dữ liệu mà không cần lập trình rõ ràng?', 'Machine Learning', NOW(), NOW());

-- Exercises cho Python Chapter 1 (Cú pháp)
INSERT INTO exercises (id, chapter_id, exercise_code, exercise_name, difficulty, bloom_level, question, correct_answer, created_at, updated_at) VALUES
(6, 6, 'Py-1.1', 'Từ khóa cấu trúc rẽ nhánh', 'EASY', 'REMEMBERING', 'Từ khóa nào dùng để bắt đầu một cấu trúc rẽ nhánh có điều kiện trong Python?', 'if', NOW(), NOW());

-- Exercises cho Python Chapter 2 (Cấu trúc dữ liệu)
INSERT INTO exercises (id, chapter_id, exercise_code, exercise_name, difficulty, bloom_level, question, correct_answer, created_at, updated_at) VALUES
(7, 7, 'Py-2.1', 'Khai báo Dictionary trống', 'EASY', 'APPLYING', 'Cú pháp nào sau đây dùng để khai báo một Dictionary rỗng trong Python?', '{}', NOW(), NOW()),
(8, 7, 'Py-2.2', 'Sắp xếp danh sách', 'MEDIUM', 'ANALYZING', 'Phương thức nào được dùng để sắp xếp trực tiếp (in-place) các phần tử trong một List của Python?', 'sort', NOW(), NOW());

SELECT setval(pg_get_serial_sequence('exercises', 'id'), (SELECT MAX(id) FROM exercises));


-- ==========================================
-- 8. DỮ LIỆU BẢNG `learning_profiles` (Đăng ký học & Tiến độ)
-- ==========================================
-- Student 1 (Trần Thị B):
-- * Java (Course 1): Tiến độ 33%, đã hoàn thành chương 1
-- * Python (Course 3): Tiến độ 66%, đã hoàn thành chương 1 và chương 2
-- * AI (Course 2): Mới đăng ký (0%)
INSERT INTO learning_profiles (id, user_id, course_id, progress_percent, bloom_mastery, enrolled_at, last_studied, updated_at) VALUES
(1, 3, 1, 33, '{"REMEMBERING":100,"UNDERSTANDING":100,"APPLYING":0}', NOW() - INTERVAL '10 days', NOW() - INTERVAL '2 hours', NOW()),
(2, 3, 3, 66, '{"REMEMBERING":100,"APPLYING":100,"ANALYZING":80}', NOW() - INTERVAL '9 days', NOW() - INTERVAL '1 hours', NOW()),
(3, 3, 2, 0, '{"REMEMBERING":0,"UNDERSTANDING":0}', NOW() - INTERVAL '1 hours', NOW(), NOW());

-- Student 2 (Lê Văn C):
-- * Java (Course 1): Tiến độ 66%, hoàn thành chương 1 và chương 2
-- * AI (Course 2): Tiến độ 20%
-- * ReactJS (Course 4): Hoàn thành 100% khóa học
INSERT INTO learning_profiles (id, user_id, course_id, progress_percent, bloom_mastery, enrolled_at, last_studied, updated_at) VALUES
(4, 4, 1, 66, '{"REMEMBERING":100,"UNDERSTANDING":50,"APPLYING":100}', NOW() - INTERVAL '8 days', NOW() - INTERVAL '5 hours', NOW()),
(5, 4, 2, 20, '{"UNDERSTANDING":60}', NOW() - INTERVAL '6 days', NOW() - INTERVAL '1 days', NOW()),
(6, 4, 4, 100, '{"REMEMBERING":100,"UNDERSTANDING":100}', NOW() - INTERVAL '5 days', NOW() - INTERVAL '12 hours', NOW());

SELECT setval(pg_get_serial_sequence('learning_profiles', 'id'), (SELECT MAX(id) FROM learning_profiles));


-- ==========================================
-- 9. DỮ LIỆU BẢNG `reviews` (Đánh giá khóa học)
-- ==========================================
-- Reviews hợp lệ hiển thị công khai
-- Có một review bị admin ẩn (isVisible = false) để test tính năng kiểm duyệt
INSERT INTO reviews (id, user_id, course_id, rating, comment, is_visible, created_at, updated_at) VALUES
(1, 3, 1, 5, 'Khóa học cực kỳ dễ hiểu cho người mới bắt đầu! Giảng viên dạy chi tiết.', true, NOW() - INTERVAL '5 days', NOW()),
(2, 4, 1, 4, 'Bài tập của chương 2 hơi khó và thử thách đối với mình nhưng nội dung rất tốt.', true, NOW() - INTERVAL '4 days', NOW()),
(3, 4, 2, 5, 'Khóa học AI rất xuất sắc! Các bài thực hành Python lý thuyết dễ hiểu.', true, NOW() - INTERVAL '3 days', NOW()),
(4, 3, 3, 2, 'Khóa học Python này chất lượng âm thanh bài giảng hơi nhỏ, đề nghị giảng viên cải thiện mic.', true, NOW() - INTERVAL '2 days', NOW()),
(5, 4, 3, 1, 'Spam nhảm nhí quảng cáo sản phẩm 12345!!!', false, NOW() - INTERVAL '1 days', NOW());

SELECT setval(pg_get_serial_sequence('reviews', 'id'), (SELECT MAX(id) FROM reviews));


-- ==========================================
-- 10. DỮ LIỆU BẢNG `notifications` (Thông báo)
-- ==========================================
-- Các loại thông báo: LESSON_REMINDER, EXERCISE_RESULT, CHAPTER_UNLOCKED, COURSE_UPDATE, SYSTEM
INSERT INTO notifications (id, user_id, message, type, is_read, created_at) VALUES
-- Cho Student 1 (Trần Thị B)
(1, 3, 'Chào mừng bạn đã đăng ký thành công khóa học Lập trình Java căn bản!', 'SYSTEM', false, NOW() - INTERVAL '10 days'),
(2, 3, 'Bài tập Java-1.1 của bạn đã được chấm điểm: Chính xác.', 'EXERCISE_RESULT', true, NOW() - INTERVAL '8 days'),
(3, 3, 'Bạn đã hoàn thành xuất sắc bài tập Chương 1 Java và mở khóa thành công Chương 2!', 'CHAPTER_UNLOCKED', false, NOW() - INTERVAL '8 days'),
(4, 3, 'Khóa học AI vừa cập nhật thêm nội dung chương mới, click để vào học ngay!', 'COURSE_UPDATE', false, NOW() - INTERVAL '30 minutes'),

-- Cho Student 2 (Lê Văn C)
(5, 4, 'Chào mừng bạn đã tham gia hệ thống học tập trực tuyến AI E-learning!', 'SYSTEM', true, NOW() - INTERVAL '8 days'),
(6, 4, 'Bạn đã mở khóa thành công Chương 2 khóa học Lập trình Java.', 'CHAPTER_UNLOCKED', false, NOW() - INTERVAL '5 days'),
(7, 4, 'Chúc mừng bạn đã hoàn thành 100% khóa học ReactJS!', 'SYSTEM', false, NOW() - INTERVAL '12 hours'),

-- Cho Giảng viên 1 (Teacher 1)
(8, 2, 'Học viên Trần Thị B đã gửi một câu hỏi thảo luận mới về JVM trong Chương 1.', 'LESSON_REMINDER', false, NOW() - INTERVAL '2 hours'),
(9, 2, 'Có 2 bài đánh giá khóa học mới được đăng tải cho các khóa học do bạn phụ trách.', 'COURSE_UPDATE', false, NOW() - INTERVAL '1 days'),

-- Cho Giảng viên 2 (Teacher 2)
(10, 5, 'Học viên Lê Văn C đã hoàn thành toàn bộ khóa học ReactJS do bạn giảng dạy.', 'SYSTEM', false, NOW() - INTERVAL '12 hours'),

-- Cho Admin (User 1)
(11, 1, 'Hệ thống phát hiện 1 đánh giá có chứa từ khóa vi phạm quy tắc cần kiểm duyệt gấp.', 'SYSTEM', false, NOW() - INTERVAL '1 days'),
(12, 1, 'Yêu cầu rút tiền hoặc xuất hóa đơn báo cáo tài chính tháng vừa được sinh tự động.', 'SYSTEM', true, NOW() - INTERVAL '5 hours');

SELECT setval(pg_get_serial_sequence('notifications', 'id'), (SELECT MAX(id) FROM notifications));


-- ==========================================
-- 11. DỮ LIỆU BẢNG `chat_sessions` và `chat_messages`
-- ==========================================
-- Student 1 (User 3) chat với AI trên Chapter 1 (Java)
-- Student 2 (User 4) chat với AI trên Chapter 4 (AI)
-- Student 1 (User 3) chat với AI trên Chapter 6 (Python)
INSERT INTO chat_sessions (id, user_id, chapter_id, created_at) VALUES
(1, 3, 1, NOW() - INTERVAL '3 days'),
(2, 4, 4, NOW() - INTERVAL '2 days'),
(3, 3, 6, NOW() - INTERVAL '1 days');

SELECT setval(pg_get_serial_sequence('chat_sessions', 'id'), (SELECT MAX(id) FROM chat_sessions));

INSERT INTO chat_messages (id, session_id, role, content, created_at) VALUES
-- Java Chat Session 1
(1, 1, 'USER', 'Tại sao tôi cần cài đặt JDK mà không phải chỉ JRE để lập trình Java?', NOW() - INTERVAL '3 days' + INTERVAL '1 minutes'),
(2, 1, 'ASSISTANT', 'Chào bạn! JRE (Java Runtime Environment) chỉ cung cấp môi trường để chạy ứng dụng Java. Còn để lập trình, bạn cần JDK (Java Development Kit) vì nó chứa các công cụ như trình biên dịch (javac) để dịch mã nguồn sang bytecode.', NOW() - INTERVAL '3 days' + INTERVAL '2 minutes'),
(3, 1, 'USER', 'Vậy JRE có nằm trong JDK không?', NOW() - INTERVAL '3 days' + INTERVAL '5 minutes'),
(4, 1, 'ASSISTANT', 'Đúng vậy, JDK chứa toàn bộ JRE bên trong cùng các công cụ phát triển khác, do đó bạn chỉ cần cài đặt JDK là đủ.', NOW() - INTERVAL '3 days' + INTERVAL '6 minutes'),

-- AI Chat Session 2
(5, 2, 'USER', 'Machine Learning và Deep Learning khác nhau cơ bản thế nào?', NOW() - INTERVAL '2 days' + INTERVAL '1 minutes'),
(6, 2, 'ASSISTANT', 'Machine Learning là tập hợp phương pháp cho phép máy tính tự học từ dữ liệu. Deep Learning là một tập con của ML sử dụng mạng nơ-ron nhân tạo nhiều lớp (deep neural networks) để học đặc trưng dữ liệu phức tạp hơn.', NOW() - INTERVAL '2 days' + INTERVAL '2 minutes'),

-- Python Chat Session 3
(7, 3, 'USER', 'Tại sao trong Python thụt lề đầu dòng lại vô cùng quan trọng?', NOW() - INTERVAL '1 days' + INTERVAL '10 minutes'),
(8, 3, 'ASSISTANT', 'Trong Python, thụt lề đầu dòng (indentation) được sử dụng để xác định khối mã lệnh (block of code) thay vì dùng cặp ngoặc nhọn `{}` như Java hay C++. Nếu thụt lề sai, bạn sẽ gặp lỗi IndentationError.', NOW() - INTERVAL '1 days' + INTERVAL '11 minutes');

SELECT setval(pg_get_serial_sequence('chat_messages', 'id'), (SELECT MAX(id) FROM chat_messages));


-- ==========================================
-- 12. DỮ LIỆU BẢNG `exercise_attempts`
-- ==========================================
-- Ghi nhận lịch sử làm bài tập
INSERT INTO exercise_attempts (id, user_id, exercise_id, submitted_answer, is_correct, attempted_at) VALUES
-- Student 1 làm Java Chapter 1 (Đúng hết)
(1, 3, 1, '1995', true, NOW() - INTERVAL '9 days'),
(2, 3, 2, 'Java Virtual Machine', true, NOW() - INTERVAL '8 days'),

-- Student 1 làm Python Chapter 1 (Đúng) và Chapter 2 (Có bài đúng, bài sai)
(3, 3, 6, 'if', true, NOW() - INTERVAL '7 days'),
(4, 3, 7, '[]', false, NOW() - INTERVAL '6 days'), -- Trả lời sai (cần {})
(5, 3, 7, '{}', true, NOW() - INTERVAL '6 days' + INTERVAL '10 minutes'), -- Trả lời lại đúng
(6, 3, 8, 'sort', true, NOW() - INTERVAL '5 days'),

-- Student 2 làm Java Chapter 1 (Có lần sai, lần đúng) và Chapter 2 (Đúng)
(7, 4, 1, '1996', false, NOW() - INTERVAL '7 days'), -- Sai
(8, 4, 1, '1995', true, NOW() - INTERVAL '7 days' + INTERVAL '15 minutes'), -- Sửa lại đúng
(9, 4, 3, 'double', true, NOW() - INTERVAL '6 days'),
(10, 4, 4, 'final', true, NOW() - INTERVAL '5 days');

SELECT setval(pg_get_serial_sequence('exercise_attempts', 'id'), (SELECT MAX(id) FROM exercise_attempts));

-- ==========================================
-- 13. DỮ LIỆU BẢNG `news`
-- ==========================================
INSERT INTO news (id, title, category, summary, content, image_url, is_spotlight, created_at, updated_at) VALUES
(1, 'PTIT chính thức triển khai nền tảng Đào tạo số tích hợp Trợ lý Gia sư AI vào giảng dạy chính quy', 'academy', 'Học viện Công nghệ Bưu chính Viễn thông tiên phong ứng dụng Trí tuệ Nhân tạo hỗ trợ sinh viên tự học 24/7. Hệ thống giúp cá nhân hóa lộ trình bài giảng và tự động mở khóa chương học.', 'Nội dung chi tiết bài viết tuyên truyền chuyển đổi số của Học viện PTIT...', 'https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1200&q=80', true, NOW() - INTERVAL '1 day', NOW()),
(2, 'Lễ vinh danh và trao học bổng tài năng cho sinh viên có thành tích xuất sắc', 'academy', 'Học viện trao tặng hàng trăm suất học bổng khuyến khích học tập và khen thưởng các sinh viên đạt thành tích cao trong nghiên cứu khoa học.', 'Chi tiết lễ vinh danh sinh viên xuất sắc...', 'https://images.unsplash.com/photo-1541339907198-e08756dedf3f?auto=format&fit=crop&w=800&q=80', false, NOW() - INTERVAL '3 days', NOW()),
(3, 'Sinh viên PTIT xuất sắc giành Giải Nhất Cuộc thi Sáng tạo AI Toàn quốc 2026', 'tech', 'Đội tuyển PTIT xuất sắc vượt qua 50 trường đại học với sản phẩm Trợ lý AI hỗ trợ tự học trực tuyến thông minh cho ngành viễn thông.', 'Chi tiết cuộc thi AI toàn quốc 2026...', 'https://images.unsplash.com/photo-1531482615713-2afd69097998?auto=format&fit=crop&w=800&q=80', false, NOW() - INTERVAL '5 days', NOW()),
(4, 'Chuỗi hoạt động Mùa Hè Xanh và Chiến dịch Tình nguyện Chuyển đổi số cộng đồng', 'student', 'Hơn 500 sinh viên tình nguyện PTIT ra quân tập huấn kỹ năng số, hỗ trợ người dân cài đặt ứng dụng công và phổ cập Internet.', 'Chi tiết hoạt động Mùa hè xanh...', 'https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=800&q=80', false, NOW() - INTERVAL '7 days', NOW());

SELECT setval(pg_get_serial_sequence('news', 'id'), (SELECT MAX(id) FROM news));

