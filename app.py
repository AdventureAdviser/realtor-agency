from flask import Flask, render_template, g, request
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
    # Выбираем «избранные» объекты (в БД поле featured INTEGER: 1 или 0)
    featured = db.execute('SELECT id, title, price, image_url FROM objects WHERE featured=1').fetchall()
    return render_template('index.html', featured=featured)


# Поиск объектов по названию
@app.route('/search')
def search():
    db = get_db()
    q = request.args.get('q', '').strip()
    if q:
        results = db.execute(
            'SELECT id, title, price, image_url FROM objects WHERE title LIKE ?',
            (f'%{q}%',)
        ).fetchall()
    else:
        results = db.execute(
            'SELECT id, title, price, image_url FROM objects'
        ).fetchall()
    return render_template('search.html', results=results, query=q)

if __name__ == '__main__':
    # При первом запуске можно создать БД
    if not os.path.exists(DATABASE):
        con = sqlite3.connect(DATABASE)
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE objects (
                id INTEGER PRIMARY KEY,
                title TEXT,
                price TEXT,
                image_url TEXT,
                featured INTEGER DEFAULT 0
            )
        """)
        # Пример данных
        cur.executemany("INSERT INTO objects (title, price, image_url, featured) VALUES (?, ?, ?, ?)", [
            ("Офис в центре", "от 50 000 ₽/мес", "/static/img/office1.jpg", 1),
            ("Склад на окраине", "от 30 000 ₽/мес", "/static/img/warehouse1.jpg", 1),
            ("Магазин у метро", "от 70 000 ₽/мес", "/static/img/shop1.jpg", 1),
            ("Помещение open space", "от 45 000 ₽/мес", "/static/img/openspace1.jpg", 1),
        ])
        con.commit()
        con.close()
    app.run(debug=True)