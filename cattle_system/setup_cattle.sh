#!/bin/bash

# Cattle System 초기 설정 스크립트
# 이 스크립트는 cattle_system 웹 애플리케이션을 실행하기 위한 환경을 구성합니다.

echo "================================"
echo "Cattle System 초기 설정 시작"
echo "================================"

# Python3 및 pip 설치
echo "[1/3] Python3 및 필요한 패키지 설치 중..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# Python 가상환경 생성 (선택사항이지만 권장)
echo "[2/3] 가상환경 설정 중..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "가상환경 생성 완료: venv"
fi

# Python 패키지 설치
echo "[3/3] Python 패키지 설치 중..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "가상환경 활성화 완료"
fi

pip3 install --upgrade pip
pip3 install flask

# 디렉토리 구조 확인
echo ""
echo "================================"
echo "디렉토리 구조 확인"
echo "================================"

REQUIRED_DIRS=(
    "data/UserData"
    "data/CattleData"
    "log/Access_log"
    "log/Auth_log"
    "log/Event_log"
    "log/System_log"
    "module"
    "static/css"
    "static/js"
    "templates"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo "✓ 디렉토리 생성: $dir"
    else
        echo "✓ 디렉토리 확인: $dir"
    fi
done

# 기본 사용자 계정 생성 확인
echo ""
echo "================================"
echo "기본 설정 완료!"
echo "================================"
echo ""
echo "다음 단계:"
echo "1. data/UserData/UserTable 파일을 확인하세요"
echo "2. 기본 관리자 계정을 등록하려면 register 페이지를 방문하세요"
echo "3. cattle_system.py를 실행하세요:"
echo "   python3 cattle_system.py"
echo ""
echo "웹 애플리케이션은 http://localhost:5000 에서 접근 가능합니다"
echo ""
