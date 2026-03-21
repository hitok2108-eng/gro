import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template, request, redirect, session, url_for, flash
import os
import psycopg2
import time
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit, join_room

DATABASE_URL = os.environ.get("DATABASE_URL")
# ================== APP INIT ==================
app = Flask(__name__)
app.secret_key = 'supersecretkey'

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ================== MYSQL ==================


def get_db():
     conn = psycopg2.connect(DATABASE_URL)
     return conn

def init_db():
 
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(100) UNIQUE,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS messages(
        id SERIAL PRIMARY KEY,
        chat_id VARCHAR(100),
        user_name VARCHAR(100),
        text TEXT,
        image TEXT,
        reply TEXT,
        time BIGINT
    )
    """)
# админ
    c.execute("""
    CREATE TABLE IF NOT EXISTS room_admins(
        id SERIAL PRIMARY KEY,
        username VARCHAR(100),
        chat_id INTEGER
     )
     """)

     c.execute("""
     CREATE TABLE IF NOT EXISTS user_chat_read (
         id SERIAL PRIMARY KEY,
         username VARCHAR(100),
         chat_id VARCHAR(100),
         last_read_time BIGINT,
         UNIQUE(username, chat_id)
     )
     """)
    conn.commit()
    conn.close()
     

init_db()



# ================== HELPERS ==================
def parse_chat_id(chat_id):
    """Преобразует chatId вида 'room_1' или 'admin_1' в число 1"""
    if isinstance(chat_id, str) and "_" in chat_id:
        return int(chat_id.split("_")[1])
    return int(chat_id)

# ================== AUTH ==================

@app.route('/')
def start():
    if 'username' in session:
        return redirect(url_for('home'))
    return render_template('index_login.html')

@app.route('/index')
def home():
    if 'username' not in session:
        return redirect(url_for('start'))
    return render_template('index.html')

@app.route('/auth', methods=['POST'])
def auth():

    action = request.form.get('action')
    username = request.form.get('username')
    password = request.form.get('password')
    password2 = request.form.get('password2')

    conn = get_db()
    c = conn.cursor()

    if action == 'register':

        if password != password2:
            flash("Пароли не совпадают")
            return redirect(url_for('start'))

        try:
            hashed = generate_password_hash(password)

            c.execute(
                "INSERT INTO users (username,password) VALUES (%s,%s)",
                (username,hashed)
            )

            conn.commit()

            session['username'] = username
            return redirect(url_for('home'))

        except:
            flash("Пользователь существует")
            return redirect(url_for('start'))

        finally:
            conn.close()

    elif action == 'login':

        c.execute("SELECT password FROM users WHERE username=%s",(username,))
        result = c.fetchone()

        conn.close()

        if result and check_password_hash(result[0], password):

            session['username'] = username
            return redirect(url_for('home'))

        else:

            flash("Неверные данные")
            return redirect(url_for('start'))

# ================== CHATS ==================

@app.route('/chats')
def chats():
    if 'username' not in session:
        return redirect(url_for('start'))
    return render_template('chats.html', username=session['username'])

@app.route('/go_chats')
def go_chats():
    if 'username' not in session:
        return redirect(url_for('start'))
    return redirect(url_for('chats'))

@app.route("/get_unread")
def get_unread():
    if 'username' not in session:
        return {}

    username = session['username']

    conn = get_db()
    c = conn.cursor()

    c.execute("""
    SELECT m.chat_id, COUNT(*)
    FROM messages m
    LEFT JOIN user_chat_read r
      ON m.chat_id = r.chat_id AND r.username = %s
    WHERE m.time > COALESCE(r.last_read_time, 0)
    GROUP BY m.chat_id
    """, (username,))

    rows = c.fetchall()
    conn.close()

    return {chat_id: count for chat_id, count in rows}

# ================== OLD ROUTES (ВСЕ СОХРАНЕНЫ) ==================

@app.route('/shop')
def shop():
    if 'username' not in session:
        return redirect(url_for('start'))
    return render_template('mario.html')

@app.route('/mario')
def mario():
    return render_template('mario.html')

@app.route('/samurai1')
def samurai1():
    return render_template('samurai1.html')

@app.route('/fast')
def fast():
    return render_template('fast.html')

@app.route('/federacia')
def federacia():
    return render_template('federacia.html')

@app.route('/EnergizerExchange1')
def EnergizerExchange1():
    return render_template('EnergizerExchange1.html')

@app.route('/propoganda')
def propoganda():
    return render_template('propoganda.html')

@app.route('/fa1')
def fa1():
    return render_template('fa1.html')

@app.route('/barselona')
def barselona():
    return render_template('barselona.html')

@app.route('/mah')
def mah():
    return render_template('mah.html')

@app.route('/green2')
def green2():
    return render_template('green2.html')

@app.route('/brat')
def brat():
    return render_template('brat.html')

@app.route('/katia')
def katia():
    return render_template('katia.html')

@app.route('/detka')
def detka():
    return render_template('detka.html')

@app.route('/scrudj')
def scrudj():
    return render_template('scrudj.html')

@app.route('/my_orders')
def my_orders():
    if 'username' not in session:
        return redirect(url_for('start'))
    return "<h2>Заглушка заказов</h2>"

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('start'))

# ================== ADMIN PANEL ==================

@app.route("/admin_panel")
def admin_panel():

    if 'username' not in session:
        return redirect(url_for('start'))

    return render_template("admin_panel.html")

@app.route("/add_admin", methods=["POST"])
def add_admin():
    username = request.form.get("username")
    chat_id = int(request.form.get("chat_id"))

    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO room_admins(username, chat_id) VALUES (%s, %s)", (username, chat_id))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_panel"))

@app.route("/remove_admin", methods=["POST"])
def remove_admin():
    username = request.form.get("username")
    chat_id = int(request.form.get("chat_id"))

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM room_admins WHERE username=%s AND chat_id=%s", (username, chat_id))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_panel"))
# ================== LOAD MORE HISTORY ==================

@app.route("/load_more")
def load_more():
    chat_id = request.args.get("chatId")
    before = int(request.args.get("before") or 0)

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, user_name, text, image, reply, time
        FROM messages
        WHERE chat_id=%s AND time < %s
        ORDER BY time DESC
        LIMIT 50
    """, (chat_id, before))
    rows = c.fetchall()
    conn.close()

    messages_list = []
    for r in rows:
        messages_list.append({
            "id": r[0],
            "user": r[1],
            "text": r[2],
            "image": r[3],
            "reply": r[4],
            "time": r[5]
        })

    messages_list.reverse()
    return {"messages": messages_list}

#============ admin

def is_admin(username, chat_id):
    

    conn = get_db()
    c = conn.cursor()

    c.execute("""
    SELECT 1 FROM room_admins
    WHERE username=%s AND chat_id=%s
    """,(username, chat_id))

    result = c.fetchone()

    conn.close()

    return result is not None

@socketio.on("mark_read")
def mark_read(data):
    if 'username' not in session:
        return

    username = session['username']
    chat_id = data.get("chatId")
    last_time = data.get("time")

    if not chat_id or not last_time:
        return

    conn = get_db()
    c = conn.cursor()

    c.execute("""
        INSERT INTO user_chat_read(username, chat_id, last_read_time)
        VALUES (%s, %s, %s)
        ON CONFLICT (username, chat_id)
        DO UPDATE SET last_read_time = EXCLUDED.last_read_time
    """, (username, chat_id, last_time))

    conn.commit()
    conn.close()

# ================== SOCKET ==================

@socketio.on("connect")
def connect():
    if 'username' not in session:
        return False

@socketio.on("join")
def on_join(data):
    raw_chat_id = data.get("chatId")
    if not raw_chat_id or 'username' not in session:
        return

    join_room(raw_chat_id)

    username = session.get("username")
    admin = is_admin(username, raw_chat_id)
    emit("admin_status", {"is_admin": admin})

    # Подгружаем последние 50 сообщений для комнаты
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, user_name, text, image, reply, time
        FROM messages
        WHERE chat_id=%s
        ORDER BY time DESC
        LIMIT 50
    """, (raw_chat_id,))
    rows = c.fetchall()
    conn.close()

    messages_list = [{
        "id": r[0],
        "user": r[1],
        "text": r[2],
        "image": r[3],
        "reply": r[4],
        "time": r[5]
    } for r in rows]

    messages_list.reverse()  # старые сообщения сверху
    emit("chat_history", {"chatId": raw_chat_id, "messages": messages_list})

    print("LOAD CHAT:", raw_chat_id)
# ================== SEND MESSAGE ==================

@socketio.on("send_message")
def on_message(data):
    # Проверка авторизации
    if 'username' not in session:
        return

    chat_id = data.get("chatId")
    username = session['username']

    if not chat_id:
        return

    # ПРОВЕРКА НА МУТ
    if chat_id in muted_users and username in muted_users[chat_id]:
        print(f"User {username} is muted in {chat_id}, message ignored")
        return

    # Получаем данные сообщения
    text = data.get("text") or None
    image = data.get("image") or None
    reply = data.get("reply") or None
    msg_time = data.get("time") or int(time.time() * 1000)

    msg = {
        "user": username,
        "text": text,
        "image": image,
        "reply": reply,
        "time": msg_time
    }

    # Сохраняем сообщение в базе данных
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO messages(chat_id, user_name, text, image, reply, time)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """, (chat_id, username, text, image, reply, msg_time))
    msg["id"] = c.fetchone()[0]
    conn.commit()

    # Ограничение до 2000 сообщений на чат
    c.execute("""
        DELETE FROM messages
        WHERE id NOT IN (
            SELECT id FROM (
                SELECT id FROM messages
                WHERE chat_id=%s
                ORDER BY time DESC
                LIMIT 2000
            ) t
        )
        AND chat_id=%s
    """, (chat_id, chat_id))
    conn.commit()
    conn.close()

    # Отправляем сообщение всем участникам комнаты
    emit("new_message", {"chatId": chat_id, "message": msg}, to=chat_id)

    print(f"SEND MESSAGE: {msg} in {chat_id}")
# ================== DELETE MESSAGE ==================

@socketio.on("delete_message")
def delete_message(data):
    username = session.get("username")
    chat_id = data.get("chatId")
    msg_id = data.get("id")

    if not username or not chat_id or not msg_id:
        return

    if not is_admin(username, chat_id):
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE id=%s AND chat_id=%s", (msg_id, chat_id))
    conn.commit()
    conn.close()

    # Отправка всем в комнате, чтобы клиент удалил сообщение
    emit("message_deleted", {"chatId": chat_id, "id": msg_id}, to=chat_id)

    print(f"DELETED MESSAGE {msg_id} FROM {chat_id}")

# ================== MUTE USER ==================

muted_users = {}  # ключ: chatId, значение: set(username)

@socketio.on("mute_user")
def mute_user(data):
    username = session.get("username")
    chat_id = data.get("chatId")
    target_user = data.get("user")

    if not username or not chat_id or not target_user:
        return

    # Проверяем, что текущий пользователь — админ
    if not is_admin(username, chat_id):
        return

    # Создаём множество для чата, если его ещё нет
    if chat_id not in muted_users:
        muted_users[chat_id] = set()

    muted_users[chat_id].add(target_user)

    print(f"MUTED {target_user} in {chat_id}")
# ================== START ==================

if __name__ == '__main__':
    socketio.run(app,host='0.0.0.0',port=5001,debug=False)
