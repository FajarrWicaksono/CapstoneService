import os
from flask import jsonify, request
from Models.artikel_model import Artikel
from bson import ObjectId
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads/artikel'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

class ArtikelController:
    def __init__(self, mongo):
        self.artikel_model = Artikel(mongo)

    def allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        artikels = self.artikel_model.find_all_artikels()
        result = [{
            'id': str(a['_id']),
            'url': a.get('url', ''),
            'title': a.get('title', ''),
            'content': a.get('content', ''),
            'image_url': a.get('image_url', '')
        } for a in artikels]
        return jsonify(result)

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
            'thumbnail_url': artikel.get('thumbnail_url'),
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

    def create_artikel_from_view(self):
        title = request.form.get('title')
        content = request.form.get('content')
        author = request.form.get('author')
        file = request.files.get('thumbnail')

        if not all([title, content, author]):
            return jsonify({'error': 'Semua field harus diisi'}), 400

        thumbnail_url = None
        if file and self.allowed_file(file.filename):
            filename = secure_filename(file.filename)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            thumbnail_url = '/' + filepath

        artikel_id = self.artikel_model.create_artikel(
            title=title,
            content=content,
            author=author,
            thumbnail_url=thumbnail_url
        )

        return jsonify({
            'message': 'Artikel berhasil dibuat',
            'artikel_id': str(artikel_id)
        }), 201
