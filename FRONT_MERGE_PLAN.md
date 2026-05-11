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
