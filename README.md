# Cow Nose ID Backend

## Run
```bash
pip install -r requirements.txt
flask --app app.web:create_app run
```

## Frontend 연동 기준 API

### Auth
- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/logout`
- `POST /auth/change-password`
- `GET /me` (호환 alias)

### CSRF
- `GET /api/csrf-token`
- `POST/PUT/PATCH/DELETE` 요청은 `X-CSRF-Token` 헤더 필요

### Identify
- `POST /api/identify`
- multipart form field 이름: `file`
- 응답 예시:
```json
{
  "matched": true,
  "cow_id": 1,
  "bbox": [100,100,200,200],
  "cow": {"cow_id": 1, "name": "..."}
}
```

### Admin Accounts
- `GET /admin/accounts`
- `POST /admin/accounts`
- `DELETE /admin/accounts/{id}`

### Admin Cows
- `GET /admin/cows`
- `POST /admin/cows`
- `GET /admin/cows/{id}`
- `PUT /admin/cows/{id}`
- `DELETE /admin/cows/{id}`

## 현재 상태/제한
- 파이프라인은 detect->crop->embed->search->DB lookup 흐름으로 연결됨.
- 다만 YOLO/DINO/FAISS 서비스 모듈은 현재 스텁 구현이므로 실제 모델/인덱스 연결은 추가 구현 필요.
- Bootstrap admin(`admin/admin`) 자동 생성 로직 포함.
