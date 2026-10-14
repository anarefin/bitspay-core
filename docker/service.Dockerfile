# syntax=docker/dockerfile:1
# Runtime image for a host-built jar (`make build` runs ./gradlew bootJar first). Context = services/<svc>.
FROM eclipse-temurin:25-jre AS extract
WORKDIR /w
COPY build/libs/*.jar app.jar
RUN java -Djarmode=tools -jar app.jar extract --layers --launcher --destination out

FROM eclipse-temurin:25-jre
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 bitspay
USER 10001
WORKDIR /app
COPY --from=extract /w/out/dependencies/ ./
COPY --from=extract /w/out/spring-boot-loader/ ./
COPY --from=extract /w/out/snapshot-dependencies/ ./
COPY --from=extract /w/out/application/ ./
ENTRYPOINT ["java", "org.springframework.boot.loader.launch.JarLauncher"]
