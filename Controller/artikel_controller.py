import os
from flask import jsonify, request
from Models.artikel_model import Artikel
from bson import ObjectId

class ArtikelController:
    def __init__(self, mongo):
        self.artikel_model = Artikel(mongo)

    def create_artikel(self):
        data = request.get_json()
        required_fields = ['title', 'content', 'author']
        if not data or any(field not in data for field in required_fields):
            return jsonify({
                'error': 'Semua field harus diisi',
                'required_fields': required_fields
            }), 400
        
        artikel_id = self.artikel_model.create_artikel(
            title=data['title'],
            content=data['content'],
            author=data['author']
        )

        return jsonify({
            'message': 'Artikel berhasil dibuat',
            'artikel_id': str(artikel_id)
        }), 201

    def get_all_artikels(self, from_view=False):
        if not from_view and request.headers.get('x-api-key') != os.getenv('API_KEY'):
            return jsonify({'message': 'Unauthorized'}), 401

        artikels = self.artikel_model.find_all_artikels()
        result = [{
            'id': str(a['_id']),
            'title': a['title'],
            'content': a['content'],
            'author': a['author'],
            'created_at': a.get('created_at'),
            'updated_at': a.get('updated_at')
        } for a in artikels]

        return jsonify(result), 200

    def get_artikel_by_id(self, artikel_id):
        try:
            obj_id = ObjectId(artikel_id)
        except Exception:
            return jsonify({'error': 'ID tidak valid'}), 400

        artikel = self.artikel_model.find_artikel_by_id(obj_id)
        if not artikel:
            return jsonify({'error': 'Artikel tidak ditemukan'}), 404

        return jsonify({
            'id': str(artikel['_id']),
            'title': artikel['title'],
            'content': artikel['content'],
            'author': artikel['author'],
            'created_at': artikel.get('created_at'),
            'updated_at': artikel.get('updated_at')
        }), 200

    def update_artikel(self, artikel_id):
        try:
            obj_id = ObjectId(artikel_id)
        except Exception:
            return jsonify({'error': 'ID tidak valid'}), 400

        data = request.get_json()
        artikel = self.artikel_model.find_artikel_by_id(obj_id)
        if not artikel:
            return jsonify({'error': 'Artikel tidak ditemukan'}), 404

        updated = self.artikel_model.update_artikel(obj_id, data)
        if updated.modified_count == 0:
            return jsonify({'message': 'Tidak ada perubahan yang dilakukan'}), 200

        return jsonify({'message': 'Artikel berhasil diperbarui'}), 200

    def delete_artikel(self, artikel_id):
        try:
            obj_id = ObjectId(artikel_id)
        except Exception:
            return jsonify({'error': 'ID tidak valid'}), 400

        artikel = self.artikel_model.find_artikel_by_id(obj_id)
        if not artikel:
            return jsonify({'error': 'Artikel tidak ditemukan'}), 404

        self.artikel_model.delete_artikel(obj_id)
        return jsonify({'message': 'Artikel berhasil dihapus'}), 200

    def get_artikel_by_id(self, artikel_id):
        try:
            obj_id = ObjectId(artikel_id)
        except Exception:
            return jsonify({'error': 'ID tidak valid'}), 400

        artikel = self.artikel_model.find_artikel_by_id(obj_id)
        if not artikel:
            return jsonify({'error': 'Artikel tidak ditemukan'}), 404

        return jsonify({
            'id': str(artikel['_id']),
            'title': artikel['title'],
            'content': artikel['content'],
            'author': artikel['author'],
            'created_at': artikel.get('created_at'),
            'updated_at': artikel.get('updated_at')
        }), 200

    def update_artikel(self, artikel_id, data=None):
        try:
            obj_id = ObjectId(artikel_id)
        except Exception:
            return jsonify({'error': 'ID tidak valid'}), 400

        if data is None:
            data = request.get_json()

        artikel = self.artikel_model.find_artikel_by_id(obj_id)
        if not artikel:
            return jsonify({'error': 'Artikel tidak ditemukan'}), 404

        updated = self.artikel_model.update_artikel(obj_id, data)
        if updated.modified_count == 0:
            return jsonify({'message': 'Tidak ada perubahan yang dilakukan'}), 200

        return jsonify({'message': 'Artikel berhasil diperbarui'}), 200

    def delete_artikel(self, artikel_id):
        try:
            obj_id = ObjectId(artikel_id)
        except Exception:
            return jsonify({'error': 'ID tidak valid'}), 400

        artikel = self.artikel_model.find_artikel_by_id(obj_id)
        if not artikel:
            return jsonify({'error': 'Artikel tidak ditemukan'}), 404

        self.artikel_model.delete_artikel(obj_id)
        return jsonify({'message': 'Artikel berhasil dihapus'}), 200
    
    def create_artikel_from_view(self, data):
        required_fields = ['title', 'content', 'author']
        if not data or any(field not in data or not data[field] for field in required_fields):
            return jsonify({
                'error': 'Semua field harus diisi',
                'required_fields': required_fields
            }), 400

        artikel_id = self.artikel_model.create_artikel(
            title=data['title'],
            content=data['content'],
            author=data['author']
        )

        return jsonify({
            'message': 'Artikel berhasil dibuat',
            'artikel_id': str(artikel_id)
        }), 201