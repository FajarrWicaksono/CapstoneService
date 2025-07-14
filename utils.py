from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import bcrypt
from flask import flash, redirect, request, jsonify, session, url_for
import jwt
import datetime
from functools import wraps
from google.oauth2 import id_token
from authlib.integrations.flask_client import OAuth
from google.auth.transport import requests as google_requests
import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, auth
from werkzeug.utils import secure_filename


load_dotenv()

# === CONFIGURATION ===
JWT_SECRET = os.getenv("JWT_SECRET", "Rahasia Tau")
JWT_ALGORITHM = "HS256"
API_KEY = os.getenv("API_KEY", "Rahasia")
email_address = os.getenv('EMAIL_ADDRESS')
email_password = os.getenv('EMAIL_PASSWORD')
verification_base_url = os.getenv("VERIFICATION_BASE_URL")
oauth = OAuth()

if not firebase_admin._apps:
    cred = credentials.Certificate("credentials\ergosit-a31de-firebase-adminsdk-fbsvc-8e63cf7392.json")  # ← sesuaikan path
    firebase_admin.initialize_app(cred)

# === JWT CREATION ===
def create_token(user_id, secret=JWT_SECRET):
    from Models.user_model import User
    from app import mongo 
    user_model = User(mongo.db)
    user = user_model.find_user_by_id(user_id)
    payload = {
        'sub': str(user_id),
        'user_id': str(user_id),
        'email': user['email'],
        'role': user.get('role', 'user'),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)

def check_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def verify_token(token, secret=JWT_SECRET):
    try:
        return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# === DECORATORS ===
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', None)
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'message': 'Token is missing!'}), 401
        token = auth_header.split(" ")[1]
        payload = verify_token(token)
        if not payload:
            return jsonify({'message': 'Token is invalid or expired!'}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Cek sesi login dari browser
        if session.get('logged_in') and session.get('user_role') == 'admin':
            return f(*args, **kwargs)

        # Cek header Authorization dari API
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                if payload.get('role') == 'admin':
                    return f(*args, **kwargs)
                else:
                    return jsonify({'error': 'Hanya admin yang diizinkan'}), 403
            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'Token expired!'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'error': 'Token tidak valid!'}), 401

        # Jika tidak login dan tidak ada token
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Akses ditolak, login sebagai admin diperlukan.'}), 401
        else:
            flash('Login sebagai admin diperlukan.', 'danger')
            return redirect(url_for('login_admin'))

    return decorated_function


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('x-api-key')
        if not api_key or api_key != API_KEY:
            return jsonify({'message': 'API key missing or invalid!'}), 401
        return f(*args, **kwargs)
    return decorated


# === GOOGLE OAUTH VERIFY ===
def verify_google_token(token):
    try:
        print("DEBUG: Verifying token with Firebase Admin SDK")
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        import traceback
        print("DEBUG: Gagal verifikasi token Firebase:")
        print(traceback.format_exc())
        return None

# === EMAIL VERIFICATION ===
def send_verification_email(recipient_email, token):
    if not email_address or not email_password:
        raise ValueError("EMAIL_ADDRESS or EMAIL_PASSWORD not set in .env")

    msg = EmailMessage()
    msg['Subject'] = 'Verifikasi Email Anda - ERGO Sit'
    msg['From'] = email_address
    msg['To'] = recipient_email

    link = f"{verification_base_url}/api/auth/verify-email?token={token}"

    msg.set_content(f'''
Halo,

Terima kasih telah mendaftar di ERGO Sit.

Silakan klik link berikut untuk memverifikasi email Anda:
{link}

Link ini hanya berlaku satu kali.

Terima kasih!
''')
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(email_address, email_password)
        smtp.send_message(msg)


# === OTP EMAIL SENDER ===
def send_email(receiver_email, otp_code):
    subject = "Kode Verifikasi - Reset Password"
    body = f"Halo,\n\nKode verifikasi Anda adalah: {otp_code}\n\nJangan berikan kode ini kepada siapa pun.\n\nSalam,\nTim ERGO Sit"
    msg = MIMEMultipart()
    msg["From"] = email_address
    msg["To"] = receiver_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_address, email_password)
            server.sendmail(email_address, receiver_email, msg.as_string())
            print(f"DEBUG: Email OTP berhasil dikirim ke {receiver_email}")
    except Exception as e:
        print(f"ERROR: Gagal mengirim email: {e}")


# === GOOGLE OAUTH CONFIG ===
def config_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        access_token_url='https://oauth2.googleapis.com/token',
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        api_base_url='https://www.googleapis.com/oauth2/v1/',
        userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
        client_kwargs={'scope': 'openid email profile'},
    )

def save_profile_picture(file):
    if not file:
        return None
    filename = secure_filename(file.filename)
    folder = 'static/uploads/profile_pictures'
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    file.save(path)
    return f"/{path}"