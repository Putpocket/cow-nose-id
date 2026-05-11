# Frontend Merge Plan

## Goal

`cattle_system`에서 작업한 프론트엔드 화면을 백엔드 프로젝트에 병합하되, 백엔드 기능과 구조는 최대한 유지한다.
프론트는 최종 백엔드 API 계약에 맞추고, 백엔드에 아직 없는 기능은 테스트가 가능한 최소 범위로만 임시 구현한다.
임시 구현은 백엔드 담당자가 언제든 교체할 수 있도록 이 문서와 README에 명확히 남긴다.

## Merge Scope

병합 대상은 화면 파일로 제한한다.

- `cattle_system/templates`
- `cattle_system/static/css`
- `cattle_system/static/js`

병합 제외 대상은 다음과 같다.

- `cattle_system/cattle_system.py`
- `cattle_system/module`
- `cattle_system/data`
- `cattle_system/log`
- `__pycache__`
- `*.pyc`
- `dummy.data`

## Routing/API Contract (Frontend 기준)

### Auth
- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/logout`

### Identify
- `POST /api/identify`
- form field: `file`

### Admin Accounts
- `GET /admin/accounts`
- `POST /admin/accounts`
- `DELETE /admin/accounts/<id>`

### Admin Cows
- `GET /admin/cows`
- `POST /admin/cows`
- `GET /admin/cows/<id>`
- `PUT /admin/cows/<id>`
- `DELETE /admin/cows/<id>`

## AuthN/AuthZ Rules

- 프론트 자체 인증 구현은 제거한다.
- API `401` 응답 시 로그인 화면 이동.
- API `403` 응답 시 `/block` 표시 화면 이동.
- 관리자 화면 접근 표시는 `admin` 또는 `super` 권한일 때 허용한다. (`super`는 테스트/확장용)

## Backend Feedback Alignment

- 사용자/소 데이터는 PostgreSQL 기준으로 처리.
- 인증은 Flask session 기반.
- 비밀번호는 안전한 hash 저장.
- 공개 회원가입 제거, 관리자만 계정 생성.
- 관리자 API는 로그인 + 관리자 권한 필수.
- 상태 변경 API는 CSRF 토큰 필요.
- 업로드 보안/감사 로그는 백엔드 책임.

## Temporary Backend Implementation Rule

- 테스트 가능한 최소 기능만 구현.
- 기존 구조를 크게 바꾸지 않음.
- 임시 구현 항목은 README에 명시.
