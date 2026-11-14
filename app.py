from google import genai
import streamlit as st
from PIL import Image
import io
import random
import json
import sqlite3
import hashlib
import time

st.set_page_config(page_title="AI Roleplay - Universe & Character Hub", page_icon="🌌", layout="wide")

st.markdown("""
    <style>
    .stChatMessage { border-radius: 20px !important; padding: 18px 22px !important; margin-bottom: 16px !important; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid rgba(255,255,255,0.1); }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .affection-badge { display: inline-block; background: linear-gradient(135deg, rgba(255,105,180,0.2), rgba(138,43,226,0.2)); border: 1px solid rgba(255,105,180,0.4); border-radius: 20px; padding: 4px 12px; font-size: 12px; color: #ff99cc; font-weight: bold; }
    .stChatMessage p em, .stChatMessage em { color: #94a3b8 !important; font-style: normal !important; }
    .stChatMessage p { line-height: 1.7 !important; margin-bottom: 12px !important; }
    </style>
""", unsafe_allow_html=True)

# 🗄️ ฐานข้อมูลในตัวเดียวกัน
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
    
    # บังคับสร้าง Admin เริ่มต้น
    admin_pass = hashlib.sha256("admin".encode()).hexdigest()
    cursor.execute("""
        INSERT INTO users (username, password, is_admin, user_name) 
        VALUES ('admin', ?, 1, 'Admin')
        ON CONFLICT(username) DO UPDATE SET password = ?, is_admin = 1
    """, (admin_pass, admin_pass))

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

conn = init_db()
cursor = conn.cursor()

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = None

if not api_key:
    st.warning("⚠️ ยังไม่ได้ตั้งค่า GEMINI_API_KEY ใน Streamlit Secrets")
    st.stop()

client = genai.Client(api_key=api_key)
model_name = "gemini-3.5-flash-lite"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_relationship_level(score):
    levels = [
        (0, "คนแปลกหน้า"), (100, "คนรู้จัก"), (200, "เพื่อนใหม่"), (300, "เพื่อนสนิท"),
        (400, "คนรู้ใจ"), (500, "คู่ชีวิต / คนสำคัญ"), (600, "พาร์ทเนอร์รู้ใจ"),
        (700, "โซลเมท"), (800, "ความผูกพันลึกซึ้ง"), (900, "รักแท้ไร้ขีดจำกัด")
    ]
    idx = min(score // 100, len(levels) - 1)
    return levels[idx][1]

# Session States
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username" not in st.session_state: st.session_state.username = ""
if "is_admin" not in st.session_state: st.session_state.is_admin = False
if "in_chat" not in st.session_state: st.session_state.in_chat = False

# Login / Register Screen
if not st.session_state.logged_in:
    st.title("🌌 AI Roleplay - Universe Hub")
    tab1, tab2 = st.tabs(["🔑 เข้าสู่ระบบ", "📝 สมัครสมาชิก"])
    with tab1:
        with st.form("login_form"):
            l_user = st.text_input("Username")
            l_pass = st.text_input("Password", type="password")
            if st.form_submit_button("เข้าสู่ระบบ", use_container_width=True):
                cursor.execute("SELECT password, is_admin FROM users WHERE username = ?", (l_user,))
                row = cursor.fetchone()
                if row and row[0] == hash_password(l_pass):
                    st.session_state.logged_in = True
                    st.session_state.username = l_user
                    st.session_state.is_admin = bool(1 if l_user.lower() == "admin" else row[1])
                    st.success("เข้าสู่ระบบสำเร็จ!")
                    st.rerun()
                else:
                    st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    with tab2:
        with st.form("register_form"):
            r_user = st.text_input("ตั้ง Username")
            r_pass = st.text_input("ตั้ง Password", type="password")
            if st.form_submit_button("สมัครสมาชิก", use_container_width=True):
                if r_user and r_pass:
                    cursor.execute("SELECT username FROM users WHERE username = ?", (r_user,))
                    if cursor.fetchone():
                        st.error("ชื่อผู้ใช้นี้ถูกใช้งานแล้ว")
                    else:
                        cursor.execute("INSERT INTO users (username, password, is_admin, user_name) VALUES (?, ?, 0, ?)", (r_user, hash_password(r_pass), r_user))
                        conn.commit()
                        st.success("สมัครสมาชิกสำเร็จ! ไปที่แท็บเข้าสู่ระบบได้เลย")
    st.stop()

current_user = st.session_state.username
if current_user.lower() == "admin": st.session_state.is_admin = True
is_current_admin = st.session_state.is_admin

cursor.execute("SELECT user_name, user_persona, pronoun_speak, pronoun_desc, call_speak, call_desc FROM users WHERE username = ?", (current_user,))
p_row = cursor.fetchone()
u_name, u_persona, u_pspeak, u_pdesc, u_cspeak, u_cdesc = p_row if p_row else (current_user, "", "", "", "", "")

cursor.execute("SELECT name FROM characters")
all_chars = [row[0] for row in cursor.fetchall()]

if "current_char" not in st.session_state or st.session_state.current_char not in all_chars:
    st.session_state.current_char = all_chars[0] if all_chars else None

with st.sidebar:
    st.markdown(f"👤 **ผู้ใช้งาน:** `{current_user}`")
    st.markdown("🛡️ **สถานะ:** `ผู้ดูแลระบบ (Admin)`" if is_current_admin else "👤 **สถานะ:** `ผู้ใช้งานทั่วไป`")
    st.divider()

    with st.expander("⚙️ ตั้งค่าบทบาทตัวตนของคุณ"):
        with st.form("persona_form"):
            e_uname = st.text_input("ชื่อของคุณ:", value=u_name)
            e_persona = st.text_area("บทบาทของคุณ:", value=u_persona)
            if st.form_submit_button("💾 บันทึก", use_container_width=True):
                cursor.execute("UPDATE users SET user_name = ?, user_persona = ? WHERE username = ?", (e_uname, e_persona, current_user))
                conn.commit()
                st.success("บันทึกสำเร็จ!")
                st.rerun()

    st.divider()
    title_text = "🛠️ จัดการระบบ (Admin Only)" if is_current_admin else "⚙️ จัดการตัวละคร"
    st.markdown(f"### {title_text}")
    
    actions = [
        "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติ)",
        "➕ สร้างตัวละครหลักใหม่ (Manual)",
        "🗑️ ลบตัวละครหลัก"
    ]
    sidebar_action = st.selectbox("เลือกการจัดการ:", actions)

    if all_chars:
        selected_char = st.selectbox("เลือกตัวละครหลัก:", all_chars, index=all_chars.index(st.session_state.current_char) if st.session_state.current_char in all_chars else 0)
        if selected_char != st.session_state.current_char:
            st.session_state.current_char = selected_char
            st.rerun()

    st.divider()
    if st.button("🚪 ออกจากระบบ", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.in_chat = False
        st.rerun()
    if st.button("🏠 กลับหน้าแรก", use_container_width=True):
        st.session_state.in_chat = False
        st.rerun()

    # Admin Action handlers inside sidebar
    if sidebar_action == "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติ)":
        with st.form("ai_gen"):
            ai_name = st.text_input("ชื่อตัวละครหรือดารา:")
            if st.form_submit_button("🚀 สร้างตัวละคร", use_container_width=True) and ai_name:
                with st.spinner("AI กำลังสร้างตัวละคร..."):
                    prompt_gen = f"สร้างข้อมูลสำหรับ '{ai_name}' ในรูปแบบ JSON 1 บรรทัด: {{\"name\": \"{ai_name}\", \"prompt\": \"คาแรคเตอร์\", \"personality\": \"นิสัย\", \"lore\": \"ประวัติ\", \"first_messages\": [\"ข้อความแรก\"]}}"
                    res = client.models.generate_content(model=model_name, contents=prompt_gen)
                    try:
                        data = json.loads(res.text.strip()[res.text.strip().find("{"):res.text.strip().rfind("}")+1])
                        cursor.execute("INSERT OR REPLACE INTO characters (name, prompt, personality, lore, first_message) VALUES (?, ?, ?, ?, ?)", (data.get("name", ai_name), data.get("prompt",""), data.get("personality",""), data.get("lore",""), json.dumps(data.get("first_messages",["สวัสดี"]), ensure_ascii=False)))
                        conn.commit()
                        st.session_state.current_char = data.get("name", ai_name)
                        st.session_state.in_chat = True
                        st.success("สร้างสำเร็จ!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"ข้อผิดพลาด: {e}")
    elif sidebar_action == "➕ สร้างตัวละครหลักใหม่ (Manual)":
        with st.form("manual_gen"):
            m_name = st.text_input("ชื่อตัวละคร:")
            m_prompt = st.text_area("คาแรคเตอร์:")
            if st.form_submit_button("💾 บันทึก", use_container_width=True) and m_name:
                cursor.execute("INSERT OR REPLACE INTO characters (name, prompt, first_message) VALUES (?, ?, ?)", (m_name, m_prompt, json.dumps(["สวัสดีครับ"], ensure_ascii=False)))
                conn.commit()
                st.session_state.current_char = m_name
                st.session_state.in_chat = True
                st.success("บันทึกสำเร็จ!")
                st.rerun()
    elif sidebar_action == "🗑️ ลบตัวละครหลัก" and st.session_state.current_char:
        if st.button(f"🗑️ ยืนยันลบ '{st.session_state.current_char}'", use_container_width=True):
            cursor.execute("DELETE FROM characters WHERE name = ?", (st.session_state.current_char,))
            conn.commit()
            st.session_state.current_char = None
            st.session_state.in_chat = False
            st.rerun()

# 🏠 หน้าแรก
if not st.session_state.in_chat:
    st.title("🔥 จักรวาลยอดนิยม & ตัวละครทั้งหมด")
    st.divider()
    if not all_chars:
        st.info("📭 ยังไม่มีตัวละครในระบบ กรุณาสร้างตัวละครหลักผ่านเมนูด้านข้าง")
    else:
        cols = st.columns(3)
        for idx, c_name in enumerate(all_chars):
            cursor.execute("SELECT prompt, personality, lore FROM characters WHERE name = ?", (c_name,))
            c_data = cursor.fetchone()
            with cols[idx % 3]:
                with st.container(border=True):
                    st.image("https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=500", use_container_width=True)
                    st.markdown(f"### 🌟 {c_name}")
                    if st.button("✨ เริ่มแชท", key=f"chat_{c_name}", use_container_width=True):
                        st.session_state.current_char = c_name
                        st.session_state.in_chat = True
                        st.rerun()
    st.stop()

# 💬 ห้องแชท
if st.session_state.in_chat and st.session_state.current_char:
    cursor.execute("SELECT prompt, personality, lore, first_message FROM characters WHERE name = ?", (st.session_state.current_char,))
    char_data = cursor.fetchone()
    base_prompt, char_personality, char_lore, char_first_msg_raw = char_data if char_data else ("", "", "", "[]")

    cursor.execute("INSERT OR IGNORE INTO character_status (username, char_name, affection_score, relationship_level) VALUES (?, ?, 0, 'คนแปลกหน้า')", (current_user, st.session_state.current_char))
    conn.commit()
    
    cursor.execute("SELECT affection_score, relationship_level FROM character_status WHERE username = ? AND char_name = ?", (current_user, st.session_state.current_char))
    status_row = cursor.fetchone()
    current_affection, current_rel_level = status_row if status_row else (0, "คนแปลกหน้า")

    roleplay_instruction = f"คุณสวมบทบาท '{st.session_state.current_char}': {base_prompt} | นิสัย: {char_personality}\nบรรยายใน *...* และบทพูดใน \"...\"\nบรรทัดสุดท้ายส่งออกเป็น JSON เป๊ะๆ: {{\"score_change\": 2, \"quest_update\": null, \"memory_update\": \"สรุปสั้นๆ\"}}"

    cursor.execute("SELECT COUNT(*) FROM messages WHERE username = ? AND char_name = ?", (current_user, st.session_state.current_char))
    if cursor.fetchone()[0] == 0:
        try:
            msgs = json.loads(char_first_msg_raw)
            init_msg = random.choice(msgs) if msgs else "สวัสดีครับ"
        except:
            init_msg = "สวัสดีครับ"
        cursor.execute("INSERT INTO messages (username, char_name, role, content) VALUES (?, ?, 'assistant', ?)", (current_user, st.session_state.current_char, init_msg))
        conn.commit()

    cursor.execute("SELECT role, content FROM messages WHERE username = ? AND char_name = ? ORDER BY id ASC", (current_user, st.session_state.current_char))
    current_messages = [{"role": r[0], "content": r[1]} for r in cursor.fetchall()]

    col_title, col_reset = st.columns([6, 2])
    with col_title:
        st.markdown(f"### แชทกับ: `{st.session_state.current_char}`")
    with col_reset:
        if st.button("🔄 รีเซ็ตแชท", use_container_width=True):
            cursor.execute("DELETE FROM messages WHERE username = ? AND char_name = ?", (current_user, st.session_state.current_char))
            cursor.execute("UPDATE character_status SET affection_score = 0, relationship_level = 'คนแปลกหน้า' WHERE username = ? AND char_name = ?", (current_user, st.session_state.current_char))
            conn.commit()
            st.rerun()

    st.markdown(f'<div class="affection-badge">💖 ความสัมพันธ์: {current_rel_level} | คะแนน: {current_affection} แต้ม</div>', unsafe_allow_html=True)
    st.divider()

    for message in current_messages:
        with st.chat_message("user" if message["role"] == "user" else "assistant"):
            st.markdown(message["content"])

    if user_input := st.chat_input(f"ส่งข้อความหา {st.session_state.current_char}..."):
        cursor.execute("INSERT INTO messages (username, char_name, role, content) VALUES (?, ?, 'user', ?)", (current_user, st.session_state.current_char, user_input))
        conn.commit()

        with st.chat_message("assistant"):
            try:
                chat = client.chats.create(model=model_name, config={"system_instruction": roleplay_instruction})
                response = chat.send_message(user_input)
                raw_t = response.text
                if "{" in raw_t and "}" in raw_t:
                    clean_t = raw_t[:raw_t.find("{")].strip()
                    try:
                        j_data = json.loads(raw_t[raw_t.find("{"):raw_t.rfind("}")+1])
                        new_score = current_affection + j_data.get("score_change", 2)
                        new_lvl = get_relationship_level(new_score)
                        cursor.execute("UPDATE character_status SET affection_score = ?, relationship_level = ? WHERE username = ? AND char_name = ?", (new_score, new_lvl, current_user, st.session_state.current_char))
                        conn.commit()
                    except:
                        pass
                else:
                    clean_t = raw_t.strip()
            except Exception as e:
                clean_t = f"เกิดข้อผิดพลาด: {e}"

            st.markdown(clean_t)
            cursor.execute("INSERT INTO messages (username, char_name, role, content) VALUES (?, ?, 'assistant', ?)", (current_user, st.session_state.current_char, clean_t))
            conn.commit()
        st.rerun()
