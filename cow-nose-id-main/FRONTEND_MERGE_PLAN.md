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

## Git Cleanup

다음 파일과 디렉터리는 Git 추적 대상에서 제거하고 `.gitignore`에 추가한다.

- `.env`
- `__pycache__/`
- `*.pyc`
- `data/`
- `uploads/`
- `logs/`
- `backup/`
- `backups/`
- `*.log`
- `dummy.data`

## Routing Plan

프론트 화면 라우트는 다음 기준으로 정리한다.

- `/login`: 로그인 화면
- `/`: 일반 사용자 메인 화면
- `/admin`: 관리자 화면
- `/block`: 권한 없음 표시 화면
- `/register`: 제거
- `/upload`: 별도 화면으로 유지하지 않고 일반 사용자 메인에 업로드 기능 통합

`block.html`은 프론트 화면으로 통합한다. 단, 권한 판단은 직접 하지 않고 백엔드 API 응답 결과를 보여주는 표시 전용 화면으로 사용한다.

## Authentication And Authorization

프론트 자체 인증 구현은 제거한다.

제거 대상:

- 파일 기반 사용자 DB
- `session_id=username` 쿠키 방식
- 프론트 자체 로그인 검증
- 단순 SHA 기반 비밀번호 검증
- 공개 회원가입 화면과 링크

백엔드 기준:

- 로그인은 `POST /auth/login` 호출 결과를 사용한다.
- 현재 사용자 정보와 권한은 `GET /auth/me` 결과를 사용한다.
- API가 `401`을 반환하면 로그인 화면으로 이동한다.
- API가 `403`을 반환하면 `/block` 또는 권한 없음 화면을 표시한다.

## Role Policy

백엔드 기본 권한은 `user`, `admin` 기준으로 맞춘다.

다만 테스트와 향후 확장 가능성을 위해 `super` 권한은 프론트 옵션에 남긴다.

- 일반 사용자: `user`
- 관리자: `admin`
- 테스트/확장용 최고 권한: `super`

프론트 관리자 화면 접근 표시는 `admin` 또는 `super`일 때 허용한다.
`super`는 백엔드 권한 정책 확정 시 제거하거나 백엔드 정책에 맞춰 조정할 수 있도록 README에 남긴다.

## User Main Screen

기존 `index.html`은 전체 소 목록과 최근 등록 데이터 중심이라 관리자 화면과 역할이 겹친다.
일반 사용자 메인 화면은 다음 기능 중심으로 재구성한다.

- 이미지 업로드
- 식별 결과 확인
- 본인 최근 조회 이력 확인

본인 조회 이력 API가 아직 없으면 빈 상태 화면을 제공한다.
테스트에 꼭 필요할 경우 최소 임시 API를 구현하고 README에 백엔드 대체 필요 항목으로 남긴다.

## Admin Screen

관리자 화면은 다음 기능 중심으로 정리한다.

- 계정 목록 조회
- 계정 생성
- 계정 삭제
- 소 목록 조회
- 소 등록
- 소 수정
- 소 삭제
- 이미지 업로드
- 로그/백업/갱신 상태 확인 영역

전체 소 목록과 최근 등록 데이터는 일반 사용자 메인이 아니라 관리자 화면으로 이동한다.

## API Contract

프론트는 다음 백엔드 스타일 API 경로에 맞춘다.

### Auth

- `POST /auth/login`
- `GET /auth/me`

### Identify

- `POST /api/identify`
- form field: `file`

기존 프론트의 `image` 필드명은 사용하지 않는다.

### Admin Accounts

- `GET /admin/accounts`
- `POST /admin/accounts`
- `DELETE /admin/accounts/<id>`

### Admin Cows

- `GET /admin/cows`
- `POST /admin/cows`
- `PUT /admin/cows/<id>`
- `DELETE /admin/cows/<id>`

백엔드에 아직 없는 관리자 API는 테스트를 막는 경우에만 최소 임시 구현한다.
임시 구현은 `app/api/admin.py` 안에서 보강하는 것을 기본으로 한다.
단, 기존 백엔드 구조를 크게 바꾸지 않고 백엔드 담당자가 쉽게 교체할 수 있게 작성한다.

## JavaScript Cleanup

`cattleData` 중복 선언 문제를 정리한다.

- 템플릿에서는 `window.cattleData` 형태로 넘긴다.
- `index.js`에서는 `window.cattleData`를 읽는다.

단, 현재 백엔드 CSP가 `script-src 'self'` 기준이므로 inline script가 차단될 수 있다.
필요하면 nonce 또는 JSON script 태그 방식으로 조정한다.

## UI Text And Buttons

서비스 톤을 맞추기 위해 이모지 버튼은 제거한다.

- `🔍` 대신 `검색`
- `☰` 대신 일반 텍스트 메뉴 버튼 또는 CSS 기반 메뉴 표시

아이콘 라이브러리는 이번 단계에서는 추가하지 않는다.
필요할 경우 이후 lucide를 로컬 번들 방식으로 도입한다.

## Backend Feedback Alignment

백엔드 피드백과 맞추기 위해 프론트 병합에서는 다음을 지킨다.

- 사용자/소 데이터 파일 저장 로직은 병합하지 않는다.
- 인증은 백엔드 세션/API 결과를 기준으로 한다.
- 공개 회원가입은 제거한다.
- 계정 생성은 관리자 화면에서만 제공한다.
- 업로드 form field는 `file`로 통일한다.
- 관리자 기능은 관리자 API를 통해서만 호출한다.
- CSRF 토큰은 백엔드 확정 후 메타 태그 또는 응답 기반 헤더로 붙일 수 있게 구조를 열어둔다.
- 업로드 제한과 감사 로그는 백엔드 책임으로 두되, 프론트는 백엔드 오류 메시지를 화면에 표시한다.

## Temporary Backend Implementation Rule

백엔드 개발 부분은 함부로 크게 변경하지 않는다.

테스트 중 프론트 확인에 꼭 필요한 API가 없으면 다음 기준으로만 보강한다.

- 테스트 가능한 최소 기능만 구현한다.
- 기존 백엔드 파일 중 `app/api/admin.py` 보강을 우선한다.
- PostgreSQL, 세션, 권한 검사 방향을 해치지 않는다.
- 파일 기반 DB나 프론트 독립 서버 로직을 되살리지 않는다.
- 임시 구현임을 README에 남긴다.
- 백엔드 담당자가 대체해야 할 항목을 명확히 기록한다.

## README Notes To Add

README에는 다음 내용을 추가한다.

- 프론트 병합 범위
- 제외된 `cattle_system` 파일 목록
- 사용 API 목록
- 임시 구현한 백엔드 엔드포인트
- 백엔드 담당자가 교체 또는 확장해야 할 항목
- `super` 권한은 테스트/확장용이라는 설명
- `block.html`은 표시 전용 권한 없음 화면이라는 설명
- 실행 및 테스트 방법

