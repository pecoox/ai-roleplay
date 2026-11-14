import streamlit as st
import psycopg2
import hashlib

def init_db():
    db_url = st.secrets["SUPABASE_URL"]
    conn = psycopg2.connect(db_url, sslmode='require')
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

    admin_pass_hashed = hashlib.sha256("admin".encode()).hexdigest()
    cursor.execute("""
        INSERT INTO users (username, password, is_admin, user_name) 
        VALUES ('admin', %s, 1, 'Admin')
        ON CONFLICT (username) DO UPDATE SET password = EXCLUDED.password, is_admin = 1
    """, (admin_pass_hashed,))

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            name TEXT PRIMARY KEY,
            prompt TEXT,
            personality TEXT,
            lore TEXT,
            first_message TEXT,
            avatar BYTEA,
            creator TEXT DEFAULT 'admin'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supporting_characters (
            id SERIAL PRIMARY KEY,
            char_name TEXT,
            sub_name TEXT,
            sub_prompt TEXT,
            sub_personality TEXT,
            sub_lore TEXT,
            sub_avatar BYTEA
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
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
            char_name TEXT,
            photo BYTEA,
            photo_hash TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            username TEXT,
            char_name TEXT,
            role TEXT,
            content TEXT,
            image_blob BYTEA
        )
    """)

    conn.commit()
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_relationship_level(score):
    levels = [
        (0, "คนแปลกหน้า"),
        (100, "คนรู้จัก"),
        (200, "เพื่อนใหม่"),
        (300, "เพื่อนสนิท"),
        (400, "คนรู้ใจ"),
        (500, "คู่ชีวิต / คนสำคัญ"),
        (600, "พาร์ทเนอร์รู้ใจ"),
        (700, "โซลเมท"),
        (800, "ความผูกพันลึกซึ้ง"),
        (900, "รักแท้ไร้ขีดจำกัด")
    ]
    idx = min(score // 100, len(levels) - 1)
    return levels[idx][1]
