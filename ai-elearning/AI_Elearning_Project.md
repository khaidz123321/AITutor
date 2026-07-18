# Dự án AI E-learning

## 1. Giới thiệu tổng quan

Đây là nền tảng học tập trực tuyến (e-learning) tích hợp AI, cho phép người dùng học theo lộ trình **khóa học (course) → chương (chapter) → bài tập (exercise)**. Trong mỗi chương, người học có thể trò chuyện với AI (chat AI) để được hỗ trợ giải đáp thắc mắc về nội dung bài học. AI chat được kết nối với một dự án Python backend (xử lý NLP/LLM) để trả lời câu hỏi dựa trên ngữ cảnh chương học. Sau khi học xong một chương, người dùng phải hoàn thành bài tập (exercise) của chương đó; nếu trả lời đúng, hệ thống sẽ mở khóa và cho phép chuyển sang chương tiếp theo.

## 2. Mô hình dữ liệu (Entity)

Dựa trên sơ đồ ERD/class diagram được cung cấp, hệ thống gồm các thực thể chính sau:

### 2.1. `user`
Thông tin tài khoản người dùng.
- `field: type` (id, email, password_hash, full_name, created_at, ...)

### 2.2. `user_profile`
Hồ sơ chi tiết của người dùng (mở rộng từ `user`).
- Item 1: thông tin cá nhân (avatar, ngày sinh, giới tính...)
- Item 2: thông tin liên hệ
- Item 3: thông tin bổ sung khác

### 2.3. `role`
Vai trò trong hệ thống (admin, học viên, giảng viên...).
- `field: type` (id, name, description, ...)

### 2.4. `user_role`
Bảng liên kết nhiều-nhiều giữa `user` và `role`.
- `field: type` (user_id, role_id, ...)

### 2.5. `learning_profile`
Hồ sơ học tập, lưu tiến độ và mức độ hiểu bài của người dùng để cá nhân hóa lộ trình học (do AI phân tích).
- `field: type`
- `method(type): type` — ví dụ: `updateProgress(courseId): void`, `getLearningPath(): List<Course>`

### 2.6. `course`
Khóa học, chứa nhiều `chapter`.
- `field: type` (id, title, description, level, ...)
- `method(type): type` — ví dụ: `getChapters(): List<Chapter>`

### 2.7. `chaper` (chapter)
Chương học, thuộc về một `course`, chứa nội dung bài học và liên kết tới `exercise` + `chat AI`.

| Field | Type | Ví dụ |
|---|---|---|
| `id` | UUID/int | — |
| `course_id` | FK → course | — |
| `subject_name` | string | "Giải tích 1" |
| `chapter_number` | int | 1 |
| `chapter_name` | string | "Tính chất của hàm số" |
| `content` | text | nội dung bài học |
| `order_index` | int | thứ tự chương trong course |
| `is_locked` | boolean | true/false |
| `created_at` / `updated_at` | datetime | — |

- `method(type): type` — ví dụ: `getExercises(): List<Exercise>`, `unlockNext(): void`

### 2.8. `exercise`
Bài tập/câu hỏi kiểm tra trong mỗi chương (một chương có thể có nhiều exercise).

| Field | Type | Ví dụ |
|---|---|---|
| `id` | UUID/int | — |
| `chapter_id` | FK → chaper | — |
| `exercise_code` | string | "1.1", "1.2" |
| `exercise_name` | string | "Số thực", "Số phức" |
| `difficulty` | enum | Easy / Medium / Hard |
| `bloom_level` | enum (dropdown) | Remembering / Understanding / Applying / Analyzing / Evaluating |
| `question` | text | nội dung câu hỏi |
| `correct_answer` | string/text | đáp án đúng |
| `created_at` / `updated_at` | datetime | — |

- `method(type): type` — ví dụ: `checkAnswer(answer): boolean`, `getNextExercise(): Exercise`

### 2.9. `notifications`
Thông báo gửi tới người dùng (nhắc học, kết quả bài tập, mở khóa chương mới...).
- `field: type` (id, user_id, message, is_read, created_at, ...)
- `method(type): type` — ví dụ: `markAsRead(): void`

### 2.10. `review`
Đánh giá/nhận xét của người dùng về khóa học hoặc chương học.
- `field: type` (id, user_id, course_id, rating, comment, ...)
- `method(type): type` — ví dụ: `submitReview(): void`

## 3. Luồng nghiệp vụ chính

### 3.1. Luồng học tập theo chương
1. Người dùng đăng nhập (`user`, `user_profile`, `role`/`user_role` xác định quyền truy cập).
2. Hệ thống lấy danh sách `chapter` thuộc `course` đã đăng ký, dựa trên `learning_profile` để gợi ý lộ trình phù hợp.
3. Người dùng học nội dung của `chapter` hiện tại.
4. Trong quá trình học, người dùng có thể mở **Chat AI** để đặt câu hỏi liên quan tới nội dung chương.
5. Sau khi học xong, người dùng lần lượt làm các `exercise` của chương (mỗi chương có thể gồm nhiều bài, ví dụ 1.1, 1.2..., được phân loại theo `difficulty` và `bloom_level`).
6. Hệ thống kiểm tra đáp án từng bài (`checkAnswer`):
   - Nếu **đúng tất cả** → cập nhật `learning_profile`, mở khóa (`is_locked = false`) chương tiếp theo, gửi `notifications` thông báo hoàn thành.
   - Nếu **sai** → cho phép làm lại hoặc gợi ý ôn tập (có thể gợi ý hỏi thêm Chat AI), có thể ưu tiên ôn theo `bloom_level` chưa đạt.
7. Người dùng có thể để lại `review` cho khóa học/chương sau khi hoàn thành.

### 3.2. Luồng Chat AI
1. Người dùng gửi câu hỏi từ giao diện chương học (`chapter`).
2. Frontend gửi request kèm `chapter_id` + nội dung câu hỏi tới **AI Service (Python backend)**.
3. Python service:
   - Lấy ngữ cảnh nội dung chương (`chapter.content`) làm tài liệu tham chiếu (retrieval/RAG).
   - Gọi LLM (ví dụ Claude API) để sinh câu trả lời dựa trên ngữ cảnh.
   - Trả kết quả về cho frontend.
4. Lịch sử hội thoại có thể được lưu lại để phục vụ cá nhân hóa (`learning_profile`) và phân tích sau này.

### 3.3. Luồng mở khóa chương
- Mỗi `chapter` có cờ `is_locked`.
- Chương đầu tiên của `course` mặc định mở khóa.
- Một `chapter` chỉ được mở khóa khi `exercise` của chương liền trước được trả lời đúng.

## 4. Module quản lý dành cho Admin/Teacher

### 4.1. Mục tiêu
Cung cấp một khu vực quản trị (admin panel) riêng để `admin` và `teacher` (xác định qua `role`/`user_role`) có thể tạo mới, chỉnh sửa, xóa dữ liệu khóa học mà không cần can thiệp trực tiếp vào database. Toàn bộ API quản trị được bảo vệ bằng **Spring Boot + Spring Security + JWT**.

### 4.2. Phân quyền theo vai trò

| Vai trò | Quyền hạn |
|---|---|
| `admin` | Toàn quyền: quản lý user, role, course, chapter, exercise, xem thống kê, duyệt review |
| `teacher` | Quản lý course/chapter/exercise do mình phụ trách; xem tiến độ học viên; không quản lý user/role hệ thống |
| `student` (mặc định) | Chỉ truy cập các API học tập, không truy cập API quản trị |

Phân quyền được thực hiện bằng `@PreAuthorize("hasRole('ADMIN')")` hoặc `hasAnyRole('ADMIN','TEACHER')` ở từng endpoint/controller method, dựa trên claim `role` được nhúng trong JWT token.

### 4.3. Cơ chế xác thực & bảo mật với Spring Security + JWT

**Luồng đăng nhập:**
1. Người dùng gửi `email`/`password` tới `POST /api/auth/login`.
2. `AuthenticationManager` của Spring Security xác thực với `UserDetailsService` (đọc từ bảng `user`, `user_role`, `role`).
3. Nếu hợp lệ, hệ thống sinh:
   - **Access Token** (JWT, thời hạn ngắn ~15-30 phút) chứa claim `userId`, `email`, `roles`.
   - **Refresh Token** (thời hạn dài hơn, ~7 ngày), lưu ở DB/Redis để hỗ trợ thu hồi (revoke).
4. Client lưu token (HttpOnly cookie hoặc Authorization header `Bearer <token>`) và đính kèm trong các request tiếp theo.

**Luồng xác thực mỗi request:**
- `JwtAuthenticationFilter` (custom `OncePerRequestFilter`) chặn request, đọc token từ header `Authorization`.
- Validate chữ ký, thời hạn token bằng `JwtUtils` (dùng thư viện `io.jsonwebtoken:jjwt`).
- Nếu hợp lệ → set `Authentication` vào `SecurityContextHolder` với danh sách quyền (`GrantedAuthority`) tương ứng `role`.
- `SecurityFilterChain` cấu hình các endpoint:
  - `/api/auth/**` → public.
  - `/api/student/**` → yêu cầu đăng nhập (mọi role).
  - `/api/admin/**` → yêu cầu `ROLE_ADMIN`.
  - `/api/teacher/**` → yêu cầu `ROLE_ADMIN` hoặc `ROLE_TEACHER`.

**Các biện pháp bảo mật bổ sung:**
- Mật khẩu lưu dạng băm `BCryptPasswordEncoder`.
- Refresh token rotation + blacklist khi logout (lưu Redis hoặc bảng `revoked_token`).
- Giới hạn tần suất đăng nhập sai (rate limiting) để chống brute-force.
- CORS cấu hình chỉ cho phép domain frontend hợp lệ.
- Ghi log audit (ai sửa course/chapter/exercise nào, lúc nào) để truy vết thay đổi nội dung.

### 4.4. Chức năng quản trị chính

**Quản lý nội dung học:**
- CRUD `course` (tạo/sửa/xóa/ẩn-hiện khóa học).
- CRUD `chaper`: thêm chương mới, sắp xếp lại `order_index`, khóa/mở khóa thủ công (`is_locked`), chỉnh sửa `content`.
- CRUD `exercise`: thêm/sửa câu hỏi theo `difficulty` và `bloom_level`, cập nhật `correct_answer`.

**Quản lý người dùng (admin):**
- CRUD `user`, gán/thu hồi `role` qua `user_role`.
- Khóa/mở khóa tài khoản vi phạm.

**Theo dõi & báo cáo:**
- Xem tiến độ học tập của học viên (dựa trên `learning_profile`).
- Thống kê tỷ lệ trả lời đúng/sai theo `exercise`, theo `bloom_level` để đánh giá độ khó nội dung.
- Quản lý/duyệt `review` (ẩn review không phù hợp).
- Gửi `notifications` hàng loạt (thông báo cập nhật khóa học, bảo trì hệ thống...).

### 4.5. Quy ước chung về API & Versioning

- Tất cả API đều được tiền tố version: **`/api/v1/...`** (cho phép nâng cấp `v2` sau này mà không phá vỡ client cũ).
- Phân nhóm theo đối tượng dùng:
  - `/api/v1/auth/**` — xác thực (public).
  - `/api/v1/public/**` — dữ liệu công khai, không cần đăng nhập (vd. danh sách course để xem trước).
  - `/api/v1/student/**` — API dành cho học viên (yêu cầu đăng nhập, role `STUDENT`/bất kỳ).
  - `/api/v1/admin/**` — API quản trị toàn hệ thống (yêu cầu `ROLE_ADMIN`).
  - `/api/v1/teacher/**` — API quản lý nội dung do giáo viên phụ trách (yêu cầu `ROLE_ADMIN` hoặc `ROLE_TEACHER`).
  - `/api/v1/ai/**` — API giao tiếp với AI Service (Python) qua Backend, dành cho học viên đã đăng nhập.
- Response chuẩn hóa dạng `{ "status": "success", "data": {...}, "message": "" }` kèm HTTP status code phù hợp; lỗi trả `{ "status": "error", "errorCode": "...", "message": "..." }`.
- Hỗ trợ phân trang cho các API danh sách: query param `?page=0&size=20&sort=createdAt,desc`.
- Toàn bộ API trừ nhóm `auth`/`public` đều yêu cầu header `Authorization: Bearer <access_token>`.

## 5. Danh sách API đầy đủ theo từng Entity (v1)

### 5.1. Auth & Token (liên quan `user`, `role`, `user_role`)

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Public | Đăng ký tài khoản học viên mới |
| POST | `/api/v1/auth/login` | Public | Đăng nhập, trả `access_token` + `refresh_token` |
| POST | `/api/v1/auth/refresh` | Public (kèm refresh token) | Cấp lại access token mới |
| POST | `/api/v1/auth/logout` | Đã đăng nhập | Thu hồi (revoke) refresh token hiện tại |
| POST | `/api/v1/auth/forgot-password` | Public | Gửi email đặt lại mật khẩu |
| POST | `/api/v1/auth/reset-password` | Public (kèm reset token) | Đặt lại mật khẩu mới |
| GET | `/api/v1/auth/me` | Đã đăng nhập | Lấy thông tin user + role hiện tại từ token |

### 5.2. `user`

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/admin/users` | ADMIN | Danh sách user (phân trang, filter theo role) |
| GET | `/api/v1/admin/users/{id}` | ADMIN | Chi tiết một user |
| POST | `/api/v1/admin/users` | ADMIN | Tạo user mới (vd. tạo tài khoản teacher) |
| PUT | `/api/v1/admin/users/{id}` | ADMIN | Cập nhật thông tin user |
| PATCH | `/api/v1/admin/users/{id}/status` | ADMIN | Khóa/mở khóa tài khoản |
| DELETE | `/api/v1/admin/users/{id}` | ADMIN | Xóa (hoặc vô hiệu hóa) user |
| PUT | `/api/v1/student/users/me` | Học viên (chính mình) | Cập nhật thông tin cá nhân của bản thân |
| PUT | `/api/v1/student/users/me/password` | Học viên (chính mình) | Đổi mật khẩu |

### 5.3. `user_profile`

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/student/users/me/profile` | Học viên | Xem hồ sơ cá nhân của mình |
| PUT | `/api/v1/student/users/me/profile` | Học viên | Cập nhật hồ sơ cá nhân (avatar, ngày sinh, liên hệ...) |
| GET | `/api/v1/admin/users/{id}/profile` | ADMIN | Xem hồ sơ chi tiết của một user bất kỳ |
| PUT | `/api/v1/admin/users/{id}/profile` | ADMIN | Admin chỉnh sửa hồ sơ của user |

### 5.4. `role` & `user_role`

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/admin/roles` | ADMIN | Danh sách role hệ thống |
| POST | `/api/v1/admin/roles` | ADMIN | Tạo role mới |
| PUT | `/api/v1/admin/roles/{id}` | ADMIN | Cập nhật role |
| DELETE | `/api/v1/admin/roles/{id}` | ADMIN | Xóa role (nếu không còn user nào dùng) |
| GET | `/api/v1/admin/users/{id}/roles` | ADMIN | Xem danh sách role hiện tại của user |
| PUT | `/api/v1/admin/users/{id}/roles` | ADMIN | Gán/cập nhật role cho user (ghi vào `user_role`) |
| DELETE | `/api/v1/admin/users/{id}/roles/{roleId}` | ADMIN | Thu hồi một role khỏi user |

### 5.5. `learning_profile`

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/student/learning-profile` | Học viên | Xem hồ sơ học tập của mình (tiến độ, mức độ hiểu bài) |
| GET | `/api/v1/student/learning-profile/path` | Học viên | Lấy lộ trình học gợi ý (`getLearningPath`) |
| POST | `/api/v1/student/learning-profile/progress` | Học viên / hệ thống nội bộ | Cập nhật tiến độ sau khi học/làm bài (`updateProgress`) |
| GET | `/api/v1/teacher/learning-profiles` | ADMIN, TEACHER | Xem hồ sơ học tập của các học viên trong khóa phụ trách |
| GET | `/api/v1/admin/learning-profiles/{userId}` | ADMIN | Xem chi tiết hồ sơ học tập của một học viên |

### 5.6. `course`

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/public/courses` | Public | Danh sách course công khai (xem trước) |
| GET | `/api/v1/public/courses/{id}` | Public | Chi tiết course (mô tả, danh sách chương rút gọn) |
| GET | `/api/v1/student/courses` | Học viên | Danh sách course đã đăng ký |
| POST | `/api/v1/student/courses/{id}/enroll` | Học viên | Đăng ký tham gia course |
| GET | `/api/v1/student/courses/{id}/chapters` | Học viên | Lấy danh sách chương kèm trạng thái khóa/mở (`getChapters`) |
| POST | `/api/v1/admin/courses` | ADMIN, TEACHER | Tạo course mới |
| PUT | `/api/v1/admin/courses/{id}` | ADMIN, TEACHER (chủ sở hữu) | Cập nhật course |
| DELETE | `/api/v1/admin/courses/{id}` | ADMIN | Xóa course |
| PATCH | `/api/v1/admin/courses/{id}/visibility` | ADMIN, TEACHER | Ẩn/hiện course |

### 5.7. `chaper` (chapter)

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/student/chapters/{id}` | Học viên | Xem chi tiết nội dung một chương (nếu đã mở khóa) |
| GET | `/api/v1/student/chapters/{id}/exercises` | Học viên | Lấy danh sách exercise của chương (`getExercises`) |
| POST | `/api/v1/admin/courses/{courseId}/chapters` | ADMIN, TEACHER | Thêm chương mới vào course |
| PUT | `/api/v1/admin/chapters/{id}` | ADMIN, TEACHER | Cập nhật nội dung/tên chương (`subject_name`, `chapter_name`, `content`...) |
| DELETE | `/api/v1/admin/chapters/{id}` | ADMIN, TEACHER | Xóa chương |
| PATCH | `/api/v1/admin/chapters/{id}/order` | ADMIN, TEACHER | Sắp xếp lại `order_index` |
| PATCH | `/api/v1/admin/chapters/{id}/lock` | ADMIN, TEACHER | Khóa/mở khóa thủ công (`is_locked`) |

### 5.8. `exercise`

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/student/exercises/{id}` | Học viên | Xem chi tiết một câu hỏi (ẩn `correct_answer`) |
| POST | `/api/v1/student/exercises/{id}/submit` | Học viên | Nộp đáp án, kiểm tra (`checkAnswer`), trả về đúng/sai |
| GET | `/api/v1/student/chapters/{chapterId}/exercises/next` | Học viên | Lấy câu hỏi tiếp theo trong chương (`getNextExercise`) |
| POST | `/api/v1/admin/chapters/{chapterId}/exercises` | ADMIN, TEACHER | Thêm exercise mới cho chương (kèm `difficulty`, `bloom_level`) |
| PUT | `/api/v1/admin/exercises/{id}` | ADMIN, TEACHER | Cập nhật câu hỏi/đáp án/độ khó/bloom_level |
| DELETE | `/api/v1/admin/exercises/{id}` | ADMIN, TEACHER | Xóa exercise |
| GET | `/api/v1/admin/exercises/{id}/stats` | ADMIN, TEACHER | Thống kê tỷ lệ trả lời đúng/sai của câu hỏi |

### 5.9. `notifications`

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/student/notifications` | Học viên | Danh sách thông báo của mình (phân trang) |
| PATCH | `/api/v1/student/notifications/{id}/read` | Học viên | Đánh dấu đã đọc (`markAsRead`) |
| PATCH | `/api/v1/student/notifications/read-all` | Học viên | Đánh dấu đã đọc toàn bộ |
| DELETE | `/api/v1/student/notifications/{id}` | Học viên | Xóa một thông báo |
| POST | `/api/v1/admin/notifications` | ADMIN | Gửi thông báo tới một/nhiều user cụ thể |
| POST | `/api/v1/admin/notifications/broadcast` | ADMIN | Gửi thông báo hàng loạt (toàn hệ thống/theo course) |

### 5.10. `review`

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/public/courses/{id}/reviews` | Public | Xem review công khai của một course |
| POST | `/api/v1/student/courses/{id}/reviews` | Học viên | Gửi đánh giá/nhận xét (`submitReview`) |
| PUT | `/api/v1/student/reviews/{id}` | Học viên (chủ review) | Sửa review của mình |
| DELETE | `/api/v1/student/reviews/{id}` | Học viên (chủ review) | Xóa review của mình |
| GET | `/api/v1/admin/reviews` | ADMIN | Danh sách toàn bộ review để kiểm duyệt |
| PATCH | `/api/v1/admin/reviews/{id}/visibility` | ADMIN | Ẩn/hiện review không phù hợp |
| DELETE | `/api/v1/admin/reviews/{id}` | ADMIN | Xóa review vi phạm |

### 5.11. Chat AI (giao tiếp Backend Spring Boot ↔ AI Service Python)

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/v1/ai/chat` | Học viên | Gửi câu hỏi kèm `chapter_id`, backend forward sang AI Service (Python) và trả lời |
| GET | `/api/v1/ai/chat/history?chapterId=` | Học viên | Lấy lịch sử hội thoại của mình theo chương |
| DELETE | `/api/v1/ai/chat/history/{sessionId}` | Học viên | Xóa một phiên hội thoại |
| (internal) POST | `http://ai-service/v1/answer` | Service-to-service (API key) | Backend gọi nội bộ tới AI Service (Python) để lấy câu trả lời RAG/LLM |

### 5.12. Báo cáo & thống kê (tổng hợp nhiều entity)

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/admin/reports/progress` | ADMIN, TEACHER | Báo cáo tiến độ học viên theo course/chapter |
| GET | `/api/v1/admin/reports/exercise-difficulty` | ADMIN, TEACHER | Thống kê độ khó thực tế theo `bloom_level` |
| GET | `/api/v1/admin/reports/courses-summary` | ADMIN | Thống kê tổng quan: số course, số học viên, đánh giá trung bình |

## 6. Kiến trúc hệ thống đề xuất

```
┌─────────────┐      REST (JWT)        ┌──────────────────────────┐
│  Frontend    │ ─────────────────────▶│  Backend API (Spring Boot) │
│ (Web Admin/  │◀───────────────────── │  + Spring Security + JWT   │
│  Học viên)   │                       │  (quản lý user, role,      │
└─────────────┘                        │  course, chapter,          │
                                        │  exercise, review,         │
                                        │  notifications)            │
                                        └─────────┬──────────────────┘
                                                  │
                                                  │ gọi nội bộ khi cần Chat AI
                                                  ▼
                                        ┌──────────────────┐
                                        │  AI Service        │
                                        │  (Python: RAG +    │
                                        │  LLM/Claude API)    │
                                        └──────────────────┘
```

- **Backend API (Spring Boot)**: quản lý toàn bộ nghiệp vụ (CRUD user, course, chapter, exercise, notifications, review); xác thực/phân quyền bằng Spring Security + JWT, áp dụng cho cả API học viên và API quản trị (admin/teacher).
- **AI Service (Python)**: chuyên trách xử lý Chat AI, nhận `chapter_id` + câu hỏi, trả lời dựa trên nội dung chương (RAG) hoặc kiến thức tổng quát. Giao tiếp với Backend API qua REST nội bộ, có thể xác thực bằng service token/API key riêng.
- **Database**: lưu trữ toàn bộ entity nêu ở mục 2.
- **Redis (tùy chọn)**: lưu refresh token, blacklist token, cache phiên đăng nhập.

## 7. Hướng phát triển tiếp theo
- Bổ sung chi tiết kiểu dữ liệu cụ thể cho từng `field` trong các entity.
- Thiết kế API endpoint chi tiết cho từng luồng (auth, course, chat, exercise).
- Xây dựng cơ chế lưu lịch sử chat và dùng nó để cá nhân hóa `learning_profile`.
- Thiết kế cơ chế thông báo real-time (`notifications`) qua WebSocket hoặc push notification.
- Bổ sung 2FA cho tài khoản admin/teacher để tăng cường bảo mật.
- Xây dựng giao diện admin dashboard (React/Vue) thao tác trực tiếp với API quản trị Spring Boot.
- Khi có thay đổi lớn về hợp đồng API, phát hành `/api/v2/...` song song và duy trì `/api/v1/...` trong giai đoạn chuyển tiếp (deprecation period) để không phá vỡ client cũ.
- Viết tài liệu API tự động bằng Swagger/OpenAPI (springdoc-openapi) gắn theo từng version.
