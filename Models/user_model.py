from bson import ObjectId
import bcrypt
import datetime

class User:
    def __init__(self, mongo):
        self.db = mongo

    def create_user(self, full_name, phone, email, password, age, gender,
                    is_verified=False, verification_token=None,
                    role='user', profile_picture=None):
        
        default_picture_url = "https://ui-avatars.com/api/?name=User&background=007BFF&color=ffffff"

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()) if password else None
        user = {
            'full_name': full_name,
            'phone': phone,
            'email': email,
            'password': hashed_password.decode('utf-8') if hashed_password else '',
            'age': age,
            'gender': gender,
            'is_verified': is_verified,
            'verification_token': verification_token,
            'role': role,
            'profile_picture': profile_picture or default_picture_url,
            'created_at': datetime.datetime.utcnow(),
            'updated_at': datetime.datetime.utcnow()
        }
        return self.db.users.insert_one(user).inserted_id

    def update_user_by_id(self, user_id, update_data):
        self.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': update_data, '$currentDate': {'updated_at': True}}
        )

    def find_user_by_email(self, email):
        return self.db.users.find_one({'email': email})

    def find_user_by_phone(self, phone):
        return self.db.users.find_one({'phone': phone})

    def find_user_by_id(self, user_id):
        return self.db.users.find_one({'_id': ObjectId(user_id)})

    def find_user_by_token(self, token):
        return self.db.users.find_one({'verification_token': token})

    def verify_password(self, user, password):
        return bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8'))

    def update_user_verification(self, user_id):
        self.db.users.update_one(
            {'_id': user_id},
            {'$set': {'is_verified': True}, '$unset': {'verification_token': ""}}
        )

    def save_otp_code(self, email, code):
        self.db.users.update_one(
            {'email': email},
            {
                '$set': {
                    'otp_code': code,
                    'otp_expiry': datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
                }
            }
        )

    def check_otp_code(self, email, code):
        user = self.find_user_by_email(email)
        if not user:
            return False
        expiry = user.get('otp_expiry')
        if not expiry or datetime.datetime.utcnow() > expiry:
            return False
        return user.get('otp_code') == code

    def update_password(self, email, new_password):
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        self.db.users.update_one(
            {'email': email},
            {'$set': {'password': hashed, 'updated_at': datetime.datetime.utcnow()}}
        )

    def clear_otp_code(self, email):
        self.db.users.update_one(
            {'email': email},
            {'$unset': {'otp_code': "", 'otp_expiry': ""}}
        )

    def update_password(self, email, new_password):
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        self.db.users.update_one(
            {'email': email},
            {'$set': {'password': hashed, 'updated_at': datetime.datetime.utcnow()}}
        )
