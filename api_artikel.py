from flask import Flask, jsonify, request
from flask_pymongo import PyMongo
from bson import ObjectId
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Konfigurasi MongoDB
app.config["MONGO_URI"] = "mongodb://localhost:27017/ergo_db"
mongo = PyMongo(app)

# Ambil semua artikel
@app.route('/api/artikel', methods=['GET'])
def get_all_artikel():
    artikel_list = []
    for artikel in mongo.db.artikel.find():
        artikel_list.append({
            "_id": str(artikel["_id"]),
            "judul": artikel.get("judul"),
            "konten": artikel.get("konten"),
            "kategori": artikel.get("kategori"),
            "tanggal": artikel.get("tanggal")
        })
    return jsonify(artikel_list)


# Ambil artikel berdasarkan ID
@app.route('/api/artikel/<string:id>', methods=['GET'])
def get_artikel_by_id(id):
    artikel = mongo.db.artikel.find_one({"_id": ObjectId(id)})
    if artikel:
        return jsonify({
            "_id": str(artikel["_id"]),
            "judul": artikel.get("judul"),
            "konten": artikel.get("konten"),
            "kategori": artikel.get("kategori"),
            "tanggal": artikel.get("tanggal")
        })
    else:
        return jsonify({"error": "Artikel tidak ditemukan"}), 404

# Menjalankan server
if __name__ == '__main__':
    app.run(debug=True, port=5012)
