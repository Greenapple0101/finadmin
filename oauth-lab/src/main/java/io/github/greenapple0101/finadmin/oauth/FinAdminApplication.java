package io.github.greenapple0101.finadmin.oauth;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

// 이 파일이 관리자 API의 시작점입니다. 화면과 데이터베이스 없이 JVM 하나로 실행합니다.
@SpringBootApplication
public class FinAdminApplication {
    public static void main(String[] args) {
        SpringApplication.run(FinAdminApplication.class, args);
    }
}
