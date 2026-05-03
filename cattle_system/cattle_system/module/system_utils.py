from datetime import datetime
import os
import time
import json
from flask import request
from hashlib import sha256

USER_PATH = os.popen('pwd').read().strip()

class share_memory:
    hash_mem = {}

def logging_system(log_type=None, flag=None, msg=None, packet=None):
    if not log_type:
        return
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    date = datetime.now().strftime('%Y-%m-%d')
    log_msg = ""
    log_path = ""

    try:
        ip = request.remote_addr
    except RuntimeError:
        ip = "unknown"

    if "access" in log_type:
        log_msg = f"{now} : Access attempt from IP: {ip}\n"
        log_path = f'{USER_PATH}/log/Access_log/{date}_Access.log'
    elif "auth" in log_type:
        log_msg = f"{now} - {msg} {ip}\n"
        log_path = f'{USER_PATH}/log/Auth_log/{date}_Auth.log'
    else:
        log_msg = f"{now} - {msg}\n"
        log_path = f'{USER_PATH}/log/System_log/{date}_System.log'

    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(log_msg)

def wirte_packet(packet):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    date = datetime.now().strftime('%Y-%m-%d')
    packet = json.dumps(packet, indent=4)
    with open(f'{USER_PATH}/log/Packet_log/{date}_Packet_list.log', 'a', encoding='utf-8') as f:
        f.write(f"{now} :\n{packet}\n")

def system_event(log_type=None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

key = ""
iv = ""
def AES_Encrypt(plain_text: str) -> str:
    return plain_text

def AES_Decrypt(chiper_text: str) -> str:
    return chiper_text

def SHA_Encrypt(plain_text: str) -> str:
    if plain_text is None:
        return ""
    plain_text = plain_text.encode('utf-8')
    pepper = "IPS_SYSTEM".encode('utf-8')
    return sha256(plain_text + pepper).hexdigest()

def verify_password(raw_password: str, hashed_password: str) -> bool:
    return SHA_Encrypt(raw_password) == hashed_password