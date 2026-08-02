package re.edu.ai_elearning.config;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;
import re.edu.ai_elearning.security.JwtAuthenticationFilter;

import java.util.Arrays;
import java.util.List;

@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;

    @Bean
    public AuthenticationManager authenticationManager(AuthenticationConfiguration configuration) throws Exception {
        return configuration.getAuthenticationManager();
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(AbstractHttpConfigurer::disable)
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                // 1. Public static web pages & assets
                .requestMatchers(
                    "/",
                    "/index.html",
                    "/login.html",
                    "/register.html",
                    "/*.html",
                    "/css/**",
                    "/js/**",
                    "/assets/**",
                    "/components/**",
                    "/uploads/**",
                    "/favicon.ico"
                ).permitAll()

                // 2. Public REST API endpoints
                .requestMatchers("/api/v1/auth/**").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/v1/courses").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/v1/courses/{id}").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/v1/courses/{id}/reviews").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/v1/reviews/course/{courseId}").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/v1/news/**").permitAll()
                .requestMatchers(HttpMethod.POST, "/api/v1/support-tickets").permitAll()
                .requestMatchers("/api-docs/**", "/swagger-ui/**", "/swagger-ui.html").permitAll()

                // 3. Student & general authenticated endpoints
                .requestMatchers("/api/v1/student/**").authenticated()
                .requestMatchers("/api/v1/support-tickets/**").authenticated()

                // 3. Admin specific endpoints
                .requestMatchers("/api/v1/users/me/**").authenticated() // Phải khai báo /me trước /{id}
                .requestMatchers("/api/v1/users/**").hasRole("ADMIN")
                .requestMatchers(HttpMethod.POST, "/api/v1/news/**").hasRole("ADMIN")
                .requestMatchers(HttpMethod.PUT, "/api/v1/news/**").hasRole("ADMIN")
                .requestMatchers(HttpMethod.DELETE, "/api/v1/news/**").hasRole("ADMIN")
                .requestMatchers(HttpMethod.POST, "/api/v1/notifications").hasRole("ADMIN")
                .requestMatchers(HttpMethod.POST, "/api/v1/notifications/broadcast").hasRole("ADMIN")
                .requestMatchers(HttpMethod.GET, "/api/v1/reviews").hasRole("ADMIN")
                .requestMatchers(HttpMethod.PATCH, "/api/v1/reviews/{id}/visibility").hasRole("ADMIN")
                .requestMatchers(HttpMethod.DELETE, "/api/v1/reviews/{id}/admin").hasRole("ADMIN")
                .requestMatchers("/api/v1/reports/courses-summary").hasRole("ADMIN")

                // 4. Admin & Teacher endpoints
                .requestMatchers(HttpMethod.GET, "/api/v1/courses/all").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.POST, "/api/v1/courses").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.PUT, "/api/v1/courses/{id}").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.PATCH, "/api/v1/courses/{id}/visibility").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.POST, "/api/v1/courses/{courseId}/chapters").hasAnyRole("ADMIN", "TEACHER")
                
                .requestMatchers(HttpMethod.POST, "/api/v1/chapters").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.PUT, "/api/v1/chapters/{id}").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.DELETE, "/api/v1/chapters/{id}").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.PATCH, "/api/v1/chapters/{id}/order").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.PATCH, "/api/v1/chapters/{id}/lock").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.POST, "/api/v1/chapters/{chapterId}/exercises").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.POST, "/api/v1/chapters/{chapterId}/exercises-ai/import-pdf").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.POST, "/api/v1/chapters/{chapterId}/exercises-ai/generate-auto").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.POST, "/api/v1/chapters/{chapterId}/exercises-ai/sync").hasAnyRole("ADMIN", "TEACHER")

                .requestMatchers(HttpMethod.POST, "/api/v1/exercises").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.PUT, "/api/v1/exercises/{id}").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.DELETE, "/api/v1/exercises/{id}").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers(HttpMethod.GET, "/api/v1/exercises/{id}/stats").hasAnyRole("ADMIN", "TEACHER")

                .requestMatchers("/api/v1/learning-profiles/course/{courseId}").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers("/api/v1/reports/progress").hasAnyRole("ADMIN", "TEACHER")
                .requestMatchers("/api/v1/reports/exercise-difficulty").hasAnyRole("ADMIN", "TEACHER")

                // 5. Authenticated endpoints
                .requestMatchers(HttpMethod.GET, "/api/v1/courses/enrolled").authenticated()
                .requestMatchers(HttpMethod.POST, "/api/v1/courses/{id}/enroll").authenticated()
                .requestMatchers(HttpMethod.POST, "/api/v1/courses/{id}/reviews").authenticated()
                .requestMatchers(HttpMethod.GET, "/api/v1/courses/{id}/chapters").authenticated()

                .requestMatchers(HttpMethod.GET, "/api/v1/chapters/{id}").authenticated()
                .requestMatchers(HttpMethod.GET, "/api/v1/chapters/{id}/exercises").authenticated()
                .requestMatchers(HttpMethod.GET, "/api/v1/chapters/{id}/exercises/next").authenticated()

                .requestMatchers(HttpMethod.GET, "/api/v1/exercises/{id}").authenticated()
                .requestMatchers(HttpMethod.POST, "/api/v1/exercises/{id}/submit").authenticated()

                .requestMatchers(HttpMethod.POST, "/api/v1/reviews/course/{courseId}").authenticated()
                .requestMatchers(HttpMethod.PUT, "/api/v1/reviews/{id}").authenticated()
                .requestMatchers(HttpMethod.DELETE, "/api/v1/reviews/{id}").authenticated()

                .requestMatchers("/api/v1/learning-profiles/me/**").authenticated()
                .requestMatchers("/api/v1/notifications/**").authenticated()
                .requestMatchers("/api/v1/ai/chat/**").authenticated()

                .anyRequest().authenticated()
            );

        http.addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        // Cấu hình từ application.properties hoặc mặc định
        configuration.setAllowedOrigins(List.of(
                "http://localhost:8080",
                "http://localhost:3000",
                "http://localhost:5173"
        ));
        configuration.setAllowedMethods(Arrays.asList("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(Arrays.asList("Authorization", "Content-Type", "Cache-Control"));
        configuration.setExposedHeaders(List.of("Authorization"));
        configuration.setAllowCredentials(true);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }
}
