from flask import Flask, render_template, g, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
import sqlite3
import os

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')

# --- Upload folder for images ---
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'img')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db():
    if 'db' not in g:
        con = sqlite3.connect(DATABASE)
        con.row_factory = sqlite3.Row
        g.db = con
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    db = get_db()
    # Carousel: избранные объекты
    featured = db.execute(
        'SELECT id, title, price, image_url FROM objects WHERE featured=1'
    ).fetchall()

    # Параметры поиска
    q = request.args.get('q', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    obj_type = request.args.get('type', '').strip()

    # Формируем запрос
    sql = 'SELECT id, title, price, image_url FROM objects WHERE 1=1'
    params = []
    # Не фильтруем по q в SQL, фильтрация по q будет в Python ниже
    if min_price:
        sql += ' AND CAST(REPLACE(REPLACE(REPLACE(price, " ₽/мес", ""), "от ", ""), " ", "") AS INTEGER) >= ?'
        params.append(min_price)
    if max_price:
        sql += ' AND CAST(REPLACE(REPLACE(REPLACE(price, " ₽/мес", ""), "от ", ""), " ", "") AS INTEGER) <= ?'
        params.append(max_price)
    if obj_type:
        sql += ' AND type = ?'
        params.append(obj_type)

    # Выполняем SQL с фильтрами по цене и типу
    rows = db.execute(sql, params).fetchall()
    # Фильтрация по части названия без учёта регистра
    if q:
        rows = [row for row in rows if q.lower() in row['title'].lower()]
    # Результат: либо отфильтрованные строки, либо избранные при пустых фильтрах
    filter_applied = bool(q or min_price or max_price or obj_type)
    results = rows if filter_applied else featured

    return render_template(
        'index.html',
        featured=featured,
        results=results,
        query=q
    )

@app.route('/api/search')
def api_search():
    db = get_db()
    q = request.args.get('q', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    obj_type = request.args.get('type', '').strip()

    sql = 'SELECT id, title, price, image_url FROM objects WHERE 1=1'
    params = []
    # Не фильтруем по q в SQL, фильтрация по q будет в Python ниже
    if min_price:
        sql += ' AND CAST(REPLACE(REPLACE(REPLACE(price, " ₽/мес", ""), "от ", ""), " ", "") AS INTEGER) >= ?'
        params.append(min_price)
    if max_price:
        sql += ' AND CAST(REPLACE(REPLACE(REPLACE(price, " ₽/мес", ""), "от ", ""), " ", "") AS INTEGER) <= ?'
        params.append(max_price)
    if obj_type:
        sql += ' AND type = ?'
        params.append(obj_type)

    rows = db.execute(sql, params).fetchall() if params else db.execute(
        'SELECT id, title, price, image_url FROM objects'
    ).fetchall()
    # Фильтрация по части названия без учёта регистра
    if q:
        rows = [row for row in rows if q.lower() in row['title'].lower()]
    results = [
        {'id': row['id'], 'title': row['title'], 'price': row['price'], 'image_url': row['image_url']}
        for row in rows
    ]
    return jsonify(results=results)


# --- Request form and admin routes ---

@app.route('/request', methods=['POST'])
def submit_request():
    db = get_db()
    db.execute(
        "INSERT INTO requests (object_id, name, phone, email, comment) VALUES (?,?,?,?,?)",
        (
            request.form.get('object_id'),
            request.form.get('name'),
            request.form.get('phone'),
            request.form.get('email'),
            request.form.get('comment')
        )
    )
    db.commit()
    return redirect(url_for('index'))

@app.route('/admin/requests')
def admin_requests():
    db = get_db()
    rows = db.execute(
        """SELECT r.id, o.title, r.name, r.phone, r.email, r.comment, r.status
           FROM requests r
           JOIN objects o ON o.id = r.object_id
           ORDER BY r.id DESC"""
    ).fetchall()
    return render_template('admin_requests.html', rows=rows)

@app.route('/admin/close/<int:req_id>')
def admin_close(req_id):
    db = get_db()
    db.execute("UPDATE requests SET status='closed' WHERE id=?", (req_id,))
    db.commit()
    return redirect(url_for('admin_requests'))

# ---------- ADMIN OBJECTS (view / edit / delete) ----------

@app.route('/admin/objects')
def admin_objects():
    db = get_db()
    objs = db.execute("SELECT id, title, type, price, featured FROM objects ORDER BY id DESC").fetchall()
    return render_template('admin_objects.html', objs=objs)

@app.route('/admin/object/<int:obj_id>/edit', methods=['GET', 'POST'])
def admin_object_edit(obj_id):
    db = get_db()
    if request.method == 'POST':
        # --- handle uploaded photos ---
        photos = request.files.getlist('photos')
        if photos and photos[0].filename:  # at least one file selected
            image_url_new = None
            new_paths = []
            for file in photos:
                filename = secure_filename(file.filename)
                save_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(save_path)
                new_paths.append(f"/static/img/{filename}")
            if not image_url_new:
                image_url_new = new_paths[0]  # first uploaded becomes main
            images_csv = ",".join(new_paths)
        else:
            images_csv = request.form.get('existing_images', '')
            image_url_new = request.form.get('existing_image_url')
        db.execute("""UPDATE objects SET title=?, type=?, price=?, address=?, area=?,
                      layout=?, description=?, featured=?, images=?, image_url=? WHERE id=?""",
                   (
                       request.form.get('title'),
                       request.form.get('type'),
                       request.form.get('price'),
                       request.form.get('address'),
                       request.form.get('area'),
                       request.form.get('layout'),
                       request.form.get('description'),
                       1 if request.form.get('featured') else 0,
                       images_csv,
                       image_url_new,
                       obj_id
                   ))
        db.commit()
        return redirect(url_for('admin_objects'))
    obj = db.execute("SELECT * FROM objects WHERE id=?", (obj_id,)).fetchone()
    if obj is None:
        return "Object not found", 404
    return render_template('admin_object_edit.html', obj=obj)

@app.route('/admin/object/<int:obj_id>/delete')
def admin_object_delete(obj_id):
    db = get_db()
    db.execute("DELETE FROM objects WHERE id=?", (obj_id,))
    db.commit()
    return redirect(url_for('admin_objects'))
@app.route('/object/<int:obj_id>')
def object_detail(obj_id):
    db = get_db()
    obj = db.execute('SELECT * FROM objects WHERE id=?', (obj_id,)).fetchone()
    if obj is None:
        return "Object not found", 404

    # Похожие объекты того же типа, кроме текущего
    similar = db.execute(
        'SELECT id, title, price, image_url FROM objects WHERE type=? AND id<>? LIMIT 4',
        (obj['type'], obj_id)
    ).fetchall()

    return render_template('object.html', obj=obj, similar=similar)

if __name__ == '__main__':
    # При первом запуске можно создать БД
    if not os.path.exists(DATABASE):
        con = sqlite3.connect(DATABASE)
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE objects (
                id INTEGER PRIMARY KEY,
                title TEXT,
                type TEXT,
                price TEXT,
                image_url TEXT,           -- главное фото
                images TEXT,               -- CSV дополнительных фото
                address TEXT,
                area INTEGER,              -- площадь в м²
                layout TEXT,               -- планировка/формат
                description TEXT,
                lat REAL,
                lon REAL,
                featured INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER,
                name TEXT,
                phone TEXT,
                email TEXT,
                comment TEXT,
                status TEXT DEFAULT 'open'
            )
        """)
        # Пример данных
        cur.executemany(
            "INSERT INTO objects (title, type, price, image_url, images, address, area, layout, description, lat, lon, featured) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("Офис в центре", "office", "от 50 000 ₽/мес", "/static/img/office1.jpg",
                 "/static/img/office1.jpg,/static/img/office2.jpg",
                 "Москва, ул. Пример 1", 120, "open space",
                 "Современный светлый офис в бизнес‑центре класса A.",
                 55.7558, 37.6176, 1),

                ("Склад на окраине", "warehouse", "от 30 000 ₽/мес", "/static/img/warehouse1.jpg",
                 "/static/img/warehouse1.jpg",
                 "Москва, проезд Складской 5", 300, "cold storage",
                 "Высокие потолки, удобный подъезд для фур.",
                 55.8000, 37.7000, 1),

                ("Магазин у метро", "shop", "от 70 000 ₽/мес", "/static/img/shop1.jpg",
                 "/static/img/shop1.jpg",
                 "Москва, ул. Торговая 12", 80, "street retail",
                 "Потоковое место, первая линия домов.",
                 55.7600, 37.6200, 1),

                ("Помещение open space", "openspace", "от 45 000 ₽/мес", "/static/img/openspace1.jpg",
                 "/static/img/openspace1.jpg",
                 "Москва, ул. Стартапов 3", 110, "open space",
                 "Гибкая планировка, натуральное освещение.",
                 55.7700, 37.6300, 1),
            ]
        )
        con.commit()
        con.close()

    print("Главный сайт:  http://127.0.0.1:5000/")
    print("Панель админа: http://127.0.0.1:5000/admin/requests")
    app.run(debug=True)

