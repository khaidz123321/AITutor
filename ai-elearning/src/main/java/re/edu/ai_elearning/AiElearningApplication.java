package re.edu.ai_elearning;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class AiElearningApplication {

    public static void main(String[] args) {
        SpringApplication.run(AiElearningApplication.class, args);
    }

}
