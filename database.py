import sqlite3
import hashlib

def init_db():
    conn = sqlite3.connect("roleplay_data.db", check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            is_admin INTEGER DEFAULT 0,
            user_name TEXT DEFAULT '',
            user_persona TEXT DEFAULT '',
            pronoun_speak TEXT DEFAULT '',
            pronoun_desc TEXT DEFAULT '',
            call_speak TEXT DEFAULT '',
            call_desc TEXT DEFAULT ''
        )
    """)
    
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if "is_admin" not in columns: cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    if "user_name" not in columns: cursor.execute("ALTER TABLE users ADD COLUMN user_name TEXT DEFAULT ''")
    if "user_persona" not in columns: cursor.execute("ALTER TABLE users ADD COLUMN user_persona TEXT DEFAULT ''")
    if "pronoun_speak" not in columns: cursor.execute("ALTER TABLE users ADD COLUMN pronoun_speak TEXT DEFAULT ''")
    if "pronoun_desc" not in columns: cursor.execute("ALTER TABLE users ADD COLUMN pronoun_desc TEXT DEFAULT ''")
    if "call_speak" not in columns: cursor.execute("ALTER TABLE users ADD COLUMN call_speak TEXT DEFAULT ''")
    if "call_desc" not in columns: cursor.execute("ALTER TABLE users ADD COLUMN call_desc TEXT DEFAULT ''")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            name TEXT PRIMARY KEY,
            prompt TEXT,
            personality TEXT,
            lore TEXT,
            first_message TEXT,
            avatar BLOB,
            creator TEXT DEFAULT 'admin'
        )
    """)
    
    # ตรวจสอบคอลัมน์ creator ในกรณีที่ฐานข้อมูลเดิมยังไม่มี
    cursor.execute("PRAGMA table_info(characters)")
    c_cols = [col[1] for col in cursor.fetchall()]
    if "creator" not in c_cols:
        cursor.execute("ALTER TABLE characters ADD COLUMN creator TEXT DEFAULT 'admin'")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supporting_characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            char_name TEXT,
            sub_name TEXT,
            sub_prompt TEXT,
            sub_personality TEXT,
            sub_lore TEXT,
            sub_avatar BLOB
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS character_status (
            username TEXT,
            char_name TEXT,
            affection_score INTEGER DEFAULT 0,
            relationship_level TEXT DEFAULT 'คนแปลกหน้า',
            PRIMARY KEY (username, char_name)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS novel_memories (
            username TEXT,
            char_name TEXT,
            memory_summary TEXT,
            PRIMARY KEY (username, char_name)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            char_name TEXT,
            task_desc TEXT,
            reward_points INTEGER DEFAULT 10
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_quests (
            username TEXT,
            quest_id INTEGER,
            is_completed INTEGER DEFAULT 0,
            PRIMARY KEY (username, quest_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS character_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            char_name TEXT,
            photo BLOB,
            photo_hash TEXT
        )
    """)
    
    cursor.execute("PRAGMA table_info(character_photos)")
    p_cols = [col[1] for col in cursor.fetchall()]
    if "photo_hash" not in p_cols:
        cursor.execute("ALTER TABLE character_photos ADD COLUMN photo_hash TEXT DEFAULT ''")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            char_name TEXT,
            role TEXT,
            content TEXT,
            image_blob BLOB
        )
    """)
    
    conn.commit()
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_relationship_level(score):
    levels = [
        (0, "คนแปลกหน้า"), (100, "คนรู้จัก"), (200, "เพื่อนใหม่"), 
        (300, "เพื่อนสนิท"), (400, "คนรู้ใจ"), (500, "คู่ชีวิต / คนสำคัญ"), 
        (600, "พาร์ทเนอร์รู้ใจ"), (700, "โซลเมท"), (800, "ความผูกพันลึกซึ้ง"), (900, "รักแท้ไร้ขีดจำกัด")
    ]
    idx = min(score // 100, len(levels) - 1)
    return levels[idx][1]
