import sqlite3
import logging

DB_NAME = "bot_database.db"

def init_db():
    """Инициализирует базу данных, создавая необходимые таблицы."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица розыгрышей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS giveaways (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            message_id INTEGER,
            prize TEXT,
            end_time TEXT,
            invite_link TEXT,
            giveaway_type TEXT,
            is_active BOOLEAN DEFAULT 1
        )
    ''')

    # Таблица участников
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            giveaway_id INTEGER,
            username TEXT,
            emoji TEXT,
            votes INTEGER DEFAULT 0,
            FOREIGN KEY(giveaway_id) REFERENCES giveaways(id)
        )
    ''')

    # Таблица голосов (кто за кого голосовал)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            giveaway_id INTEGER,
            participant_id INTEGER,
            FOREIGN KEY(giveaway_id) REFERENCES giveaways(id),
            FOREIGN KEY(participant_id) REFERENCES participants(id),
            UNIQUE(user_id, giveaway_id)
        )
    ''')
    
    conn.commit()
    conn.close()

def create_giveaway(chat_id, prize, invite_link, giveaway_type, end_time):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO giveaways (chat_id, prize, invite_link, giveaway_type, end_time)
        VALUES (?, ?, ?, ?, ?)
    ''', (chat_id, prize, invite_link, giveaway_type, end_time))
    giveaway_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return giveaway_id

def add_participant(giveaway_id, username, emoji):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO participants (giveaway_id, username, emoji, votes)
        VALUES (?, ?, ?, 0)
    ''', (giveaway_id, username, emoji))
    participant_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return participant_id

def get_giveaway(giveaway_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM giveaways WHERE id = ?', (giveaway_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_participants(giveaway_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM participants WHERE giveaway_id = ?', (giveaway_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def has_user_voted(user_id, giveaway_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM votes WHERE user_id = ? AND giveaway_id = ?', (user_id, giveaway_id))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def vote_for_participant(user_id, giveaway_id, participant_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Проверяем, голосовал ли уже
        cursor.execute('SELECT 1 FROM votes WHERE user_id = ? AND giveaway_id = ?', (user_id, giveaway_id))
        if cursor.fetchone():
            return False # Уже голосовал
            
        # Записываем голос
        cursor.execute('INSERT INTO votes (user_id, giveaway_id, participant_id) VALUES (?, ?, ?)', 
                       (user_id, giveaway_id, participant_id))
        
        # Обновляем счетчик
        cursor.execute('UPDATE participants SET votes = votes + 1 WHERE id = ?', (participant_id,))
        
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error voting: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
