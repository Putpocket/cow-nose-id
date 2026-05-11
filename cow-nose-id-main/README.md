# Cow Nose ID

소 비문 이미지를 업로드해 개체를 식별하고, 관리자 화면에서 계정과 소 데이터를 관리하는 Flask 기반 프로젝트입니다.

## How To Run

### DB 없이 프론트 테스트 실행

PostgreSQL이 아직 준비되지 않았고 화면/로그인/관리자 UI를 먼저 확인하고 싶다면 테스트 서버를 실행합니다.

```powershell
python testrun.py
```

테스트 서버는 메모리 데이터를 사용하므로 DB가 필요하지 않습니다.

테스트 계정:

- 관리자: `admin` / `admin`
- 일반 사용자: `user` / `user`

테스트 서버에서 확인 가능한 기능:

- 로그인
- 일반 사용자 메인 화면 진입
- 테스트 이미지 식별 응답
- 관리자 화면 진입
- 계정 목록/생성/삭제
- 소 목록/등록/수정/삭제

테스트 서버에서 만든 데이터는 서버를 종료하면 사라집니다.
실제 PostgreSQL 연동 테스트는 아래 빠른 실행 방법을 사용합니다.

### 빠른 실행

아래 명령 하나로 `.env` 생성, 패키지 확인/설치, 런타임 폴더 생성, DB 스키마 적용, 관리자 계정 생성, Flask 서버 실행까지 진행합니다.

```powershell
python run.py
```

기본 접속 주소:

- 일반 사용자 화면: `http://127.0.0.1:5000/`
- 로그인 화면: `http://127.0.0.1:5000/login`
- 관리자 화면: `http://127.0.0.1:5000/admin`
- 헬스 체크: `http://127.0.0.1:5000/health`

기본 관리자 계정은 `.env`의 아래 값으로 생성됩니다.

- `BOOTSTRAP_ADMIN_USERNAME=admin`
- `BOOTSTRAP_ADMIN_PASSWORD=admin`

개발용 기본값이므로 실제 공유 환경에서는 반드시 비밀번호를 바꾸세요.

### 실행 옵션

패키지 설치를 건너뛰고 실행:

```powershell
python run.py --skip-install
```

DB 스키마 적용과 관리자 계정 생성을 건너뛰고 실행:

```powershell
python run.py --skip-db
```

포트 변경:

```powershell
python run.py --port 8000
```

외부 기기에서 접속 가능하게 실행:

```powershell
python run.py --host 0.0.0.0
```

### 수동 실행

문제가 생겼을 때는 아래 순서로 직접 실행할 수 있습니다.

1. 가상환경 생성 및 활성화

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. 패키지 설치

```powershell
python -m pip install -r requirements.txt
```

3. 환경 변수 파일 준비

```powershell
Copy-Item .env.example .env
```

개발 환경에 맞게 최소한 아래 값을 확인합니다.

- `DATABASE_URL`: PostgreSQL 접속 주소
- `SECRET_KEY`: Flask 세션용 비밀키
- `UPLOAD_DIR`: 업로드 저장 경로
- `MAX_UPLOAD_MB`: 업로드 최대 용량
- `ALLOWED_IMAGE_EXTENSIONS`: 허용 이미지 확장자

4. PostgreSQL DB 준비

PostgreSQL에서 `cow_nose_id` 데이터베이스를 만든 뒤 스키마를 적용합니다.

```powershell
psql -U postgres -d cow_nose_id -f sql/schema.sql
```

`psql` 명령을 사용할 수 없다면 PostgreSQL 관리 도구에서 `sql/schema.sql` 내용을 실행해도 됩니다.

5. 관리자 계정 준비

현재 공개 회원가입은 제거되어 있으므로 로그인 테스트를 하려면 `users` 테이블에 관리자 계정이 필요합니다.
비밀번호 해시는 프로젝트의 Werkzeug 해시 함수를 사용해 생성합니다.

```powershell
python -c "from app.security import hash_password; print(hash_password('admin1234'))"
```

출력된 해시를 사용해 DB에 관리자 계정을 추가합니다.

```sql
INSERT INTO users (username, password_hash, role, status, must_change_password)
VALUES ('admin', '<위에서_생성한_해시>', 'admin', 'active', false);
```

6. 서버 실행

```powershell
flask --app app:create_app run --debug
```

### 실행 시 주의사항

이미지 식별 API인 `POST /api/identify`는 백엔드 파이프라인, 모델, FAISS 인덱스 준비 상태에 영향을 받습니다.
모델 파일이나 인덱스가 아직 준비되지 않은 개발 환경에서는 화면과 로그인/관리자 API는 확인할 수 있지만, 실제 식별은 실패할 수 있습니다.

관리자 계정/소 관리 API는 프론트 테스트를 위해 `app/api/admin.py`에 최소 구현되어 있습니다.
최종 보안 정책, CSRF, 감사 로그 상세 정책, 인덱스 갱신 연동은 백엔드 담당자가 교체 또는 보강해야 합니다.

`run.py`는 PostgreSQL 데이터베이스 자체를 새로 만들지는 않습니다.
`DATABASE_URL`이 가리키는 DB는 미리 생성되어 있어야 하며, 연결에 실패해도 서버는 실행됩니다.
이 경우 로그인, 관리자 API, 식별 결과 DB 조회는 DB가 준비될 때까지 실패할 수 있습니다.
DB 없이 화면을 먼저 확인하려면 `python testrun.py`를 사용하세요.

## Frontend Merge Notes

이번 병합은 `cattle_system` 전체 앱을 합치지 않고 화면 자산만 백엔드 프로젝트에 통합했습니다.

병합한 자산:

- `templates/login.html`
- `templates/index.html`
- `templates/admin.html`
- `templates/block.html`
- `static/css/index.css`
- `static/css/admin.css`
- `static/js/login.js`
- `static/js/index.js`
- `static/js/admin.js`

병합하지 않은 기존 프론트 독립 앱 자산:

- `cattle_system/cattle_system.py`
- `cattle_system/module`
- `cattle_system/data`
- `cattle_system/log`
- `cattle_system/templates/register.html`
- `__pycache__`
- `*.pyc`
- `dummy.data`

## Routing

- `/login`: 로그인 화면
- `/`: 일반 사용자 식별 화면
- `/admin`: 관리자 화면
- `/block`: 권한 없음 표시 화면
- `/register`: 제거

일반 사용자 메인은 전체 소 목록이 아니라 이미지 업로드, 식별 결과, 최근 조회 이력 영역 중심으로 변경했습니다.
전체 소 목록과 계정/소 관리는 관리자 화면으로 이동했습니다.

## API Contract Used By Frontend

인증:

- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/logout`

식별:

- `POST /api/identify`
- multipart form field: `file`

관리자 계정:

- `GET /admin/accounts`
- `POST /admin/accounts`
- `DELETE /admin/accounts/<id>`

관리자 소 데이터:

- `GET /admin/cows`
- `POST /admin/cows`
- `PUT /admin/cows/<id>`
- `DELETE /admin/cows/<id>`

## Temporary Backend Implementation

백엔드 개발 영역은 크게 변경하지 않는 것을 원칙으로 했습니다.
다만 프론트 화면 테스트가 가능하도록 `app/api/admin.py`에 관리자 API의 최소 SQL 기반 구현을 추가했습니다.

백엔드 담당자가 향후 교체 또는 보강해야 할 항목:

- CSRF 보호
- 관리자 API의 최종 권한 정책
- `super` 권한 사용 여부
- 계정 생성 시 비밀번호 정책과 초기 비밀번호 변경 흐름
- 소 이미지 업로드와 FAISS 인덱스 갱신 연결
- 조회 이력 API
- 로그/백업/인덱스 상태 API
- 감사 로그 상세 정책

`super` 권한은 테스트와 향후 확장을 위해 프론트 옵션에 남겼습니다.
현재 프론트는 `admin` 또는 `super`를 관리자 화면 접근 가능 권한으로 취급합니다.
백엔드 권한 정책 확정 시 제거하거나 정식 권한으로 승격할 수 있습니다.

`block.html`은 권한 판단을 직접 하지 않는 표시 전용 화면입니다.
프론트는 백엔드 API가 `401`을 반환하면 `/login`, `403`을 반환하면 `/block`으로 이동합니다.

## Development Notes

`.env`는 Git에 올리지 않습니다.
필요한 환경 변수는 `.env.example`을 참고해 구성합니다.

정리 대상:

- `__pycache__/`
- `*.pyc`
- `data/`
- `uploads/`
- `logs/`
- `backup/`
- `backups/`
- `dummy.data`
