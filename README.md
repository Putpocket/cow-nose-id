# Cow Nose ID

소의 코 사진을 업로드하면 학습 완료된 YOLO `.pt` 모델로 코 영역을 crop하고, DINO embedding을 추출한 뒤 FAISS cosine similarity로 가장 유사한 개체를 찾습니다. 최상위 개체의 소유주와 개체 정보는 PostgreSQL에서 조회합니다. 기본 embedding 모델은 공개 접근 가능한 DINOv2입니다.

프론트와 백엔드는 모두 Python입니다. 웹 화면은 Flask/Jinja로 렌더링하고, 같은 Flask 앱에서 JSON API도 제공합니다.

## 대상 환경

- Ubuntu 24.04
- NVIDIA RTX 4060
- CUDA 사용 가능한 PyTorch 설치 완료
- Python 3.11 또는 3.12 권장
- PostgreSQL
- 학습 완료된 YOLO `.pt` 파일 보유

## 설치

이미 PyTorch가 설치되어 있다는 전제라 `requirements.txt`에는 `torch`를 넣지 않았습니다.
CUDA를 써야 하면 새 venv를 만들기보다 학습에 사용했던 PyTorch 환경에서 실행하는 것을
권장합니다.

```bash
cd /path/to/cow-nose-id
# 예: conda activate 학습에쓴환경
pip install -U pip
pip install -r requirements.txt
cp .env.example .env
```

`.env`를 실제 환경에 맞게 수정합니다.

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cow_nose_id
FAISS_INDEX_PATH=./data/cow_nose.faiss
FAISS_IDS_PATH=./data/cow_ids.json
YOLO_WEIGHTS_PATH=/absolute/path/to/your/best.pt
YOLO_CONF_THRESHOLD=0.25
DINO_MODEL_NAME=facebook/dinov2-base
# DINOv3는 Hugging Face 인증과 접근 승인이 필요합니다.
# DINO_MODEL_NAME=facebook/dinov3-vitb16-pretrain-lvd1689m
DEVICE=cuda:0
SIMILARITY_THRESHOLD=0.72
SECRET_KEY=change-this-to-a-random-secret
UPLOAD_DIR=./data/uploads
MAX_REQUEST_MB=50
MAX_UPLOAD_MB=8
MAX_IMAGE_PIXELS=20000000
PROXY_FIX_ENABLED=false
PROXY_FIX_X_FOR=1
PROXY_FIX_X_PROTO=1
PROXY_FIX_X_HOST=1
PROXY_FIX_X_PORT=1
PROXY_FIX_X_PREFIX=0
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STORAGE_URI=memory://
LOGIN_RATE_LIMIT=5 per minute
UPLOAD_RATE_LIMIT=20 per hour
ADMIN_ACTION_RATE_LIMIT=30 per hour
REGISTRATION_MIN_IMAGES=3
REGISTRATION_MAX_IMAGES=10
ALLOWED_IMAGE_EXTENSIONS=jpg,jpeg,png,webp
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=admin
BACKUP_ENABLED=true
BACKUP_DIR=./data/backups
BACKUP_INTERVAL_SECONDS=86400
LOG_FILE=./data/logs/app.log
ERROR_LOG_FILE=./data/logs/error.log
LOG_LEVEL=INFO
AUTO_REBUILD_INDEX=true
PASSWORD_MIN_LENGTH=8
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCKOUT_SECONDS=900
SESSION_LIFETIME_MINUTES=60
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
CONTENT_SECURITY_POLICY=default-src 'self'; img-src 'self' blob: data:; script-src 'self'; style-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'
REFERRER_POLICY=same-origin
UPLOAD_FILE_MODE=0o640
```

## DB 생성

```bash
createdb cow_nose_id
psql "$DATABASE_URL" -f sql/schema.sql
```

앱 시작 시에도 `sql/schema.sql`을 기준으로 필요한 테이블을 한 번 더 확인합니다.
그래도 운영 배포에서는 위 명령으로 DB 스키마를 먼저 적용한 뒤 실행하는 방식을
권장합니다.

앱 최초 실행 시 `users` 테이블이 비어 있으면 관리자 계정이 한 번 생성됩니다.
기본값은 `admin` / `admin`입니다. 최초 로그인 직후 비밀번호 변경 화면으로
강제 이동합니다. 이후 관리자 화면에서 일반 계정 또는 추가 관리자 계정을 만들 수
있습니다. 회원가입 화면은 없습니다.

새 계정과 변경 비밀번호는 `PASSWORD_MIN_LENGTH` 이상이어야 하고 영문자와 숫자를
포함해야 합니다. 로그인 실패가 `LOGIN_MAX_ATTEMPTS`회 누적되면
`LOGIN_LOCKOUT_SECONDS` 동안 해당 아이디 로그인을 잠급니다. 로그인 실패 횟수와
잠금 시각은 DB에 저장됩니다.

초기 관리자와 관리자가 새로 만든 계정은 첫 로그인 후 비밀번호 변경이 강제됩니다.
계정 삭제는 감사 추적을 위해 실제 삭제 대신 비활성화로 처리됩니다. 계정 생성,
비밀번호 초기화, 활성화/비활성화, 로그인 성공/실패, 소 등록/수정/삭제 등 주요
관리자 행위는 `audit_logs` 테이블에 저장되고 `/admin/system`에서 확인할 수 있습니다.

관리자만 `/admin/cows/new`에서 소유주, 개체 정보, 소 코 사진을 등록할 수 있습니다.
등록 시 소 코 사진은 기본값 기준 3~10장을 업로드합니다. 업로드된 이미지는
`UPLOAD_DIR`에 저장되고 `cow_images.image_path`에 여러 행으로 기록됩니다.
관리자는 `/admin/cows`에서 소 정보를 수정하거나 삭제할 수 있습니다.
소 이미지를 교체하면 기존 이미지 레코드는 새 이미지로 대체되고, 삭제 또는 교체된
업로드 파일은 `UPLOAD_DIR` 아래에 있는 경우 함께 정리됩니다.
`AUTO_REBUILD_INDEX=true`이면 소 등록, 이미지 변경, 삭제 후 FAISS 인덱스를
백그라운드에서 자동 갱신합니다. `/admin/system`에서 갱신 상태를 확인하고
수동 갱신도 실행할 수 있습니다.

모든 POST 폼은 CSRF 토큰을 검사합니다. 업로드 요청 전체는 `MAX_REQUEST_MB`,
개별 파일은 `MAX_UPLOAD_MB`로 제한합니다. 업로드 파일은 `MAX_IMAGE_PIXELS`,
`ALLOWED_IMAGE_EXTENSIONS`, MIME 타입, 파일 시그니처,
Pillow 이미지 검증, 확장자와 실제 이미지 형식 일치 검사를 통과해야 합니다.
저장 파일명은 원본 파일명을 쓰지 않고 서버가 생성한 `cow-upload-...` 형식을
사용하며, 저장 전 이미지를 재인코딩합니다.
HTTPS로 운영할 때는 `SESSION_COOKIE_SECURE=true`로 바꾸세요. `SESSION_COOKIE_HTTPONLY`,
`SESSION_COOKIE_SAMESITE`는 세션 쿠키 보호에 사용됩니다.
앱은 기본 보안 헤더(`Content-Security-Policy`, `X-Frame-Options`,
`X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`)를 응답에 추가합니다.
업로드 디렉터리는 `0750`, 업로드 파일은 `UPLOAD_FILE_MODE` 권한으로 저장됩니다.
감사 로그에 저장되는 IP, User-Agent, 상세 메시지는 제어문자를 제거하고 길이를 제한합니다.
로그인, 업로드, 관리자 위험 작업에는 `Flask-Limiter` 기반 rate limit이 적용됩니다.
리버스 프록시 뒤에서 운영할 때는 신뢰할 수 있는 프록시만 `X-Forwarded-*` 헤더를
전달하도록 구성하고 `PROXY_FIX_ENABLED=true`를 설정해야 클라이언트 IP 기반
rate limit과 감사 로그가 올바르게 동작합니다.

## 기존 사진 벡터화

`cow_images`에 등록된 사진을 YOLO `.pt`로 crop하고 DINO embedding으로 변환합니다.
기본 embedding 모델은 `facebook/dinov2-base`입니다.
자동 갱신을 끈 환경에서는 관리자 화면에서 새 소를 등록한 뒤 아래 두 명령으로
FAISS index를 다시 만들어야 식별 검색에 반영됩니다.

```bash
python scripts/embed_dataset.py \
  --out-embeddings data/embeddings.npy \
  --out-cow-ids data/cow_ids_source.json
```

FAISS index를 생성합니다.

```bash
python scripts/build_index.py \
  --embeddings data/embeddings.npy \
  --cow-ids data/cow_ids_source.json \
  --out-index data/cow_nose.faiss \
  --out-ids data/cow_ids.json
```

## Flask 실행

서버에 학습된 `.pt` 파일을 옮긴 뒤에는 `.env`의 `YOLO_WEIGHTS_PATH`를 그 파일
경로로 맞춥니다. 예를 들어 프로젝트 안에 둘 경우:

```bash
mkdir -p models
cp /path/to/best.pt models/cow-nose-yolo.pt
```

`.env`:

```bash
YOLO_WEIGHTS_PATH=./models/cow-nose-yolo.pt
```

실행 전에 환경을 점검합니다. 이 단계에서 DB 연결, `.pt` 로드, DINO 모델 로드가 한 번에
확인됩니다.

```bash
python scripts/check_runtime.py
```

통과하면 Flask를 실행합니다.

```bash
flask --app app.web run --host 0.0.0.0 --port 8000
```

브라우저에서 `http://서버IP:8000`으로 접속합니다.

첫 테스트 순서:

1. `admin` / `admin`으로 로그인합니다.
2. 최초 비밀번호 변경을 완료합니다.
3. `/admin/cows/new`에서 소 1마리당 소 코 사진 3~10장을 등록합니다.
4. `/admin/system`에서 FAISS 인덱스 갱신 상태가 완료되는지 확인합니다.
5. `/` 식별 화면에서 새 소 코 사진 1장을 올려 결과를 확인합니다.

## 분리 프론트용 JSON API

프론트가 별도 앱이어도 백엔드는 Flask 세션 쿠키 기반 JSON API로 사용할 수 있습니다.
상태를 변경하는 요청은 CSRF 보호가 적용됩니다.

1. 먼저 `GET /api/csrf`를 호출해 `csrf_token`을 받습니다.
2. `POST`, `PATCH`, `DELETE` 요청에는 `X-CSRF-Token` 헤더로 토큰을 보냅니다.
3. 로그인 후에는 브라우저가 받은 세션 쿠키를 포함해서 API를 호출합니다.

인증:

```text
GET  /api/csrf
POST /api/auth/login
POST /api/auth/logout
GET  /api/me
POST /api/auth/change-password
```

소 식별:

`POST /api/identify`

- multipart form field: `file`
- 반환: 매칭 여부, 최고 유사도, crop box, top-k 후보, PostgreSQL에서 조회한 개체/소유주 정보

관리자 계정 관리:

```text
GET    /api/admin/users
POST   /api/admin/users
PATCH  /api/admin/users/{id}
DELETE /api/admin/users/{id}
```

`PATCH /api/admin/users/{id}`는 `password`, `status` 값을 받을 수 있습니다.
`status`는 `active` 또는 `disabled`입니다. 삭제 API도 감사 추적을 위해 실제 삭제가
아니라 비활성화로 처리합니다.

관리자 소 관리:

```text
GET    /api/admin/cows
GET    /api/admin/cows/{id}
POST   /api/admin/cows
PATCH  /api/admin/cows/{id}
DELETE /api/admin/cows/{id}
```

`POST /api/admin/cows`는 `multipart/form-data`를 사용하고 `files` 필드에 소 코
이미지 3~10장을 넣습니다. 기존 호환을 위해 같은 이름의 `file` 필드 여러 개도
처리합니다. `PATCH /api/admin/cows/{id}`는 JSON 또는 multipart form을
받을 수 있고, 이미지 교체가 필요하면 `files` 필드를 함께 보냅니다. 소 등록,
이미지 변경, 삭제 후에는 `AUTO_REBUILD_INDEX=true` 기준으로 FAISS 인덱스가
백그라운드에서 자동 갱신됩니다.

관리자 시스템:

```text
GET  /api/admin/system
POST /api/admin/backups/run
POST /api/admin/index/rebuild
```

프론트와 백엔드를 완전히 다른 도메인에서 운영하려면 쿠키 전송 정책 때문에
리버스 프록시에서 같은 사이트로 묶는 방식을 권장합니다. 다른 도메인을 써야 하면
`SESSION_COOKIE_SAMESITE=None`, `SESSION_COOKIE_SECURE=true`, CORS 허용 도메인
설정을 별도로 추가해야 합니다.

## 운영 메모

- `YOLO_WEIGHTS_PATH`는 이미 학습된 `.pt` 파일 경로를 지정합니다.
- 등록 사진에서 코 검출이 전부 실패하면 `YOLO_CONF_THRESHOLD=0.05`처럼 낮춰 테스트해볼 수 있습니다.
- 기본 embedding 모델은 `facebook/dinov2-base`입니다.
- DINOv3(`facebook/dinov3-vitb16-pretrain-lvd1689m`)는 Hugging Face gated repo라서 인증과 접근 승인이 필요합니다.
- RTX 4060을 쓰려면 `DEVICE=cuda:0`으로 둡니다.
- FAISS는 현재 `faiss-cpu` 기준입니다. 검색 벡터 수가 매우 많아 CPU 검색이 병목이면 별도 conda 환경에서 GPU FAISS를 검토하세요.
- 임계값 `SIMILARITY_THRESHOLD`는 실제 농장 데이터로 검증하면서 조정해야 합니다.
- `BACKUP_ENABLED=true`이면 앱 실행 중 `BACKUP_INTERVAL_SECONDS`마다 `pg_dump` 백업을 `BACKUP_DIR`에 저장합니다.
- `/admin/system`에서 최근 로그와 백업 파일 목록을 확인하고 수동 백업을 실행할 수 있습니다.
- 앱 로그는 `LOG_FILE`에 저장되며, `WARNING` 이상은 `ERROR_LOG_FILE`에도 함께 저장됩니다. `LOG_LEVEL=INFO`를 기본으로 사용하고, 장애 분석 때만 임시로 `DEBUG`로 올리는 것을 권장합니다.
- 운영에서는 업로드/백업 경로를 앱 루트 밖 절대 경로로 두는 것을 권장합니다. 예: `UPLOAD_DIR=/var/lib/cow-muzzle/uploads`, `BACKUP_DIR=/var/backups/cow-muzzle`.
- `RATE_LIMIT_STORAGE_URI=memory://`는 단일 프로세스 테스트용입니다. 운영에서 여러 프로세스나 서버를 쓰면 Redis 같은 공유 저장소를 지정하세요.
- 소 등록처럼 여러 이미지를 한 번에 올리는 요청은 `MAX_REQUEST_MB`가 적용되고, 각 이미지 1장에는 `MAX_UPLOAD_MB`가 적용됩니다.
- 수동 백업과 FAISS 인덱스 갱신은 백그라운드 작업으로 실행되며, `/admin/system`에서 상태를 확인할 수 있습니다.

## 보안 점검

런타임 설정과 모델/DB 연결을 확인합니다.

```bash
python -m scripts.check_runtime
```

의존성 취약점은 `pip-audit`로 점검할 수 있습니다.

```bash
python -m pip install pip-audit
python scripts/audit_dependencies.py
```
