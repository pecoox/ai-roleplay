import psycopg2
import streamlit as st
import hashlib

def init_db():
    url = st.secrets["SUPABASE_URL"]
    
    # ตรวจสอบและเติม sslmode=require เพื่อให้เชื่อมต่อกับ Supabase ได้อย่างเสถียร
    if "?" in url:
        conn_url = f"{url}&sslmode=require"
    else:
        conn_url = f"{url}?sslmode=require"
        
    conn = psycopg2.connect(conn_url)
    cursor = conn.cursor()
    
    # สร้างตารางที่จำเป็นทั้งหมดเพื่อป้องกัน Error เรื่องตารางหาย
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            user_name TEXT,
            user_persona TEXT,
            pronoun_speak TEXT,
            pronoun_desc TEXT,
            call_speak TEXT,
            call_desc TEXT
        );
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            name TEXT PRIMARY KEY,
            prompt TEXT,
            personality TEXT,
            lore TEXT,
            first_message TEXT,
            avatar BYTEA,
            creator TEXT
        );
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supporting_characters (
            id SERIAL PRIMARY KEY,
            char_name TEXT,
            sub_name TEXT,
            sub_prompt TEXT,
            sub_personality TEXT,
            sub_lore TEXT
        );
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS character_status (
            username TEXT,
            char_name TEXT,
            affection_score INTEGER DEFAULT 0,
            relationship_level TEXT DEFAULT 'คนแปลกหน้า',
            PRIMARY KEY (username, char_name)
        );
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS novel_memories (
            username TEXT,
            char_name TEXT,
            memory_summary TEXT,
            PRIMARY KEY (username, char_name)
        );
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quests (
            id SERIAL PRIMARY KEY,
            char_name TEXT,
            task_desc TEXT,
            reward_points INTEGER
        );
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_quests (
            username TEXT,
            quest_id INTEGER,
            is_completed INTEGER DEFAULT 0,
            PRIMARY KEY (username, quest_id)
        );
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS character_photos (
            id SERIAL PRIMARY KEY,
            char_name TEXT,
            photo BYTEA,
            photo_hash TEXT
        );
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            username TEXT,
            char_name TEXT,
            role TEXT,
            content TEXT,
            image_blob BYTEA
        );
    """)
    
    conn.commit()
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_relationship_level(score):
    if score >= 500: return "โซลเมท / คู่ชีวิต"
    elif score >= 300: return "คนรู้ใจ"
    elif score >= 150: return "เพื่อนสนิท"
    elif score >= 50: return "คนคุ้นเคย"
    return "คนแปลกหน้า"
