# Stage 1: Build ứng dụng bằng Gradle
FROM gradle:8.7-jdk21 AS build
WORKDIR /app
COPY --chown=gradle:gradle . /app
RUN gradle build -x test --no-daemon

# Stage 2: Chạy ứng dụng bằng JRE siêu nhẹ
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
# Sao chép file .jar đã build sang stage 2 (bỏ qua plain.jar)
COPY --from=build /app/build/libs/*-SNAPSHOT.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
