from flask import Flask, render_template, g, request, jsonify
import sqlite3
import os

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')

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
                image_url TEXT,
                featured INTEGER DEFAULT 0
            )
        """)
        # Пример данных
        cur.executemany(
            "INSERT INTO objects (title, type, price, image_url, featured) VALUES (?, ?, ?, ?, ?)", [
            ("Офис в центре", "office", "от 50 000 ₽/мес", "/static/img/office1.jpg", 1),
            ("Склад на окраине", "warehouse", "от 30 000 ₽/мес", "/static/img/warehouse1.jpg", 1),
            ("Магазин у метро", "shop", "от 70 000 ₽/мес", "/static/img/shop1.jpg", 1),
            ("Помещение open space", "openspace", "от 45 000 ₽/мес", "/static/img/openspace1.jpg", 1),
        ])
        con.commit()
        con.close()
    app.run(debug=True)