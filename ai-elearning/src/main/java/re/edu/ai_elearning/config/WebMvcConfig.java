package re.edu.ai_elearning.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.nio.file.Path;
import java.nio.file.Paths;

@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        exposeDirectory("uploads", registry);
    }

    private void exposeDirectory(String dirName, ResourceHandlerRegistry registry) {
        Path uploadDir = Paths.get(dirName);
        String uploadPath = uploadDir.toFile().getAbsolutePath();
        
        if (dirName.startsWith("../")) {
            dirName = dirName.replace("../", "");
        }
        
        // uploadPath đã là đường dẫn tuyệt đối (bắt đầu bằng "/"), nên KHÔNG được nối thêm "/" sau
        // "file:" — nếu không URL sẽ thành "file://app/uploads/..." (2 dấu / liền nhau), khiến JVM
        // hiểu nhầm "app" là hostname và fallback sang giao thức FTP để mở file, gây lỗi 500
        // UnknownHostException thay vì đọc file cục bộ.
        registry.addResourceHandler("/" + dirName + "/**")
                .addResourceLocations("file:" + uploadPath + "/");
    }
}
