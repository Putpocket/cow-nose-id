# Cow Nose ID (Frontend + Backend 통합 안내)

이 저장소는 Flask 백엔드 API와 프론트엔드 화면 병합을 전제로 동작합니다.

## 1) 실행 방법 (Backend)
```bash
pip install -r requirements.txt
flask --app app.web:create_app run
```

## 2) 프론트엔드 연동 규칙 (Frontend)
프론트는 반드시 아래 규칙으로 백엔드를 호출합니다.

- 세션 쿠키 사용: `credentials: include`
- 상태 변경 요청(POST/PUT/PATCH/DELETE): `X-CSRF-Token` 헤더 포함
- 이미지 업로드 필드명: `file`
- 권한 처리:
  - 401 -> `/login` 이동
  - 403 -> `/block` 표시

## 3) API 계약 (Backend)

### Health
- `GET /health`

### Auth
- `GET /api/csrf-token`
- `POST /auth/login`
- `GET /auth/me`
- `GET /me` (alias)
- `POST /auth/logout`
- `POST /auth/change-password`

### Admin Accounts
- `GET /admin/accounts`
- `POST /admin/accounts`
- `DELETE /admin/accounts/{id}`
- 호환 alias: `/api/admin/accounts/*`

### Admin Cows
- `GET /admin/cows`
- `POST /admin/cows`
- `GET /admin/cows/{id}`
- `PUT /admin/cows/{id}`
- `DELETE /admin/cows/{id}`
- 호환 alias: `/api/admin/cattle/*`

### Identify
- `POST /api/identify`

## 4) users 스키마 버전 이슈 대응
현재 `app/web.py`는 users 테이블 컬럼이 아래 두 형태 중 어느 쪽이든 동작하도록 처리되어 있습니다.

- 구형: `is_active`, `login_attempts`
- 신형: `status`, `failed_attempts`

운영에서는 한쪽 스키마로 통일하는 것을 권장합니다.

## 5) SQL 파일 관련
`sql/schema.sql`은 팀 내 별도 담당 작업 기준이 있을 수 있으므로,
**추가 수정이 필요하면 먼저 담당자 확인 후 반영**합니다.

## 6) 현재 파이프라인 상태
`process_image`는 detect -> crop -> embed -> search -> DB 조회 흐름으로 연결되어 있으며,
YOLO/DINO/FAISS 서비스 모듈은 교체 가능한 구조입니다.
