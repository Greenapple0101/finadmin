# Gradle로 만든 실행 JAR을 독립된 Java 프로세스로 실행합니다.
FROM eclipse-temurin:21-jre-jammy
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY --chown=app:app build/libs/finadmin-0.0.1-SNAPSHOT.jar app.jar
USER app
ENTRYPOINT ["java", "-Xms64m", "-Xmx256m", "-jar", "/app/app.jar"]
