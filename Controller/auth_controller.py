import datetime
import os
import uuid
import bcrypt
from bson import ObjectId
from flask import jsonify, request, url_for
from Models import user_model
from Models.login_log_model import LoginLog
from Models.user_model import User
from utils import check_password, create_token, send_verification_email, verify_token, oauth

class AuthController:
    def __init__(self, mongo, jwt_secret):
        self.user_model = User(mongo)
        self.login_log_model = LoginLog(mongo)
        self.jwt_secret = jwt_secret

    def register(self, data):
        print("DEBUG: Memulai proses registrasi.")
        print(f"DEBUG: Data yang diterima: {data}")

        required_fields = ['full_name', 'phone', 'email', 'password', 'age', 'gender']
        if not data or any(field not in data for field in required_fields):
            print("DEBUG: Field tidak lengkap.")
            return jsonify({'error': 'Semua field harus diisi', 'required_fields': required_fields}), 400

        if self.user_model.find_user_by_email(data['email']):
            print("DEBUG: Email sudah terdaftar.")
            return jsonify({'error': 'Email sudah terdaftar'}), 400

        if self.user_model.find_user_by_phone(data['phone']):
            print("DEBUG: Nomor HP sudah terdaftar.")
            return jsonify({'error': 'Nomor HP sudah terdaftar'}), 400

        if '@' not in data['email'] or '.' not in data['email']:
            print("DEBUG: Format email tidak valid.")
            return jsonify({'error': 'Format email tidak valid'}), 400

        if len(data['password']) < 6:
            print("DEBUG: Password terlalu pendek.")
            return jsonify({'error': 'Password minimal 6 karakter'}), 400

        try:
            age = int(data['age'])
            if age < 12 or age > 120:
                print("DEBUG: Umur tidak valid.")
                return jsonify({'error': 'Umur harus antara 12-120 tahun'}), 400
        except ValueError:
            print("DEBUG: Umur bukan angka.")
            return jsonify({'error': 'Umur harus berupa angka'}), 400

        verification_token = str(uuid.uuid4())
        print("DEBUG: Membuat user baru di database.")

        user_id = self.user_model.create_user(
            full_name=data['full_name'],
            phone=data['phone'],
            email=data['email'],
            password=data['password'],
            age=age,
            gender=data['gender'],
            is_verified=False,
            verification_token=verification_token,
            role='user', 
            profile_picture='' 
        )

        print(f"DEBUG: User ID yang dibuat: {user_id}")
        send_verification_email(data['email'], verification_token)

        return jsonify({
            'message': 'Registrasi berhasil. Silakan verifikasi email Anda melalui tautan yang dikirim.'
        }), 201

    # auth_controller.py
    def login_admin(data):
        user = user_model.find_user_by_email(data['email'])
        if user and check_password(data['password'], user['password']):
            if user['role'].lower() != 'admin':
                return jsonify({'error': 'Akses hanya untuk admin'}), 403
            
            return jsonify({
                'message': 'Login admin berhasil',
                'user': {
                    'email': user['email'],
                    'role': user['role']
                }
            }), 200

        return jsonify({'error': 'Email atau password salah'}), 401


    def login(self, data):
        print("DEBUG: Memulai proses login.")
        print(f"DEBUG: Data login: {data}")

        user_agent = request.headers.get('User-Agent')
        ip_address = request.remote_addr

        if not data or not data.get('email') or not data.get('password'):
            self.login_log_model.log_login(None, "failed", user_agent, ip_address)
            return jsonify({'error': 'Email dan password diperlukan'}), 400

        user = self.user_model.find_user_by_email(data['email'])
        if not user or not self.user_model.verify_password(user, data['password']):
            self.login_log_model.log_login(user['_id'] if user else None, "failed", user_agent, ip_address)
            return jsonify({'error': 'Email atau password salah'}), 401

        if not user.get('is_verified', False):
            self.login_log_model.log_login(user['_id'], "failed", user_agent, ip_address)
            return jsonify({'error': 'Email belum diverifikasi'}), 403

        token = create_token(user['_id'], self.jwt_secret)
        self.login_log_model.log_login(user['_id'], "success", user_agent, ip_address)

        return jsonify({
            'message': 'Login berhasil',
            'token': token,
            'user_id': str(user['_id']),
            'user_email': user['email'],
            'user_full_name': user.get('full_name', ''),
            'user_phone': user.get('phone', ''),
            'user_age': user.get('age', ''),
            'user_gender': user.get('gender', ''),
            'role': user.get('role', 'user'),
            'profile_picture': user.get('profile_picture', '')
        })

    def validate_token(self, token):
        print("DEBUG: Memvalidasi token.")
        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        if token.startswith('Bearer '):
            token = token[7:]

        payload = verify_token(token, self.jwt_secret)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401

        user = self.user_model.find_user_by_id(payload['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({
            'valid': True,
            'user_id': str(user['_id']),
            'user_email': user['email'],
            'user_name': user.get('full_name', ''),
            'role': user.get('role', 'user'),
            'profile_picture': user.get('profile_picture', '')
        })

    def login_with_google(self):
        print("DEBUG: Login dengan Google - memulai redirect.")
        redirect_uri = url_for('google_callback_route', _external=True)
        return oauth.google.authorize_redirect(redirect_uri)

    def google_callback(self):
        print("DEBUG: Callback Google login.")
        try:
            token = oauth.google.authorize_access_token()
            user_info = oauth.google.parse_id_token(token)
            print(f"DEBUG: Informasi user Google: {user_info}")
        except Exception as e:
            print(f"DEBUG: Exception saat Google login: {e}")
            return jsonify({'error': 'Gagal login dengan Google', 'details': str(e)}), 400

        email = user_info.get("email")
        full_name = user_info.get("name")
        picture = user_info.get("picture", "")
        user = self.user_model.find_user_by_email(email)

        if not user:
            print("DEBUG: User Google belum ada, membuat user baru.")
            user_id = self.user_model.create_user(
                full_name=full_name,
                phone="",
                email=email,
                password=None,
                age=0,
                gender="",
                is_verified=True,
                verification_token=None,
                role='user',
                profile_picture=picture
            )
            user = self.user_model.find_user_by_id(user_id)
        else:
            user_id = user['_id']

        jwt_token = create_token(user_id, self.jwt_secret)
        print(f"DEBUG: Token Google login dibuat: {jwt_token}")

        return jsonify({
            'message': 'Login Google berhasil',
            'token': jwt_token,
            'user_id': str(user_id),
            'user_email': email,
            'user_full_name': full_name,
            'role': user.get('role', 'user'),
            'profile_picture': user.get('profile_picture', '')
        })
    
    def get_profile(self):
        token = request.headers.get('Authorization').split(" ")[1]
        payload = verify_token(token, self.jwt_secret)

        if not payload:
            return jsonify({'error': 'Token tidak valid'}), 401

        user = self.user_model.find_user_by_id(payload['user_id'])
        if not user:
            return jsonify({'error': 'Pengguna tidak ditemukan'}), 404

        return jsonify({
            'user_id': str(user['_id']),
            'full_name': user.get('full_name', ''),
            'email': user.get('email', ''),
            'phone': user.get('phone', ''),
            'age': user.get('age', ''),
            'gender': user.get('gender', ''),
            'profile_picture': user.get('profile_picture', '')
        })
    
    def update_profile_from_token(self):
        token = request.headers.get('Authorization').split(" ")[1]
        payload = verify_token(token, self.jwt_secret)

        if not payload:
            return jsonify({'error': 'Token tidak valid'}), 401

        user_id = payload['user_id']
        return self.update_profile(user_id)

    def update_profile(self, user_id):
        user = self.user_model.find_user_by_id(user_id)
        if not user:
            return jsonify({'error': 'Pengguna tidak ditemukan'}), 404

        data = request.form
        file = request.files.get('profile_picture')

        try:
            update_data = {
                'full_name': data.get('full_name', user.get('full_name')),
                'phone': data.get('phone', user.get('phone')),
                'age': int(data.get('age', user.get('age'))),
                'gender': data.get('gender', user.get('gender')),
                'updated_at': datetime.datetime.utcnow()
            }
        except Exception as e:
            return jsonify({'error': 'Format data tidak valid', 'details': str(e)}), 400

        if file:
            from werkzeug.utils import secure_filename
            import os

            folder = 'static/uploads/profile_pictures'
            os.makedirs(folder, exist_ok=True)

            filename = secure_filename(file.filename)
            save_path = os.path.join(folder, filename)
            file.save(save_path)

            # Convert local path to accessible URL if needed
            host_url = request.host_url.rstrip('/')
            image_url = f"{host_url}/static/uploads/profile_pictures/{filename}"  # ✅ Fix backslash error
            update_data['profile_picture'] = image_url

        self.user_model.db.users.update_one(
            {'_id': user['_id']},
            {'$set': update_data}
        )

        return jsonify({'message': 'Profil berhasil diperbarui'}), 200
    
    def delete_user(self):
        try:
            token = request.headers.get('Authorization')
            if not token or not token.startswith("Bearer "):
                return jsonify({"error": "Token missing or invalid"}), 401
            token = token.split(" ")[1]

            payload = verify_token(token, self.jwt_secret)
            if not payload:
                return jsonify({"error": "Invalid or expired token"}), 401

            user_id = payload['user_id']
            try:
                obj_id = ObjectId(user_id)
            except Exception:
                return jsonify({"error": "Invalid user ID"}), 400

            user = self.user_model.find_user_by_id(user_id)
            if not user:
                return jsonify({"error": "User not found"}), 404

            result = self.user_model.db.users.delete_one({"_id": obj_id})
            if result.deleted_count == 0:
                return jsonify({"error": "User not found"}), 404

            return jsonify({"message": "User deleted successfully"}), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    def change_password_from_token(self):
        token = request.headers.get('Authorization').split(" ")[1]
        payload = verify_token(token, self.jwt_secret)

        if not payload:
            return jsonify({'success': False, 'message': 'Token tidak valid'}), 401

        user_id = payload['user_id']
        user = self.user_model.find_user_by_id(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User tidak ditemukan'}), 404

        data = request.get_json()
        old_password = data.get('old_password')
        new_password = data.get('new_password')

        if not old_password or not new_password:
            return jsonify({'success': False, 'message': 'Old password dan new password wajib diisi'}), 400

        # Verifikasi old password
        if not self.user_model.verify_password(user, old_password):
            return jsonify({'success': False, 'message': 'Password lama salah'}), 400

        # Update new password
        self.user_model.update_password(user['email'], new_password)

        return jsonify({'success': True, 'message': 'Password berhasil diubah'}), 200

