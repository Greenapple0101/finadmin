package io.github.greenapple0101.finadmin.itsm;

import jakarta.persistence.*;
import java.util.UUID;

// @Entity는 이 객체 한 개를 DB 한 행과 연결합니다. ITSM이 사용하는 회사 명부입니다.
// 같은 사람이 금융 앱과 ITSM을 이용해도, 업무 데이터의 연결은 각 앱이 따로 관리합니다.
@Entity
@Table(name = "itsm_companies")
public class ItsmCompany {
    @Id private UUID id;
    @Column(nullable = false, length = 100) private String name;

    protected ItsmCompany() {} // JPA가 저장된 행을 읽을 때 사용하는 생성자입니다.
    public UUID getId() { return id; }
    public String getName() { return name; }
}
