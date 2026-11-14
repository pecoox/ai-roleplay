from google import genai
import streamlit as st
from PIL import Image
import io
import random
import json
from database import init_db, hash_password, get_relationship_level
from ai_engine import run_with_timer
from admin_panel import render_admin_sidebar, handle_admin_actions

st.set_page_config(page_title="AI Roleplay - Novel Universe Hub", page_icon="🌌", layout="wide")

st.markdown("""
    <style>
    .stChatMessage { border-radius: 20px !important; padding: 18px 22px !important; margin-bottom: 16px !important; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid rgba(255,255,255,0.1); }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .affection-badge { display: inline-block; background: linear-gradient(135deg, rgba(255,105,180,0.2), rgba(138,43,226,0.2)); border: 1px solid rgba(255,105,180,0.4); border-radius: 20px; padding: 4px 12px; font-size: 12px; color: #ff99cc; font-weight: bold; }
    .stChatMessage p em, .stChatMessage em { color: #94a3b8 !important; font-style: normal !important; }
    .stChatMessage p { line-height: 1.7 !important; margin-bottom: 12px !important; }
    </style>
""", unsafe_allow_html=True)

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

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username" not in st.session_state: st.session_state.username = ""
if "is_admin" not in st.session_state: st.session_state.is_admin = False

# 🔐 หน้าจอ Login
if not st.session_state.logged_in:
    st.title("🌌 AI Roleplay - Novel Universe Hub")
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
                        cursor.execute("SELECT COUNT(*) FROM users")
                        assigned_admin = 1 if (r_user.lower() == "admin" or cursor.fetchone()[0] == 0) else 0
                        cursor.execute("INSERT INTO users (username, password, is_admin, user_name) VALUES (?, ?, ?, ?)", (r_user, hash_password(r_pass), assigned_admin, r_user))
                        conn.commit()
                        st.success("สมัครสมาชิกสำเร็จ! กรุณาไปที่แท็บเข้าสู่ระบบ")
    st.stop()

current_user = st.session_state.username
is_current_admin = st.session_state.is_admin

cursor.execute("SELECT user_name, user_persona FROM users WHERE username = ?", (current_user,))
u_row = cursor.fetchone()
u_name, u_persona = (u_row[0], u_row[1]) if u_row else (current_user, "")

cursor.execute("SELECT name FROM characters")
all_chars = [row[0] for row in cursor.fetchall()]

if "in_chat" not in st.session_state: st.session_state.in_chat = False
if "current_char" not in st.session_state or st.session_state.current_char not in all_chars:
    st.session_state.current_char = all_chars[0] if all_chars else None

with st.sidebar:
    st.markdown(f"👤 **ผู้ใช้งาน:** `{current_user}`")
    if st.button("🚪 ออกจากระบบ", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.in_chat = False
        st.rerun()
    st.divider()
    if st.button("🏠 กลับหน้าแรก", use_container_width=True):
        st.session_state.in_chat = False
        st.rerun()
    st.divider()

    if is_current_admin:
        sidebar_action = render_admin_sidebar(cursor, conn, all_chars, st.session_state.current_char)
    else:
        sidebar_action = "เลือกตัวละคร"

    if all_chars and sidebar_action not in ["✨ สร้างตัวละครหลักด้วย AI (พรีเมียมขั้นสูง)", "🌐 นำเข้าตัวละครจากข้อมูลเว็บ (Smart Parser)"]:
        selected_char = st.selectbox("เลือกตัวละครหลัก:", all_chars, index=all_chars.index(st.session_state.current_char) if st.session_state.current_char in all_chars else 0)
        if selected_char != st.session_state.current_char:
            st.session_state.current_char = selected_char
            st.rerun()

    active_char = st.session_state.current_char
    if is_current_admin:
        handle_admin_actions(sidebar_action, cursor, conn, all_chars, active_char, client, model_name, current_user)

# 🏠 หน้าแรก
if not st.session_state.in_chat:
    st.title("🔥 จักรวาลยอดนิยม & ตัวละครทั้งหมด")
    st.divider()
    if not all_chars:
        st.info("📭 ยังไม่มีตัวละครในระบบ กรุณาสร้างตัวละครหลักผ่านเมนู Admin ด้านข้าง")
    else:
        cols = st.columns(3)
        for idx, c_name in enumerate(all_chars):
            cursor.execute("SELECT prompt, avatar FROM characters WHERE name = ?", (c_name,))
            c_data = cursor.fetchone()
            with cols[idx % 3]:
                with st.container(border=True):
                    if c_data and c_data[1]:
                        st.image(Image.open(io.BytesIO(c_data[1])), use_container_width=True)
                    else:
                        st.image("https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=500", use_container_width=True)
                    st.markdown(f"### 🌟 {c_name}")
                    if st.button("✨ แชท", key=f"b_{c_name}", use_container_width=True):
                        st.session_state.current_char = c_name
                        st.session_state.in_chat = True
                        st.rerun()
    st.stop()

# 💬 ห้องแชท
if st.session_state.in_chat and st.session_state.current_char:
    cursor.execute("SELECT prompt, personality, lore, first_message, avatar FROM characters WHERE name = ?", (st.session_state.current_char,))
    char_data = cursor.fetchone()
    base_prompt, char_personality, char_lore, char_first_msg_raw, char_avatar_img = (
        (char_data[0], char_data[1], char_data[2], char_data[3], Image.open(io.BytesIO(char_data[4]))) if (char_data and char_data[4]) else (char_data[0], char_data[1], char_data[2], char_data[3], None)
    )

    cursor.execute("SELECT sub_name, sub_prompt, sub_personality FROM supporting_characters WHERE char_name = ?", (st.session_state.current_char,))
    supporting_text = ", ".join([f"{s[0]} ({s[1]})" for s in cursor.fetchall()]) or "ไม่มี"

    cursor.execute("INSERT OR IGNORE INTO character_status (username, char_name, affection_score, relationship_level) VALUES (?, ?, 0, 'คนแปลกหน้า')", (current_user, st.session_state.current_char))
    conn.commit()
    
    cursor.execute("SELECT affection_score, relationship_level FROM character_status WHERE username = ? AND char_name = ?", (current_user, st.session_state.current_char))
    status_row = cursor.fetchone()
    current_affection, current_rel_level = status_row[0], status_row[1]

    roleplay_instruction = f"""
คุณคือนักเขียนนิยายโรแมนติก/ดราม่ามืออาชีพ และผู้สวมบทบาทตัวละคร '{st.session_state.current_char}'
- คาแรคเตอร์หลัก: {base_prompt} | นิสัย: {char_personality}
- ตัวละครเสริมในฉาก: {supporting_text}
- ผู้สนทนา: {u_name} | ความสัมพันธ์: {current_rel_level} ({current_affection} แต้ม)
กฎ: บรรยายท่าทางให้อยู่ใน *...* และบทพูดใน "..." บรรทัดสุดท้ายต้องเป็น JSON นี้เป๊ะๆ:
{{"score_change": 2, "quest_update": null, "memory_update": "[สรุปสั้นๆ]"}}
"""

    cursor.execute("SELECT COUNT(*) FROM messages WHERE username = ? AND char_name = ?", (current_user, st.session_state.current_char))
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO messages (username, char_name, role, content) VALUES (?, ?, 'assistant', ?)", (current_user, st.session_state.current_char, "*ปรายตามองคุณ* \"มีธุระอะไร?\""))
        conn.commit()

    cursor.execute("SELECT role, content, image_blob FROM (SELECT role, content, image_blob, id FROM messages WHERE username = ? AND char_name = ? ORDER BY id DESC LIMIT 15) ORDER BY id ASC", (current_user, st.session_state.current_char))
    current_messages = [{"role": r[0], "content": r[1], "image": Image.open(io.BytesIO(r[2])) if r[2] else None} for r in cursor.fetchall()]

    st.markdown(f"### แชทกับ: `{st.session_state.current_char}`")
    st.divider()

    for message in current_messages:
        with st.chat_message("user" if message["role"] == "user" else "assistant", avatar="👤" if message["role"] == "user" else (char_avatar_img or "✨")):
            st.markdown(message["content"])
            if message["image"]: st.image(message["image"], width=280)

    if user_input := st.chat_input(f"ส่งข้อความหา {st.session_state.current_char}..."):
        cursor.execute("INSERT INTO messages (username, char_name, role, content) VALUES (?, ?, 'user', ?)", (current_user, st.session_state.current_char, user_input))
        conn.commit()
        
        with st.chat_message("assistant", avatar=char_avatar_img or "✨"):
            response = client.chats.create(model=model_name, config={"system_instruction": roleplay_instruction}).send_message(user_input)
            st.markdown(response.text.split("{")[0])
            cursor.execute("INSERT INTO messages (username, char_name, role, content) VALUES (?, ?, 'assistant', ?)", (current_user, st.session_state.current_char, response.text.split("{")[0].strip()))
            conn.commit()
        st.rerun()
