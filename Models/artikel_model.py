from bson import ObjectId
from datetime import datetime

class Artikel:
    def __init__(self, db):
        self.db = db

    def create_artikel(self, title, content, author):
        data = {
            'title': title,
            'content': content,
            'author': author,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        return self.db.artikels.insert_one(data).inserted_id

    def find_all_artikels(self):
        return list(self.db.artikels.find())

    def find_artikel_by_id(self, artikel_id):
        return self.db.artikels.find_one({'_id': ObjectId(artikel_id)})

    def update_artikel(self, artikel_id, data):
        data['updated_at'] = datetime.utcnow()
        return self.db.artikels.update_one(
            {'_id': ObjectId(artikel_id)},
            {'$set': data}
        )

    def delete_artikel(self, artikel_id):
        return self.db.artikels.delete_one({'_id': ObjectId(artikel_id)})