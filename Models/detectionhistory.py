from datetime import datetime

class DetectionHistory:
    def __init__(self, db):
        self.collection = db.detection_history  # Koleksi MongoDB

    def save_history(self, user_id, posture, angle):
        history_data = {
            'user_id': str(user_id),
            'posture': posture,
            'angle': angle,
            'timestamp': datetime.utcnow()
        }
        return self.collection.insert_one(history_data).inserted_id

    def find_history_by_user_id(self, user_id):
        histories = list(self.collection.find({'user_id': str(user_id)}).sort('timestamp', -1))
        for h in histories:
            h['_id'] = str(h['_id'])
            h['timestamp'] = h['timestamp'].isoformat()
        return histories

    def delete_history_by_user_id(self, user_id):
        return self.collection.delete_many({'user_id': str(user_id)})
    
    def get_user_history(self, user_id):
        cursor = self.collection.find({'user_id': str(user_id)}).sort('timestamp', -1)
        history = []
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            doc['timestamp'] = doc['timestamp'].isoformat() if 'timestamp' in doc else None
            history.append(doc)
        return history
