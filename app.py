from flask import Flask, request, jsonify, send_from_directory, render_template, flash, redirect, session, url_for
from flask_jwt_extended import JWTManager, get_jwt_identity, jwt_required
from flask_pymongo import PyMongo
from flask_cors import CORS
from dotenv import load_dotenv
import os
import random
from bson import ObjectId
from bson.errors import InvalidId

# Models dan controller
from Models.detectionhistory import DetectionHistory
from Models.login_log_model import LoginLog
from Models.user_model import User
from Controller.auth_controller import AuthController
from Controller.artikel_controller import ArtikelController
from utils import admin_required, config_oauth, require_api_key, token_required, verify_google_token, create_token

# === Inisialisasi Flask ===
load_dotenv()
app = Flask(__name__, static_url_path='/static', static_folder='static')
CORS(app)

# === Config dasar ===
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/capstone")
jwt_secret = os.getenv("JWT_SECRET", "your-secret-key")

# === Config JWT === ✅
app.config["JWT_SECRET_KEY"] = jwt_secret
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"

# Inisialisasi JWT
jwt = JWTManager(app)

# === Inisialisasi Mongo & Model ===
mongo = PyMongo(app)
user_model = User(mongo.db)
login_log_model = LoginLog(mongo.db)
artikel_controller = ArtikelController(mongo.db)
auth_controller = AuthController(mongo.db, jwt_secret)

# === Google OAuth ===
config_oauth(app)

# === AUTH ROUTES ===

@app.route('/api/auth/register', methods=['POST'])
def register():
    print("DEBUG: Raw request data:", request.data)
    try:
        data = request.get_json()
        print("DEBUG: Parsed JSON data:", data)
        if not data:
            return jsonify({'error': 'Tidak ada data yang diterima'}), 400
        return auth_controller.register(data)
    except Exception as e:
        print(f"DEBUG: Error parsing JSON: {e}")
        return jsonify({'error': 'Gagal parsing JSON', 'details': str(e)}), 400

@app.route('/api/auth/login', methods=['POST'])
def login():
    return auth_controller.login(request.get_json())

@app.route('/api/auth/validate', methods=['GET'])
def validate_token():
    token = request.headers.get('Authorization')
    return auth_controller.validate_token(token)

@app.route('/api/auth/login-history/<user_id>', methods=['GET'])
def login_history(user_id):
    try:
        # Validasi ObjectId jika perlu (opsional karena kita simpan user_id sebagai string)
        try:
            ObjectId(user_id)  # untuk validasi format saja
        except InvalidId:
            return jsonify({'error': 'ID user tidak valid'}), 400

        logs = login_log_model.find_logs_by_user_id(user_id)

        return jsonify(logs), 200

    except Exception as e:
        print(f"Error saat mengambil login history: {e}")
        return jsonify({'error': 'Terjadi kesalahan di server'}), 500

@app.route('/api/auth/verify-email', methods=['GET'])
def verify_email():
    token = request.args.get('token')
    if not token:
        return render_template("verification_failed.html", message="Token tidak ditemukan.")

    user = user_model.find_user_by_token(token)
    if not user:
        return render_template("verification_failed.html", message="Token tidak valid atau sudah digunakan.")

    user_model.update_user_verification(user['_id'])
    return render_template("verification_success.html", message="Email berhasil diverifikasi. Anda bisa login sekarang.")

@app.route('/api/auth/status', methods=['GET'])
def check_verification_status():
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'Email tidak ditemukan'}), 400
    user = user_model.find_user_by_email(email)
    if not user:
        return jsonify({'error': 'User tidak ditemukan'}), 404
    return jsonify({'is_verified': user.get('is_verified', False)})

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'error': 'Email diperlukan'}), 400
    user = user_model.find_user_by_email(email)
    if not user:
        return jsonify({'error': 'Email tidak ditemukan'}), 404
    otp_code = str(random.randint(100000, 999999))
    user_model.save_otp_code(email, otp_code)
    from utils import send_email
    send_email(email, otp_code)
    print(f"DEBUG: OTP dikirim ke {email} => {otp_code}")
    return jsonify({'message': 'Kode verifikasi telah dikirim ke email Anda'}), 200


@app.route('/api/auth/verify-code', methods=['POST'])
def verify_code():
    data = request.get_json()
    email = data.get('email')
    code = data.get('code')
    if not email or not code:
        return jsonify({'error': 'Email dan kode diperlukan'}), 400
    is_valid = user_model.check_otp_code(email, code)
    if not is_valid:
        return jsonify({'error': 'Kode tidak valid atau kedaluwarsa'}), 401
    return jsonify({'message': 'Kode valid'}), 200

@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email')
    code = data.get('code')
    new_password = data.get('new_password')
    if not email or not code or not new_password:
        return jsonify({'error': 'Semua field diperlukan'}), 400
    if not user_model.check_otp_code(email, code):
        return jsonify({'error': 'Kode tidak valid'}), 401
    user_model.update_password(email, new_password)
    user_model.clear_otp_code(email)
    return jsonify({'message': 'Password berhasil diubah'}), 200

@app.route('/api/auth/resend-code', methods=['POST'])
def resend_code():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'error': 'Email diperlukan'}), 400
    user = user_model.find_user_by_email(email)
    if not user:
        return jsonify({'error': 'Email tidak ditemukan'}), 404
    # Buat ulang kode OTP
    otp_code = str(random.randint(100000, 999999))
    # Simpan ke database
    user_model.save_otp_code(email, otp_code)
    # Kirim email via SMTP
    from utils import send_email
    send_email(email, otp_code)
    # Kirim ulang kode ke email (dalam produksi gunakan SMTP)
    print(f"DEBUG: Kode OTP DIKIRIM ULANG ke {email} => {otp_code}")
    return jsonify({'message': 'Kode verifikasi telah dikirim ulang ke email Anda'}), 200

@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_profile():
    return auth_controller.get_profile()

@app.route('/api/user/profile/update', methods=['PUT'])
@token_required
def update_profile():
    return auth_controller.update_profile_from_token()

@app.route('/static/uploads/profile_pictures/<filename>')
def serve_profile_picture(filename):
    return send_from_directory('static/uploads/profile_pictures', filename)

@app.route('/api/user/delete', methods=['DELETE'])
@token_required
def delete_user():
    return auth_controller.delete_user()

# Google OAuth login endpoint
@app.route('/google/login')
def google_login_route():
    return auth_controller.login_with_google()

@app.route('/google/callback')
def google_callback_route():
    return auth_controller.google_callback()

@app.route('/api/auth/google-login', methods=['POST'])
def google_login():
    print("DEBUG: Memulai proses login Google...")

    data = request.get_json()
    print(f"DEBUG: Data yang diterima: {data}")

    id_token = data.get('idToken')
    if not id_token:
        print("DEBUG: Token Google tidak ditemukan.")
        return jsonify({'error': 'Token Google tidak ditemukan'}), 400

    idinfo = verify_google_token(id_token)
    if not idinfo:
        print("DEBUG: Verifikasi token Google gagal.")
        return jsonify({'error': 'Token Google tidak valid'}), 401

    print(f"DEBUG: Token berhasil diverifikasi. Info: {idinfo}")

    email = idinfo.get('email')
    name = idinfo.get('name', '')
    picture = idinfo.get('picture', '')
    uid = idinfo.get('uid') or idinfo.get('sub')

    if not email:
        return jsonify({'error': 'Email tidak ditemukan dalam token'}), 400

    # Cek apakah user sudah ada
    user = user_model.find_user_by_email(email)
    if not user:
        print("DEBUG: User belum ada, membuat akun baru...")
        user_id = user_model.create_user(
            full_name=name,
            phone='',
            email=email,
            password='',
            age='',
            gender='',
            is_verified=True,
            profile_picture=picture
        )
    else:
        print("DEBUG: User sudah ada.")
        user_id = user['_id']

    login_log_model.log_login(
        str(user_id),  # pastikan string
        "success",
        request.headers.get('User-Agent'),
        request.remote_addr
    )

    # Buat JWT token untuk aplikasi
    jwt_token = create_token(user_id)
    print(f"DEBUG: JWT token dibuat: {jwt_token}")

    return jsonify({
        'token': jwt_token,
        'user_id': str(user_id),
        'user_email': email,
        'user_full_name': name,
        'profile_picture': picture,
        'message': 'Login berhasil'
    })

# === ARTIKEL ROUTES API ===

@app.route('/api/artikel', methods=['POST'])
@require_api_key
@token_required
def create_artikel():
    return artikel_controller.create_artikel(request.get_json())

@app.route('/api/artikel', methods=['GET'])
def get_all_artikels():
    return artikel_controller.get_all_artikels()

@app.route('/api/artikel/<artikel_id>', methods=['GET'])
@require_api_key
@token_required
def get_artikel_by_id(artikel_id):
    return artikel_controller.get_artikel_by_id(artikel_id)

@app.route('/api/artikel/<artikel_id>', methods=['PUT'])
@require_api_key
@token_required
def update_artikel(artikel_id):
    return artikel_controller.update_artikel(artikel_id, request.get_json())

@app.route('/api/artikel/<artikel_id>', methods=['DELETE'])
@require_api_key
@token_required
def delete_artikel(artikel_id):
    return artikel_controller.delete_artikel(artikel_id)

@app.route('/api/user/change-password', methods=['PUT'])
@token_required
def change_password():
    return auth_controller.change_password_from_token()

# === ADMIN ROUTES ===
@app.route('/', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = user_model.find_user_by_email(email)

        if user and user_model.verify_password(user, password):
            if user.get('role') != 'admin':
                flash('Akses hanya untuk admin.', 'danger')
                return redirect(url_for('login_admin'))

            # Simpan session
            session['logged_in'] = True
            session['user_role'] = user['role']
            session['user_email'] = user['email']

            flash('Login berhasil sebagai admin!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Email atau password salah.', 'danger')

    return render_template('accounts/login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Berhasil logout.', 'success')
    return redirect(url_for('login_admin'))


@app.route('/dashboard')
@admin_required
def index():
    return render_template('home/index.html')


@app.route('/tables')
@admin_required
def tabel_artikel_view():
    response, status_code = artikel_controller.get_all_artikels(from_view=True)
    artikels = response.get_json() if status_code == 200 else []
    return render_template('home/tables.html', artikels=artikels)


@app.route('/tambah-artikel', methods=['GET', 'POST'])
@admin_required
def tambah_artikel():
    if request.method == 'POST':
        response, status = artikel_controller.create_artikel_from_view()
        
        if status == 201:
            flash("Artikel berhasil ditambahkan.", "success")
            return redirect('/tables')
        else:
            error_message = response.get_json().get('error', 'Terjadi kesalahan.')
            flash(f"Gagal menambahkan artikel: {error_message}", "danger")
    
    return render_template('home/tambah_artikel.html')

@app.route('/delete-artikel/<artikel_id>', methods=['POST'])
@admin_required
def delete_artikel_view(artikel_id):
    response, status = artikel_controller.delete_artikel(artikel_id)
    if status == 200:
        flash("Artikel berhasil dihapus.", "success")
    else:
        flash("Gagal menghapus artikel.", "danger")
    return redirect('/tables')


@app.route('/edit-artikel/<artikel_id>', methods=['GET', 'POST'])
@admin_required
def edit_artikel_view(artikel_id):
    if request.method == 'POST':
        data = {
            'title': request.form['title'],
            'content': request.form['content'],
            'author': request.form['author']
        }
        response, status = artikel_controller.update_artikel(artikel_id, data)
        if status == 200:
            flash("Artikel berhasil diperbarui.", "success")
        else:
            flash("Gagal memperbarui artikel.", "danger")
        return redirect('/tables')

    response, status = artikel_controller.get_artikel_by_id(artikel_id)
    if status != 200:
        flash("Artikel tidak ditemukan.", "danger")
        return redirect('/tables')

    artikel = response.get_json()
    return render_template('home/edit_artikel.html', artikel=artikel)

@app.route('/api/history', methods=['POST'])
@jwt_required()
def save_detection_history():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    print("📦 JSON diterima dari Flutter:", data)

    posture = data.get('posture')
    angle = data.get('angle')

    if not posture or angle is None:
        return jsonify({"message": "posture and angle are required"}), 400

    history_model = DetectionHistory(mongo.db)
    history_model.save_history(user_id, posture, angle)

    return jsonify({"message": "History saved"}), 201

@app.route('/api/history', methods=['GET'])
@jwt_required()
def get_detection_history():
    user_id = get_jwt_identity()
    history_model = DetectionHistory(mongo.db)
    history = history_model.get_user_history(user_id)
    return jsonify({'success': True, 'data': history}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5012)