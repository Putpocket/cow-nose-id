## 🐄 Cattle System

**Cattle System은 Flask 기반의 소 관리 웹 애플리케이션입니다.**  
**소의 정보를 등록하고 관리할 수 있는 간단하고 직관적인 시스템입니다.**

---

## ✏️ 주요 기능

### 👤 사용자 관리

1. **계정 시스템**
   - 사용자 등록 및 로그인
   - 세션 기반 인증
   - 권한 레벨 (User, Admin, Super)

2. **관리자 기능**
   - 계정 추가/삭제
   - 권한 설정 및 관리

### 🐄 소 데이터 관리

1. **소 정보 등록**
   - 소 ID, 이름, 소유자 정보 등록
   - 상태 및 신뢰도 관리
   - 비고사항 기록

2. **데이터 관리**
   - 소 데이터 추가/삭제
   - 실시간 데이터 조회
   - 파일 기반 데이터 저장

### 📊 웹 인터페이스

1. **대시보드**
   - 최근 등록된 소 데이터 표시
   - 사용자 정보 및 권한 표시

2. **관리자 페이지**
   - 계정 관리 인터페이스
   - 소 데이터 관리 인터페이스
   - 실시간 데이터 업데이트

---

## 🚩 시스템 구조

> **개발 환경**: Python 3.x, Flask
> **사용 언어**: Python, HTML, CSS, JavaScript

### 📁 프로젝트 구조
```
cattle_system/
├── cattle_system.py          # 메인 Flask 애플리케이션
├── module/
│   └── system_utils.py       # 유틸리티 함수들
├── data/
│   ├── UserData/            # 사용자 데이터
│   └── CattleData/          # 소 데이터
├── log/                     # 로그 파일들
│   ├── Access_log/
│   ├── Auth_log/
│   ├── Event_log/
│   └── System_log/
├── static/                  # 정적 파일들
│   ├── css/
│   └── js/
└── templates/               # HTML 템플릿들
    ├── index.html
    ├── login.html
    ├── register.html
    ├── admin.html
    └── cattle_upload.html
```

### 🔧 주요 컴포넌트

#### 웹 서버 (Flask)
- 사용자 인증 및 세션 관리
- RESTful API 엔드포인트
- 템플릿 렌더링

#### 데이터 관리
- 파일 기반 데이터 저장
- 실시간 메모리 캐싱
- JSON 기반 로그 시스템

#### 보안 기능
- SHA-256 비밀번호 암호화
- 세션 쿠키 기반 인증
- 권한 기반 접근 제어

---

## 🛠️ 설치 및 실행

### 1. 환경 설정
```bash
# setup_cattle.sh 실행 (권장)
chmod +x setup_cattle.sh
./setup_cattle.sh

# 또는 수동 설치
sudo apt update
sudo apt install python3 python3-pip
pip3 install flask
```

### 2. 애플리케이션 실행
```bash
python3 cattle_system.py
```

### 3. 웹 브라우저에서 접속
```
http://localhost:5000
```

---

## 📋 API 엔드포인트

### 사용자 관련
- `GET /` - 메인 대시보드
- `GET/POST /login` - 로그인
- `GET/POST /register` - 회원가입
- `POST /logout` - 로그아웃

### 관리자 기능
- `GET /admin_pages` - 관리자 페이지
- `GET /api/admin/accounts` - 계정 목록 조회
- `POST /api/admin/accounts` - 계정 추가
- `DELETE /api/admin/accounts/<userid>` - 계정 삭제
- `GET/POST/DELETE /api/admin/cattle` - 소 데이터 관리

### 일반 기능
- `GET /upload` - 파일 업로드 페이지
- `GET /api/cattle` - 소 데이터 조회

---

## 🔐 기본 계정

시스템 설치 후 다음 계정으로 로그인할 수 있습니다:
- **아이디**: anyang
- **비밀번호**: 1234
- **권한**: Super

---

## 📝 개발 노트

- 데이터는 파일 기반으로 저장되며 재시작 시 유지됩니다
- 로그는 시간별로 분류되어 저장됩니다
- 관리자 권한이 있어야 계정 및 소 데이터 관리가 가능합니다
- 세션은 브라우저 쿠키를 통해 유지됩니다

---

**마지막 수정일**: 2026-05-04


