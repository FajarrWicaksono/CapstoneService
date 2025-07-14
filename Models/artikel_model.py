from bson import ObjectId
from datetime import datetime

class Artikel:
    def __init__(self, db):
        self.collection = db.artikels

    def create_artikel(self, title, content, author, thumbnail_url=None):
        data = {
            'title': title,
            'content': content,
            'author': author,
            'thumbnail_url': thumbnail_url,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        return self.collection.insert_one(data).inserted_id

    def find_all_artikels(self):
        return list(self.collection.find().sort("created_at", -1))  # urut terbaru

    def find_artikel_by_id(self, artikel_id):
        try:
            return self.collection.find_one({'_id': ObjectId(artikel_id)})
        except Exception:
            return None

    def update_artikel(self, artikel_id, data):
        update_fields = {}
        for key in ['title', 'content', 'author', 'thumbnail_url']:
            if key in data:
                update_fields[key] = data[key]
        update_fields['updated_at'] = datetime.utcnow()

        return self.collection.update_one(
            {'_id': ObjectId(artikel_id)},
            {'$set': update_fields}
        )

    def delete_artikel(self, artikel_id):
        return self.collection.delete_one({'_id': ObjectId(artikel_id)})
