from datetime import datetime
from bson import ObjectId

class LoginLog:
    def __init__(self, db):
        self.collection = db.login_logs  # Koleksi MongoDB untuk menyimpan log

    def log_login(self, user_id, status, user_agent, ip_address):
        log_data = {
            'user_id': str(user_id),  # Simpan sebagai string
            'status': status,
            'timestamp': datetime.utcnow(),
            'user_agent': user_agent,
            'ip_address': ip_address
        }
        return self.collection.insert_one(log_data).inserted_id

    def find_logs_by_user_id(self, user_id):
        logs = list(self.collection.find({'user_id': str(user_id)}).sort('timestamp', -1))
        for log in logs:
            log['_id'] = str(log['_id'])
            log['timestamp'] = log['timestamp'].isoformat()
        return logs

    def find_all_logs(self):
        return list(self.collection.find())

    def delete_logs_by_user_id(self, user_id):
        return self.collection.delete_many({'user_id': str(user_id)})
