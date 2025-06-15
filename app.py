from flask import Flask, flash, redirect, render_template, request, jsonify, send_from_directory
from flask_pymongo import PyMongo
from flask_cors import CORS
from dotenv import load_dotenv
import random
import os
from Models.user_model import User
from Controller.auth_controller import AuthController
from Controller.artikel_controller import ArtikelController
from utils import config_oauth, require_api_key, token_required, verify_google_token, create_token

# Load environment variables
load_dotenv()

app = Flask(__name__, static_url_path='/static', static_folder='static')
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/capstone")
mongo = PyMongo(app)
user_model = User(mongo.db)
config_oauth(app)
jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-here")
auth_controller = AuthController(mongo.db, jwt_secret)
artikel_controller = ArtikelController(mongo.db)

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

@app.route('/api/auth/verify-email', methods=['GET'])
def verify_email():
    token = request.args.get('token')
    if not token:
        return jsonify({'message': 'Token tidak ditemukan'}), 400
    user = user_model.find_user_by_token(token)
    if not user:
        return jsonify({'message': 'Token tidak valid atau sudah digunakan'}), 400
    user_model.update_user_verification(user['_id'])
    return jsonify({'message': 'Email berhasil diverifikasi. Anda bisa login sekarang.'}), 200

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
    # Generate kode 6 digit
    otp_code = str(random.randint(100000, 999999))
    # Simpan ke database
    user_model.save_otp_code(email, otp_code)
    # Kirim email via SMTP
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

    # Buat JWT token untuk aplikasi
    jwt_token = create_token(user_id)
    print(f"DEBUG: JWT token dibuat: {jwt_token}")

    return jsonify({
        'token': jwt_token,
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
@require_api_key
@token_required
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



# === ADMIN ROUTES ===
@app.route('/')
def index():
    return render_template('home/index.html')

@app.route('/tables')
def tabel_artikel_view():
    response, status_code = artikel_controller.get_all_artikels(from_view=True)
    artikels = response.get_json() if status_code == 200 else []
    return render_template('home/tables.html', artikels=artikels)

@app.route('/tambah-artikel', methods=['GET', 'POST'])
def tambah_artikel():
    if request.method == 'POST':
        data = {
            'title': request.form['title'],
            'content': request.form['content'],
            'author': request.form['author']
        }
        response, status = artikel_controller.create_artikel_from_view(data)
        if status == 201:
            flash("Artikel berhasil ditambahkan.", "success")
            return redirect('/tables')
        else:
            flash("Gagal menambahkan artikel: " + response.get_json().get('error', ''), "danger")
    return render_template('home/tambah_artikel.html')

@app.route('/delete-artikel/<artikel_id>', methods=['POST'])
def delete_artikel_view(artikel_id):
    response, status = artikel_controller.delete_artikel(artikel_id)
    if status == 200:
        flash("Artikel berhasil dihapus.", "success")
    else:
        flash("Gagal menghapus artikel.", "danger")
    return redirect('/tables')

@app.route('/edit-artikel/<artikel_id>', methods=['GET', 'POST'])
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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5012)