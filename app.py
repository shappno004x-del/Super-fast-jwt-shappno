from flask import Flask, request, jsonify
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import requests
import my_pb2
import output_pb2
import jwt
import time
import hashlib

app = Flask(__name__)

AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV = b'6oyZDr22E3ychjM%'

# ========== FAST CACHE ==========
cache = {}
session = requests.Session()
session.headers.update({
    'Connection': 'keep-alive',
    'Accept-Encoding': 'gzip'
})

def encrypt_message(plaintext):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    padded_message = pad(plaintext, AES.block_size)
    return cipher.encrypt(padded_message)

def fetch_open_id(access_token):
    # Check cache first
    cache_key = hashlib.md5(access_token.encode()).hexdigest()
    if cache_key in cache:
        cached_data = cache[cache_key]
        if time.time() - cached_data['time'] < 600:  # 10 minutes
            return cached_data['open_id'], None
    
    try:
        # Fast API call
        uid_url = "https://prod-api.reward.ff.garena.com/redemption/api/auth/inspect_token/"
        uid_headers = {
            "accept": "application/json, text/plain, */*",
            "access-token": access_token,
            "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        }
        
        uid_res = session.get(uid_url, headers=uid_headers, timeout=3)
        uid_data = uid_res.json()
        uid = uid_data.get("uid")
        
        if not uid:
            return None, "Failed to extract UID"
            
        openid_url = "https://shop2game.com/api/auth/player_id_login"
        openid_headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
        }
        payload = {"app_id": 100067, "login_id": str(uid)}
        
        openid_res = session.post(openid_url, headers=openid_headers, json=payload, timeout=3)
        openid_data = openid_res.json()
        open_id = openid_data.get("open_id")
        
        if not open_id:
            return None, "Failed to extract open_id"
        
        # Cache it
        cache[cache_key] = {
            'open_id': open_id,
            'time': time.time()
        }
        
        return open_id, None
    except Exception as e:
        return None, f"Error: {str(e)}"

def generate_jwt(access_token, open_id):
    platforms = [8, 3, 4, 6]
    
    for platform_type in platforms:
        try:
            game_data = my_pb2.GameData()
            game_data.timestamp = "2024-12-05 18:15:32"
            game_data.game_name = "free fire"
            game_data.game_version = 1
            game_data.version_code = "1.108.3"
            game_data.os_info = "Android OS 9 / API-28"
            game_data.device_type = "Handheld"
            game_data.network_provider = "Verizon Wireless"
            game_data.connection_type = "WIFI"
            game_data.screen_width = 1280
            game_data.screen_height = 960
            game_data.dpi = "240"
            game_data.cpu_info = "ARMv7 VFPv3 NEON VMH | 2400 | 4"
            game_data.total_ram = 5951
            game_data.gpu_name = "Adreno (TM) 640"
            game_data.gpu_version = "OpenGL ES 3.0"
            game_data.user_id = "Google|74b585a9-0268-4ad3-8f36-ef41d2e53610"
            game_data.ip_address = "172.190.111.97"
            game_data.language = "en"
            game_data.open_id = open_id
            game_data.access_token = access_token
            game_data.platform_type = platform_type
            game_data.field_99 = str(platform_type)
            game_data.field_100 = str(platform_type)

            serialized_data = game_data.SerializeToString()
            encrypted_data = encrypt_message(serialized_data)
            hex_encrypted_data = binascii.hexlify(encrypted_data).decode('utf-8')

            url = "https://loginbp.ggblueshark.com/MajorLogin"
            headers = {
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip",
                "Content-Type": "application/octet-stream",
                "X-Unity-Version": "2018.4.11f1",
                "X-GA": "v1 1",
                "ReleaseVersion": "OB54"
            }
            edata = bytes.fromhex(hex_encrypted_data)
            
            response = session.post(url, data=edata, headers=headers, verify=False, timeout=5)

            if response.status_code == 200:
                try:
                    example_msg = output_pb2.Garena_420()
                    example_msg.ParseFromString(response.content)
                    data_dict = {field.name: getattr(example_msg, field.name)
                                 for field in example_msg.DESCRIPTOR.fields
                                 if field.name not in ["binary", "binary_data", "Garena420"]}
                    
                    if data_dict and "token" in data_dict:
                        token_value = data_dict["token"]
                        final_uid = "N/A"
                        try:
                            decoded_token = jwt.decode(token_value, options={"verify_signature": False})
                            if decoded_token.get("account_id"):
                                final_uid = str(decoded_token.get("account_id"))
                        except:
                            pass
                        
                        return {
                            "status": "success",
                            "real_uid": final_uid,
                            "access_token": access_token,
                            "open_id": open_id,
                            "token": token_value
                        }
                except:
                    pass
        except:
            continue
    return None

@app.route('/token', methods=['GET'])
def oauth_guest():
    start_time = time.time()
    uid = request.args.get('uid')
    password = request.args.get('password')
    
    if not uid or not password:
        return jsonify({"status": "error", "message": "Missing uid or password"}), 400

    oauth_url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    payload = {
        'uid': uid,
        'password': password,
        'response_type': "token",
        'client_type': "2",
        'client_secret': "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        'client_id': "100067"
    }
    headers = {
        'User-Agent': "GarenaMSDK/4.0.19P9(SM-M526B ;Android 13;pt;BR;)",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip"
    }

    try:
        oauth_response = session.post(oauth_url, data=payload, headers=headers, timeout=5)
    except:
        return jsonify({"status": "error", "message": "Request failed"}), 500

    if oauth_response.status_code != 200:
        return jsonify({"status": "error", "message": "OAuth failed"}), oauth_response.status_code

    try:
        oauth_data = oauth_response.json()
    except:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 500

    access_token = oauth_data.get('access_token')
    open_id = oauth_data.get('open_id')
    
    if not access_token or not open_id:
        return jsonify({"status": "error", "message": "Missing access_token or open_id"}), 500

    result = generate_jwt(access_token, open_id)
    elapsed_time = time.time() - start_time
    
    if result:
        result["time"] = f"{elapsed_time:.2f}s"
        return jsonify(result), 200
    else:
        return jsonify({"status": "error", "message": "JWT generation failed"}), 400

@app.route('/access-jwt', methods=['GET'])
def majorlogin_jwt():
    start_time = time.time()
    access_token = request.args.get('access_token')
    
    if not access_token:
        return jsonify({"status": "error", "message": "missing access_token"}), 400

    open_id, error = fetch_open_id(access_token)
    if error:
        return jsonify({"status": "error", "message": error}), 400

    result = generate_jwt(access_token, open_id)
    elapsed_time = time.time() - start_time
    
    if result:
        result["time"] = f"{elapsed_time:.2f}s"
        return jsonify(result), 200
    else:
        return jsonify({"status": "error", "message": "JWT generation failed"}), 400

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "service": "Free Fire JWT Generator",
        "version": "OB54",
        "credit": "@SHAPPNO_004X",
        "speed": "⚡ ULTRA FAST",
        "endpoints": {
            "/token": "GET with uid & password",
            "/access-jwt": "GET with access_token"
        },
        "returns": ["real_uid", "access_token", "open_id", "token", "time"]
    })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 1089))
    try:
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except OSError:
        app.run(host='0.0.0.0', port=port + 1, debug=False, threaded=True)