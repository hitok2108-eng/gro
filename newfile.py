from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import threading
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ===== Настройки =====
app = Flask(__name__)
app.secret_key = 'supersecretkey'
DB_PATH = 'users.db'
BOT_TOKEN = "8415935436:AAFjZ1fS0XKIZhpHBSDOfe6p3suQMA2c0fA"

# ===== Инициализация базы =====
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Новая таблица для отметки прочитанного
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            notification_id INTEGER NOT NULL,
            seen INTEGER DEFAULT 0,
            FOREIGN KEY (notification_id) REFERENCES notifications(id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ===== Flask маршруты =====
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

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if action == 'register':
        if password != password2:
            flash("Пароли не совпадают")
            return redirect(url_for('start'))
        try:
            hashed = generate_password_hash(password)
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
            conn.commit()
            session['username'] = username
            return redirect(url_for('home'))
        except sqlite3.IntegrityError:
            flash("Пользователь с таким именем уже существует")
            return redirect(url_for('start'))
        finally:
            conn.close()
    elif action == 'login':
        c.execute("SELECT password FROM users WHERE username=?", (username,))
        result = c.fetchone()
        conn.close()
        if result and check_password_hash(result[0], password):
            session['username'] = username
            return redirect(url_for('home'))
        else:
            flash("Неверный логин или пароль")
            return redirect(url_for('start'))
    else:
        conn.close()
        flash("Неизвестное действие")
        return redirect(url_for('start'))

@app.route('/shop')
def shop():
    if 'username' not in session:
        return redirect(url_for('start'))
    return render_template('shop.html')

@app.route('/my_orders')
def my_orders():
    if 'username' not in session:
        return redirect(url_for('start'))
    return "<h2>Здесь пока будет ваша страница с заказами (заглушка)</h2>"

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('start'))

# ===== API для уведомлений =====
@app.route('/api/get_unseen_count')
def get_unseen_count():
    if 'username' not in session:
        return jsonify({"count": 0})
    username = session['username']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM user_notifications WHERE username=? AND seen=0", (username,))
    count = c.fetchone()[0]
    conn.close()
    return jsonify({"count": count})

@app.route('/api/get_notifications')
def get_notifications():
    if 'username' not in session:
        return jsonify([])
    username = session['username']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT n.id, n.message, un.seen
        FROM notifications n
        JOIN user_notifications un ON n.id = un.notification_id
        WHERE un.username=?
        ORDER BY n.timestamp DESC LIMIT 5
    """, (username,))
    notifications = [{"id": row[0], "message": row[1], "seen": row[2]} for row in c.fetchall()]
    conn.close()
    return jsonify(notifications)

@app.route('/api/mark_seen', methods=['POST'])
def mark_seen():
    if 'username' not in session:
        return jsonify({"status": "error"})
    username = session['username']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE user_notifications SET seen=1 WHERE username=? AND seen=0", (username,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ===== Telegram-бот обработчики =====
async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Напиши мне любое сообщение — оно сохранится и появится в колокольчике на сайте."
    )

async def save_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO notifications (message) VALUES (?)", (text,))
    notif_id = c.lastrowid

    # создаём для всех пользователей отметку непрочитанного
    c.execute("SELECT username FROM users")
    users = [row[0] for row in c.fetchall()]
    for user in users:
        c.execute("INSERT INTO user_notifications (username, notification_id, seen) VALUES (?, ?, 0)", (user, notif_id))

    # оставляем только последние 5 сообщений
    c.execute("""
        DELETE FROM notifications
        WHERE id NOT IN (SELECT id FROM notifications ORDER BY timestamp DESC LIMIT 5)
    """)
    conn.commit()
    conn.close()
    await update.message.reply_text("Сообщение сохранено!")

def run_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_bot))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_message))
    print("Бот запущен!")

    # Создаём event loop для потока
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.run_polling())

# ===== Запуск Flask + бота =====
if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    app.run(host='0.0.0.0', port=5000, debug=True)
