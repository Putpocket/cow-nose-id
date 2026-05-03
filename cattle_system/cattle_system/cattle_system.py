from flask import Flask, render_template, request, url_for, redirect, make_response, jsonify
from module import system_utils
from datetime import datetime
import os
import json
import threading

app = Flask(__name__)
app.secret_key = "IPS_SYSTEM"

PERMIT = ["User", "Admin", "Super"]
USER_PATH = os.getcwd()

def load_user_db_from_file():
    """UserTable 파일에서 사용자 정보 로드"""
    USER_DB = {}
    user_table_path = f'{USER_PATH}/data/UserData/UserTable'
    
    try:
        with open(user_table_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 주석 라인 무시
                if line.startswith('#') or not line:
                    continue
                
                parts = line.split(':')
                if len(parts) >= 4:
                    name = parts[0]
                    userid = parts[1]
                    password_hash = parts[2]
                    permit = parts[3]
                    
                    USER_DB[userid] = {
                        "name": name,
                        "password": password_hash,
                        "permit": permit
                    }
    except FileNotFoundError:
        print(f"경고: UserTable 파일을 찾을 수 없습니다. ({user_table_path})")
    except Exception as e:
        print(f"UserTable 로드 중 오류: {e}")
    
    return USER_DB

def save_user_to_file(userid, name, password_hash, permit):
    """새 사용자를 UserTable 파일에 저장"""
    user_table_path = f'{USER_PATH}/data/UserData/UserTable'
    
    try:
        os.makedirs(f'{USER_PATH}/data/UserData', exist_ok=True)
        
        # 파일에 추가
        with open(user_table_path, 'a', encoding='utf-8') as f:
            f.write(f"\n{name}:{userid}:{password_hash}:{permit}")
        return True
    except Exception as e:
        print(f"사용자 저장 중 오류: {e}")
        return False

def delete_user_from_file(userid):
    """UserTable 파일에서 사용자 삭제"""
    user_table_path = f'{USER_PATH}/data/UserData/UserTable'
    
    try:
        lines = []
        with open(user_table_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) >= 2 and parts[1] != userid:
                    lines.append(line.rstrip())
        
        with open(user_table_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        return True
    except Exception as e:
        print(f"사용자 삭제 중 오류: {e}")
        return False

def load_cattle_db_from_file():
    """CattleTable 파일에서 소 정보 로드"""
    CATTLE_DB = []
    cattle_table_path = f'{USER_PATH}/data/CattleData/CattleTable'
    
    try:
        with open(cattle_table_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 주석 라인 무시
                if line.startswith('#') or not line:
                    continue
                
                parts = line.split(':')
                if len(parts) >= 7:
                    cattle_id = parts[0]
                    name = parts[1]
                    status = parts[2]
                    confidence = parts[3]
                    timestamp = parts[4]
                    owner = parts[5]
                    note = parts[6]
                    
                    CATTLE_DB.append({
                        "id": cattle_id,
                        "name": name,
                        "status": status,
                        "confidence": confidence,
                        "timestamp": timestamp,
                        "owner": owner,
                        "note": note
                    })
    except FileNotFoundError:
        print(f"경고: CattleTable 파일을 찾을 수 없습니다. ({cattle_table_path})")
    except Exception as e:
        print(f"CattleTable 로드 중 오류: {e}")
    
    return CATTLE_DB

def save_cattle_to_file(cattle_id, name, status, confidence, timestamp, owner, note):
    """새 소 데이터를 CattleTable 파일에 저장"""
    cattle_table_path = f'{USER_PATH}/data/CattleData/CattleTable'
    
    try:
        os.makedirs(f'{USER_PATH}/data/CattleData', exist_ok=True)
        
        # 파일에 추가
        with open(cattle_table_path, 'a', encoding='utf-8') as f:
            f.write(f"\n{cattle_id}:{name}:{status}:{confidence}:{timestamp}:{owner}:{note}")
        return True
    except Exception as e:
        print(f"소 데이터 저장 중 오류: {e}")
        return False

def delete_cattle_from_file(cattle_id):
    """CattleTable 파일에서 소 데이터 삭제"""
    cattle_table_path = f'{USER_PATH}/data/CattleData/CattleTable'
    
    try:
        lines = ["#id:name:status:confidence:timestamp:owner:note"]
        with open(cattle_table_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                parts = line.split(':')
                if len(parts) >= 1 and parts[0] != cattle_id:
                    lines.append(line)
        
        with open(cattle_table_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        return True
    except Exception as e:
        print(f"소 데이터 삭제 중 오류: {e}")
        return False

# 앱 시작 시 파일에서 로드
USER_DB = load_user_db_from_file()
CATTLE_DB = load_cattle_db_from_file()
RECENT_DB = list(CATTLE_DB)

def get_user_from_cookie():
    cookie = request.cookies.get('session_id')
    if not cookie:
        return None
    return USER_DB.get(cookie)

@app.route('/', methods=['GET'])
def index():
    userinfo = get_user_from_cookie()
    if not userinfo:
        return redirect(url_for('login'))

    return render_template(
        'index.html',
        username=userinfo["name"],
        userpermit=userinfo["permit"],
        cip=request.remote_addr,
        Admin=userinfo["permit"] in PERMIT[1:],
        cattle_data=CATTLE_DB,
        recent_data=RECENT_DB
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            error = "아이디와 비밀번호를 모두 입력하세요."
        elif username not in USER_DB:
            error = "등록되지 않은 계정입니다."
        else:
            user = USER_DB[username]
            # 파일에서 로드한 비밀번호는 이미 해시되어 있음
            if user["password"] != system_utils.SHA_Encrypt(password):
                error = "비밀번호가 일치하지 않습니다."
            else:
                resp = make_response(redirect(url_for('index')))
                resp.set_cookie('session_id', username)
                return resp

    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    msg = None
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        permit = request.form.get('permit') or "User"

        if not all([name, username, password, confirm_password]):
            error = "모든 항목을 입력하세요."
        elif password != confirm_password:
            error = "비밀번호가 일치하지 않습니다."
        elif username in USER_DB:
            error = "이미 사용 중인 아이디입니다."
        else:
            password_hash = system_utils.SHA_Encrypt(password)
            if save_user_to_file(username, name, password_hash, permit):
                # 메모리의 USER_DB에도 추가
                USER_DB[username] = {
                    "name": name,
                    "password": password_hash,
                    "permit": permit
                }
                msg = "회원가입이 완료되었습니다. 로그인해주세요."
                return render_template('register.html', msg=msg)
            else:
                error = "회원가입 중 오류가 발생했습니다."

    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    resp = make_response(redirect(url_for('login')))
    resp.delete_cookie('session_id')
    return resp

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    userinfo = get_user_from_cookie()
    if not userinfo:
        return redirect(url_for('login'))

    error = None
    result = None
    if request.method == 'POST':
        image = request.files.get('image')
        if not image or image.filename == "":
            error = "이미지를 선택해 주세요."
        else:
            new_id = f"C{len(CATTLE_DB) + 1:03}"
            result = {
                "cattle_id": new_id,
                "name": f"새 소 {new_id}",
                "status": "등록 대기",
                "confidence": "N/A",
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "owner": "미정",
                "note": "AI 결과 대기"
            }
            CATTLE_DB.insert(0, result)
            RECENT_DB.insert(0, result)

    return render_template(
        'cattle_upload.html',
        username=userinfo["name"],
        userpermit=userinfo["permit"],
        cip=request.remote_addr,
        Admin=userinfo["permit"] in PERMIT[1:],
        error=error,
        result=result
    )

@app.route('/admin_pages', methods=['GET'])
def admin_pages():
    userinfo = get_user_from_cookie()
    if not userinfo or userinfo["permit"] not in PERMIT[1:]:
        return redirect(url_for('login'))

    return render_template(
        'admin.html',
        username=userinfo["name"],
        userpermit=userinfo["permit"],
        cip=request.remote_addr,
        Admin=True
    )

@app.route('/block', methods=['GET'])
def block():
    userinfo = get_user_from_cookie()
    return render_template(
        'block.html',
        username=userinfo["name"] if userinfo else "Unknown",
        userpermit=userinfo["permit"] if userinfo else "None",
        requested_page=request.args.get('page', 'Unknown'),
        cip=request.remote_addr
    )

@app.route('/api/cattle', methods=['GET'])
def api_get_cattle():
    return jsonify({"data": CATTLE_DB})

@app.route('/api/admin/cattle', methods=['GET', 'POST', 'DELETE'])
def api_admin_cattle():
    if request.method == 'GET':
        return jsonify({"data": CATTLE_DB})

    if request.method == 'POST':
        payload = request.get_json() or {}
        cattle_id = payload.get("cattleId")
        name = payload.get("name")
        owner = payload.get("owner")
        note = payload.get("note", "")

        if not all([cattle_id, name, owner]):
            return jsonify({"success": False, "message": "필수 항목이 누락되었습니다."}), 400

        new_cattle = {
            "id": cattle_id,
            "name": name,
            "status": "등록",
            "confidence": "-",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "owner": owner,
            "note": note
        }
        
        CATTLE_DB.append(new_cattle)
        
        # 파일에 저장
        if save_cattle_to_file(
            cattle_id, name, "등록", "-",
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            owner, note
        ):
            return jsonify({"success": True})
        else:
            # 저장 실패 시 메모리에서도 제거
            CATTLE_DB.pop()
            return jsonify({"success": False, "message": "파일 저장 중 오류"}), 400

    if request.method == 'DELETE':
        payload = request.get_json() or {}
        cattle_id = payload.get("cattleId")
        if not cattle_id:
            return jsonify({"success": False, "message": "삭제할 소 ID가 필요합니다."}), 400
        
        index = next((i for i, item in enumerate(CATTLE_DB) if item["id"] == cattle_id), None)
        if index is not None:
            CATTLE_DB.pop(index)
            # 파일에서 삭제
            if delete_cattle_from_file(cattle_id):
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "message": "파일 삭제 중 오류"}), 400
        return jsonify({"success": False, "message": "소 데이터를 찾을 수 없습니다."}), 404

@app.route('/api/admin/accounts', methods=['GET', 'POST'])
def api_admin_accounts():
    if request.method == 'GET':
        accounts = [
            {"userid": userid, "name": profile["name"], "permit": profile["permit"]}
            for userid, profile in USER_DB.items()
        ]
        return jsonify({"accounts": accounts})
    
    if request.method == 'POST':
        payload = request.get_json() or {}
        userid = payload.get("userid", "").strip()
        name = payload.get("name", "").strip()
        password = payload.get("password", "").strip()
        permit = payload.get("permit", "User").strip()
        
        if not all([userid, name, password]):
            return jsonify({"success": False, "message": "필수 항목이 누락되었습니다."}), 400
        
        if userid in USER_DB:
            return jsonify({"success": False, "message": "이미 존재하는 아이디입니다."}), 400
        
        if permit not in PERMIT:
            return jsonify({"success": False, "message": "유효하지 않은 권한입니다."}), 400
        
        password_hash = system_utils.SHA_Encrypt(password)
        if save_user_to_file(userid, name, password_hash, permit):
            USER_DB[userid] = {
                "name": name,
                "password": password_hash,
                "permit": permit
            }
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "파일 저장 중 오류"}), 400

@app.route('/api/admin/accounts/<userid>', methods=['DELETE'])
def api_delete_account(userid):
    if userid in USER_DB and userid != "kimyunjung":  # 기본 관리자 계정 보호
        USER_DB.pop(userid)
        if delete_user_from_file(userid):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "파일 삭제 중 오류 발생"}), 400
    return jsonify({"success": False, "message": "삭제할 수 없는 계정이거나 존재하지 않습니다."}), 400

def event_io(time, Type, msg, user, value):
    date = datetime.now().strftime('%Y-%m-%d')
    hour = datetime.now().strftime('%H')
    data = {
        "time": time,
        "Type": Type,
        "msg": msg,
        "user": user,
        "value": value
    }
    
    # 폴더 존재 확인 및 생성
    log_dir = f'{USER_PATH}/log/Event_log'
    os.makedirs(log_dir, exist_ok=True)
    
    with open(f'{log_dir}/{date}-{hour}_Event.log', "a", encoding='utf-8') as f:
        f.write(f"\n{json.dumps(data, ensure_ascii=False)}")

def app_thread():
    app.run(host='0.0.0.0', threaded=True, port=8000)

def main():
    try:
        # 로그 폴더 생성
        os.makedirs(f'{USER_PATH}/log/Access_log', exist_ok=True)
        os.makedirs(f'{USER_PATH}/log/Auth_log', exist_ok=True)
        os.makedirs(f'{USER_PATH}/log/Event_log', exist_ok=True)
        os.makedirs(f'{USER_PATH}/log/System_log', exist_ok=True)
        
        # 데이터 폴더 생성
        os.makedirs(f'{USER_PATH}/data/UserData', exist_ok=True)
        os.makedirs(f'{USER_PATH}/data/CattleData', exist_ok=True)
        
        print(f"[INFO] 애플리케이션 시작")
        print(f"[INFO] 로드된 사용자 수: {len(USER_DB)}")
        print(f"[INFO] 로드된 소 데이터 수: {len(CATTLE_DB)}")
        print(f"[INFO] UserTable 경로: {USER_PATH}/data/UserData/UserTable")
        print(f"[INFO] CattleTable 경로: {USER_PATH}/data/CattleData/CattleTable")
        
        app_process = threading.Thread(target=app_thread)
        app_process.start()
    except KeyboardInterrupt:
        return f"Application stopped due to (Ctrl + C)"

if __name__ == '__main__':
    main()