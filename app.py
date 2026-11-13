from google import genai
import streamlit as st
import sqlite3
import time
from PIL import Image
import io
import random
import json
import hashlib

st.set_page_config(
    page_title="AI Roleplay - Universe & Character Hub",
    page_icon="🌌",
    layout="wide",
)

# 🎨 ดีไซน์ CSS พรีเมียม
st.markdown(
    """
    <style>
    .stChatMessage {
        border-radius: 20px !important;
        padding: 15px 20px !important;
        margin-bottom: 16px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border: 1px solid rgba(255,255,255,0.1);
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* หลอดสถานะความชอบขนาดเล็กบนหัวแชท AI */
    .affection-badge {
        display: inline-block;
        background: linear-gradient(135deg, rgba(255,105,180,0.2), rgba(138,43,226,0.2));
        border: 1px solid rgba(255,105,180,0.4);
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 12px;
        color: #ff99cc;
        font-weight: bold;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# 🗄️ ฟังก์ชันฐานข้อมูล SQLite พร้อมระบบอัปเดตโครงสร้างอัตโนมัติ
def init_db():
  conn = sqlite3.connect("roleplay_data.db", check_same_thread=False)
  cursor = conn.cursor()

  # ตารางผู้ใช้งานระบบ
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            is_admin INTEGER DEFAULT 0,
            user_persona TEXT DEFAULT ''
        )
    """)

  cursor.execute("PRAGMA table_info(users)")
  columns = [col[1] for col in cursor.fetchall()]
  if "is_admin" not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
  if "user_persona" not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN user_persona TEXT DEFAULT ''")

  # ตัวละครหลัก (ส่วนกลาง ทุกคนเห็นเหมือนกัน)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            name TEXT PRIMARY KEY,
            prompt TEXT,
            personality TEXT,
            lore TEXT,
            first_message TEXT,
            avatar BLOB
        )
    """)

  # ตัวละครเสริม (ส่วนกลาง)
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

  # สถานะความสัมพันธ์ (แยกตาม username และ char_name)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS character_status (
            username TEXT,
            char_name TEXT,
            affection_score INTEGER DEFAULT 0,
            relationship_level TEXT DEFAULT 'คนแปลกหน้า',
            PRIMARY KEY (username, char_name)
        )
    """)

  # ภารกิจส่วนกลาง
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            char_name TEXT,
            task_desc TEXT,
            reward_points INTEGER DEFAULT 10
        )
    """)

  # สถานะการทำภารกิจสำเร็จของแต่ละยูสเซอร์
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_quests (
            username TEXT,
            quest_id INTEGER,
            is_completed INTEGER DEFAULT 0,
            PRIMARY KEY (username, quest_id)
        )
    """)

  # คลังรูปภาพ (ส่วนกลาง)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS character_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            char_name TEXT,
            photo BLOB
        )
    """)

  # ประวัติแชท (แยกตาม username และ char_name)
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

# ดึง API Key
try:
  api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
  api_key = None

if not api_key:
  st.warning("⚠️ ยังไม่ได้ตั้งค่า GEMINI_API_KEY ใน Streamlit Secrets")
  st.stop()

client = genai.Client(api_key=api_key)
model_name = "gemini-3.5-flash-lite"


def hash_password(password):
  return hashlib.sha256(password.encode()).hexdigest()


# จัดการ Session สำหรับ Login
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
if "username" not in st.session_state:
  st.session_state.username = ""
if "is_admin" not in st.session_state:
  st.session_state.is_admin = False

# ==========================================
# 🔐 หน้าจอเข้าสู่ระบบ / สมัครสมาชิก (Login / Register)
# ==========================================
if not st.session_state.logged_in:
  st.title("🌌 AI Roleplay - Universe Hub")
  st.markdown("กรุณาเข้าสู่ระบบหรือสมัครสมาชิกเพื่อเริ่มต้นการเดินทางของคุณ")

  tab1, tab2 = st.tabs(["🔑 เข้าสู่ระบบ", "📝 สมัครสมาชิก"])

  with tab1:
    with st.form("login_form"):
      l_user = st.text_input("ชื่อผู้ใช้ (Username)")
      l_pass = st.text_input("รหัสผ่าน (Password)", type="password")
      l_submit = st.form_submit_button("เข้าสู่ระบบ", use_container_width=True)

      if l_submit:
        if l_user and l_pass:
          cursor.execute(
              "SELECT password, is_admin FROM users WHERE username = ?",
              (l_user,),
          )
          row = cursor.fetchone()
          if row and row[0] == hash_password(l_pass):
            admin_status = 1 if l_user.lower() == "admin" else row[1]

            st.session_state.logged_in = True
            st.session_state.username = l_user
            st.session_state.is_admin = bool(admin_status)
            st.success("เข้าสู่ระบบสำเร็จ!")
            st.rerun()
          else:
            st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
        else:
          st.warning("กรุณากรอกข้อมูลให้ครบถ้วน")

  with tab2:
    with st.form("register_form"):
      r_user = st.text_input("ตั้งชื่อผู้ใช้ (Username)")
      r_pass = st.text_input("ตั้งรหัสผ่าน (Password)", type="password")
      r_submit = st.form_submit_button("สมัครสมาชิก", use_container_width=True)

      if r_submit:
        if r_user and r_pass:
          cursor.execute(
              "SELECT username FROM users WHERE username = ?", (r_user,)
          )
          if cursor.fetchone():
            st.error("ชื่อผู้ใช้นี้ถูกใช้งานแล้ว")
          else:
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            assigned_admin = (
                1 if (r_user.lower() == "admin" or user_count == 0) else 0
            )

            cursor.execute(
                "INSERT INTO users (username, password, is_admin, user_persona)"
                " VALUES (?, ?, ?, ?)",
                (
                    r_user,
                    hash_password(r_pass),
                    assigned_admin,
                    f"นักเรียนใหม่บ้านสลิธีริน เพื่อนร่วมชั้นของเดรโก",
                ),
            )
            conn.commit()
            if assigned_admin:
              st.success(
                  "สมัครสมาชิกสำเร็จ! (บัญชีนี้ได้รับสิทธิ์เป็น Admin เรียบร้อยแล้ว)"
              )
            else:
              st.success(
                  "สมัครสมาชิกสำเร็จ! กรุณากดไปที่แท็บ 'เข้าสู่ระบบ'"
              )
        else:
          st.warning("กรุณากรอกข้อมูลให้ครบถ้วน")
  st.stop()


# ==========================================
# 🌟 ระบบหลักหลังเข้าสู่ระบบแล้ว
# ==========================================
current_user = st.session_state.username
if current_user.lower() == "admin":
  st.session_state.is_admin = True
is_current_admin = st.session_state.is_admin

# ดึงข้อมูล Persona ของผู้ใช้ปัจจุบัน
cursor.execute(
    "SELECT user_persona FROM users WHERE username = ?", (current_user,)
)
p_row = cursor.fetchone()
current_user_persona = (
    p_row[0]
    if p_row and p_row[0]
    else "คุณคือผู้เล่นทั่วไปในโลกแฟนตาซีนี้"
)

# ดึงรายชื่อตัวละครส่วนกลางทั้งหมด
cursor.execute("SELECT name FROM characters")
all_chars = [row[0] for row in cursor.fetchall()]

if "in_chat" not in st.session_state:
  st.session_state.in_chat = False

if (
    "current_char" not in st.session_state
    or st.session_state.current_char not in all_chars
):
  st.session_state.current_char = all_chars[0] if all_chars else None

# แผงควบคุมด้านข้าง (Sidebar)
with st.sidebar:
  st.markdown(f"👤 **ผู้ใช้งาน:** `{current_user}`")
  if is_current_admin:
    st.markdown("🛡️ **สถานะ:** `ผู้ดูแลระบบ (Admin)`")
  else:
    st.markdown("👤 **สถานะ:** `ผู้ใช้งานทั่วไป (User)`")

  st.divider()

  # 🎭 เมนูตั้งค่าบทบาทของตัวเอง (User Persona)
  with st.expander("🎭 ตั้งค่าบทบาท/ตัวตนของคุณ"):
    with st.form("user_persona_form"):
      new_persona = st.text_area(
          "บทบาทของคุณในการสวมบทบาท (Roleplay Persona):",
          value=current_user_persona,
          height=90,
          placeholder="เช่น ชื่อ เมอร์ลิน เป็นเด็กปี 1 บ้านกริฟฟินดอร์...",
      )
      save_persona = st.form_submit_button(
          "💾 บันทึกบทบาท", use_container_width=True
      )
      if save_persona:
        cursor.execute(
            "UPDATE users SET user_persona = ? WHERE username = ?",
            (new_persona, current_user),
        )
        conn.commit()
        st.success("บันทึกบทบาทของคุณสำเร็จ!")
        st.rerun()

  if st.button("🚪 ออกจากระบบ", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.is_admin = False
    st.session_state.in_chat = False
    st.rerun()

  st.divider()
  if st.button("🏠 กลับสู่หน้าแรก (เลือกตัวละคร)", use_container_width=True):
    st.session_state.in_chat = False
    st.session_state.current_char = None
    st.rerun()

  st.divider()
  chat_mode = st.radio(
      "เลือกสไตล์การคุย:", ["💬 แชทสั้นๆ เป็นธรรมชาติ", "📖 โหมดนิยายบรรยายยาว"]
  )

  st.divider()

  # 🛠️ เมนูจัดการระบบ (จำกัดสิทธิ์เฉพาะ Admin เท่านั้น)
  if is_current_admin:
    st.markdown("### 🛠️ จัดการระบบ (Admin Only)")
    sidebar_action = st.selectbox(
        "เลือกการจัดการ:",
        [
            "➕ สร้างตัวละครหลักใหม่",
            "✏️ แก้ไขข้อมูลตัวละครหลัก",
            "👥 จัดการตัวละครเสริม",
            "🎯 จัดการภารกิจ (Quest Log)",
            "🖼️ จัดการคลังรูปภาพ",
            "👥 จัดการผู้ใช้งานระบบ",
        ],
    )
  else:
    st.markdown("### 📌 เมนูผู้ใช้งาน")
    sidebar_action = "เลือกตัวละคร"

  if all_chars and sidebar_action not in [
      "➕ สร้างตัวละครหลักใหม่",
      "👥 จัดการผู้ใช้งานระบบ",
  ]:
    st.divider()
    selected_char = st.selectbox(
        "เลือกตัวละครหลัก:",
        all_chars,
        index=(
            all_chars.index(st.session_state.current_char)
            if st.session_state.current_char in all_chars
            else 0
        ),
    )
    if (
        not st.session_state.current_char
        or selected_char != st.session_state.current_char
    ):
      st.session_state.current_char = selected_char

  st.divider()

  # 1. สร้างตัวละครหลักใหม่ (Admin Only)
  if is_current_admin and sidebar_action == "➕ สร้างตัวละครหลักใหม่":
    st.markdown("### 📌 สร้างตัวละครหลัก")
    with st.form("create_char_form"):
      new_name = st.text_input(
          "ชื่อตัวละครหลัก:", placeholder="เช่น เดรโก มัลฟอย..."
      )
      new_prompt = st.text_area(
          "คาแรคเตอร์หลัก (Prompt):", placeholder="คุณคือ...", height=60
      )
      new_personality = st.text_area(
          "🧠 บุคลิก/นิสัย:", placeholder="หยิ่ง ทะนงตัว...", height=60
      )
      new_lore = st.text_area(
          "📖 เรื่องราวพื้นหลัง (Lore):",
          placeholder="สถานะเริ่มต้น ความสัมพันธ์...",
          height=70,
      )

      st.markdown("💬 **ข้อความแรก (กำหนด 3 รูปแบบ)**")
      msg_1 = st.text_area("#1 แบบที่ 1:", placeholder="สถานการณ์ที่ 1...", height=70)
      msg_2 = st.text_area("#2 แบบที่ 2:", placeholder="สถานการณ์ที่ 2...", height=70)
      msg_3 = st.text_area("#3 แบบที่ 3:", placeholder="สถานการณ์ที่ 3...", height=70)

      new_avatar = st.file_uploader(
          "รูปโปรไฟล์ตัวละครหลัก",
          type=["png", "jpg", "jpeg", "webp"],
          key="new_avatar_up",
      )

      submit_create = st.form_submit_button(
          "🚀 บันทึกสร้างตัวละคร", use_container_width=True
      )
      if submit_create:
        if new_name and new_prompt:
          cursor.execute(
              "SELECT name FROM characters WHERE name = ?", (new_name,)
          )
          if not cursor.fetchone():
            avatar_bytes = (
                new_avatar.getvalue() if new_avatar is not None else None
            )
            combined_msgs = json.dumps(
                [m.strip() for m in [msg_1, msg_2, msg_3] if m.strip()],
                ensure_ascii=False,
            )
            if not json.loads(combined_msgs):
              combined_msgs = json.dumps(
                  [f"สวัสดีครับ ฉันชื่อ {new_name}"], ensure_ascii=False
              )

            cursor.execute(
                """
                    INSERT INTO characters (name, prompt, personality, lore, first_message, avatar) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    new_name,
                    new_prompt,
                    new_personality,
                    new_lore,
                    combined_msgs,
                    avatar_bytes,
                ),
            )
            conn.commit()
            st.session_state.current_char = new_name
            st.session_state.in_chat = True
            st.success(f"สร้าง '{new_name}' สำเร็จ!")
            st.rerun()
          else:
            st.warning("ชื่อนี้มีอยู่แล้วในระบบ")
        else:
          st.warning("⚠️ กรุณากรอกชื่อและคาแรคเตอร์หลักให้ครบ")

  # 2. แก้ไขข้อมูลตัวละครหลัก (Admin Only)
  elif (
      is_current_admin
      and sidebar_action == "✏️ แก้ไขข้อมูลตัวละครหลัก"
      and st.session_state.current_char
  ):
    st.markdown(f"### ✏️ แก้ไข: {st.session_state.current_char}")
    cursor.execute(
        "SELECT prompt, personality, lore, first_message, avatar FROM characters WHERE name = ?",
        (st.session_state.current_char,),
    )
    curr_data = cursor.fetchone()
    if curr_data:
      c_prompt, c_pers, c_lore, c_fmsg_json, c_avatar = curr_data
      try:
        old_msgs = json.loads(c_fmsg_json)
      except Exception:
        old_msgs = [c_fmsg_json]

      om1 = old_msgs[0] if len(old_msgs) > 0 else ""
      om2 = old_msgs[1] if len(old_msgs) > 1 else ""
      om3 = old_msgs[2] if len(old_msgs) > 2 else ""

      with st.form("edit_char_form"):
        edit_prompt = st.text_area(
            "คาแรคเตอร์หลัก (Prompt):", value=c_prompt, height=60
        )
        edit_pers = st.text_area("🧠 บุคลิก/นิสัย:", value=c_pers, height=60)
        edit_lore = st.text_area("📖 เรื่องราวพื้นหลัง (Lore):", value=c_lore, height=70)

        st.markdown("💬 **ข้อความแรก (3 รูปแบบ)**")
        edit_m1 = st.text_area("ข้อความที่ 1:", value=om1, height=70)
        edit_m2 = st.text_area("ข้อความที่ 2:", value=om2, height=70)
        edit_m3 = st.text_area("ข้อความที่ 3:", value=om3, height=70)

        edit_avatar = st.file_uploader(
            "เปลี่ยนรูปโปรไฟล์ (ถ้ามี)",
            type=["png", "jpg", "jpeg", "webp"],
            key="edit_avatar_up",
        )

        submit_edit = st.form_submit_button(
            "💾 บันทึกการแก้ไข", use_container_width=True
        )
        if submit_edit:
          new_avatar_bytes = (
              edit_avatar.getvalue() if edit_avatar is not None else c_avatar
          )
          new_combined_msgs = json.dumps(
              [m.strip() for m in [edit_m1, edit_m2, edit_m3] if m.strip()],
              ensure_ascii=False,
          )

          cursor.execute(
              """
                UPDATE characters 
                SET prompt = ?, personality = ?, lore = ?, first_message = ?, avatar = ? 
                WHERE name = ?
            """,
              (
                  edit_prompt,
                  edit_pers,
                  edit_lore,
                  new_combined_msgs,
                  new_avatar_bytes,
                  st.session_state.current_char,
              ),
          )
          conn.commit()
          st.success("อัปเดตข้อมูลตัวละครสำเร็จ!")
          st.rerun()

      st.divider()
      if st.button(
          "🗑️ ลบตัวละครหลักนี้ทั้งหมด",
          use_container_width=True,
          key="del_main_char_btn",
      ):
        cursor.execute(
            "DELETE FROM characters WHERE name = ?",
            (st.session_state.current_char,),
        )
        cursor.execute(
            "DELETE FROM messages WHERE char_name = ?",
            (st.session_state.current_char,),
        )
        cursor.execute(
            "DELETE FROM character_photos WHERE char_name = ?",
            (st.session_state.current_char,),
        )
        cursor.execute(
            "DELETE FROM character_status WHERE char_name = ?",
            (st.session_state.current_char,),
        )
        cursor.execute(
            "DELETE FROM quests WHERE char_name = ?",
            (st.session_state.current_char,),
        )
        cursor.execute(
            "DELETE FROM supporting_characters WHERE char_name = ?",
            (st.session_state.current_char,),
        )
        conn.commit()
        st.session_state.in_chat = False
        cursor.execute("SELECT name FROM characters")
        remaining = [r[0] for r in cursor.fetchall()]
        st.session_state.current_char = remaining[0] if remaining else None
        st.rerun()

  # 3. จัดการตัวละครเสริม (Admin Only)
  elif (
      is_current_admin
      and sidebar_action == "👥 จัดการตัวละครเสริม"
      and st.session_state.current_char
  ):
    st.markdown(f"### 👥 ตัวละครเสริม: {st.session_state.current_char}")
    sub_action = st.radio("เลือกการทำงาน:", ["➕ เพิ่มตัวละครเสริม", "✏️ แก้ไข/ลบตัวละครเสริม"])

    if sub_action == "➕ เพิ่มตัวละครเสริม":
      with st.form("add_sub_char_form", clear_on_submit=True):
        sub_name = st.text_input(
            "ชื่อตัวละครเสริม:", placeholder="เช่น แครบบ์..."
        )
        sub_prompt = st.text_area(
            "คาแรคเตอร์ตัวละครเสริม:", placeholder="คุณคือลูกน้อง...", height=60
        )
        sub_personality = st.text_area(
            "🧠 บุคลิกตัวละครเสริม:", placeholder="ตัวใหญ่ ชอบกิน...", height=60
        )
        sub_lore = st.text_area(
            "📖 เรื่องราวพื้นหลังตัวละครเสริม:",
            placeholder="ประวัติความสัมพันธ์...",
            height=60,
        )
        sub_avatar = st.file_uploader(
            "รูปตัวละครเสริม",
            type=["png", "jpg", "jpeg", "webp"],
            key="sub_avatar_up",
        )

        submit_sub = st.form_submit_button(
            "➕ บันทึกตัวละครเสริม", use_container_width=True
        )
        if submit_sub and sub_name:
          sub_avatar_bytes = (
              sub_avatar.getvalue() if sub_avatar is not None else None
          )
          cursor.execute(
              """
                INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore, sub_avatar)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
              (
                  st.session_state.current_char,
                  sub_name,
                  sub_prompt,
                  sub_personality,
                  sub_lore,
                  sub_avatar_bytes,
              ),
          )
          conn.commit()
          st.success(f"เพิ่มตัวละครเสริม '{sub_name}' สำเร็จ!")
          st.rerun()
    else:
      cursor.execute(
          "SELECT id, sub_name FROM supporting_characters WHERE char_name = ?",
          (st.session_state.current_char,),
      )
      sub_list = cursor.fetchall()
      if sub_list:
        sub_dict = {s[1]: s[0] for s in sub_list}
        selected_sub_name = st.selectbox(
            "เลือกตัวละครเสริม:", list(sub_dict.keys())
        )
        selected_sub_id = sub_dict[selected_sub_name]

        cursor.execute(
            "SELECT sub_prompt, sub_personality, sub_lore, sub_avatar FROM supporting_characters WHERE id = ?",
            (selected_sub_id,),
        )
        sub_data = cursor.fetchone()
        if sub_data:
          sp_prompt, sp_pers, sp_lore, sp_av = sub_data
          with st.form(f"edit_sub_form_{selected_sub_id}"):
            e_sub_name = st.text_input("ชื่อตัวละครเสริม:", value=selected_sub_name)
            e_sub_prompt = st.text_area("คาแรคเตอร์:", value=sp_prompt, height=60)
            e_sub_pers = st.text_area("บุคลิก:", value=sp_pers, height=60)
            e_sub_lore = st.text_area("เรื่องราวพื้นหลัง:", value=sp_lore, height=60)
            e_sub_av = st.file_uploader(
                "เปลี่ยนรูปตัวละครเสริม (ถ้ามี)",
                type=["png", "jpg", "jpeg", "webp"],
                key=f"edit_sub_av_{selected_sub_id}",
            )

            col_sub_e1, col_sub_e2 = st.columns(2)
            with col_sub_e1:
              submit_edit_sub = st.form_submit_button(
                  "💾 บันทึก", use_container_width=True
              )
            with col_sub_e2:
              submit_del_sub = st.form_submit_button(
                  "🗑️ ลบ", use_container_width=True
              )

            if submit_edit_sub:
              final_sub_av = (
                  e_sub_av.getvalue() if e_sub_av is not None else sp_av
              )
              cursor.execute(
                  """
                    UPDATE supporting_characters 
                    SET sub_name = ?, sub_prompt = ?, sub_personality = ?, sub_lore = ?, sub_avatar = ? 
                    WHERE id = ?
                """,
                  (
                      e_sub_name,
                      e_sub_prompt,
                      e_sub_pers,
                      e_sub_lore,
                      final_sub_av,
                      selected_sub_id,
                  ),
              )
              conn.commit()
              st.success("อัปเดตตัวละครเสริมสำเร็จ!")
              st.rerun()

            if submit_del_sub:
              cursor.execute(
                  "DELETE FROM supporting_characters WHERE id = ?",
                  (selected_sub_id,),
              )
              conn.commit()
              st.success("ลบตัวละครเสริมสำเร็จ!")
              st.rerun()
      else:
        st.caption("ยังไม่มีตัวละครเสริมในเรื่องนี้")

  # 4. จัดการภารกิจ (Admin Only)
  elif (
      is_current_admin
      and sidebar_action == "🎯 จัดการภารกิจ (Quest Log)"
      and st.session_state.current_char
  ):
    st.markdown(f"### 🎯 จัดการภารกิจ: {st.session_state.current_char}")
    with st.form("add_quest_form_sidebar", clear_on_submit=True):
      new_quest_desc = st.text_input(
          "รายละเอียดภารกิจใหม่:", placeholder="เช่น ชวนไปกินกาแฟ..."
      )
      new_quest_pts = st.slider("คะแนนรางวัลที่จะได้รับ:", 5, 50, 15)
      submit_quest = st.form_submit_button(
          "➕ เพิ่มภารกิจ", use_container_width=True
      )
      if submit_quest and new_quest_desc:
        cursor.execute(
            "INSERT INTO quests (char_name, task_desc, reward_points) VALUES (?, ?, ?)",
            (st.session_state.current_char, new_quest_desc, new_quest_pts),
        )
        conn.commit()
        st.success("เพิ่มภารกิจสำเร็จ!")
        st.rerun()

    st.markdown("---")
    cursor.execute(
        "SELECT id, task_desc FROM quests WHERE char_name = ?",
        (st.session_state.current_char,),
    )
    q_list = cursor.fetchall()
    if q_list:
      for q_id, q_desc in q_list:
        q_col1, q_col2 = st.columns([4, 1])
        with q_col1:
          st.markdown(f"- **[#{q_id}]** {q_desc}")
        with q_col2:
          if st.button("🗑️", key=f"del_q_{q_id}"):
            cursor.execute("DELETE FROM quests WHERE id = ?", (q_id,))
            conn.commit()
            st.rerun()
    else:
      st.caption("ยังไม่มีภารกิจในระบบ")

  # 5. จัดการคลังรูปภาพ (Admin Only)
  elif (
      is_current_admin
      and sidebar_action == "🖼️ จัดการคลังรูปภาพ"
      and st.session_state.current_char
  ):
    st.markdown(f"### 🖼️ คลังรูป: {st.session_state.current_char}")
    gallery_key = f"gallery_upload_{st.session_state.current_char}"
    uploaded_gallery_photos = st.file_uploader(
        "อัปโหลดรูปภาพเข้าคลัง (ให้ตัวละครสุ่มส่ง)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=gallery_key,
    )

    if uploaded_gallery_photos:
      cursor.execute(
          "SELECT COUNT(*) FROM character_photos WHERE char_name = ?",
          (st.session_state.current_char,),
      )
      current_db_count = cursor.fetchone()[0]

      if len(uploaded_gallery_photos) != current_db_count:
        cursor.execute(
            "DELETE FROM character_photos WHERE char_name = ?",
            (st.session_state.current_char,),
        )
        for photo in uploaded_gallery_photos:
          cursor.execute(
              "INSERT INTO character_photos (char_name, photo) VALUES (?, ?)",
              (st.session_state.current_char, photo.getvalue()),
          )
        conn.commit()
        st.success("อัปเดตคลังรูปภาพสำเร็จ!")
        st.rerun()

    st.markdown("---")
    cursor.execute(
        "SELECT id, photo FROM character_photos WHERE char_name = ?",
        (st.session_state.current_char,),
    )
    photos_in_db = cursor.fetchall()
    if photos_in_db:
      p_cols = st.columns(3)
      for idx, (p_id, p_blob) in enumerate(photos_in_db):
        with p_cols[idx % 3]:
          img_item = Image.open(io.BytesIO(p_blob))
          st.image(img_item, use_container_width=True)
          if st.button(f"🗑️ ลบ #{p_id}", key=f"del_photo_{p_id}"):
            cursor.execute("DELETE FROM character_photos WHERE id = ?", (p_id,))
            conn.commit()
            st.rerun()
    else:
      st.caption("ยังไม่มีรูปภาพในคลัง")

  # 6. จัดการผู้ใช้งานระบบ (Admin Only)
  elif is_current_admin and sidebar_action == "👥 จัดการผู้ใช้งานระบบ":
    st.markdown("### 👥 รายชื่อผู้ใช้งานทั้งหมด")
    cursor.execute("SELECT username, is_admin FROM users")
    users_list = cursor.fetchall()

    if users_list:
      for u_name, u_admin in users_list:
        with st.container(border=True):
          role_label = "🛡️ Admin" if u_admin == 1 else "👤 User"
          st.markdown(f"**ยูสเซอร์:** `{u_name}` ({role_label})")

          with st.form(f"manage_user_{u_name}"):
            new_p = st.text_input(
                "เปลี่ยนรหัสผ่านใหม่ (ถ้าต้องการ):",
                type="password",
                key=f"np_{u_name}",
            )
            col_u1, col_u2 = st.columns(2)
            with col_u1:
              btn_save_p = st.form_submit_button(
                  "💾 บันทึกรหัส", use_container_width=True
              )
            with col_u2:
              btn_del_u = st.form_submit_button(
                  "🗑️ ลบบัญชี", use_container_width=True
              )

            if btn_save_p:
              if new_p:
                cursor.execute(
                    "UPDATE users SET password = ? WHERE username = ?",
                    (hash_password(new_p), u_name),
                )
                conn.commit()
                st.success(f"เปลี่ยนรหัสผ่านของ '{u_name}' สำเร็จ!")
                st.rerun()
              else:
                st.warning("กรุณากรอกรหัสผ่านใหม่")

            if btn_del_u:
              if u_name.lower() == "admin" and current_user.lower() == u_name:
                st.error("ไม่สามารถลบบัญชี Admin หลักของตัวเองได้")
              else:
                cursor.execute(
                    "DELETE FROM users WHERE username = ?", (u_name,)
                )
                cursor.execute(
                    "DELETE FROM messages WHERE username = ?", (u_name,)
                )
                cursor.execute(
                    "DELETE FROM character_status WHERE username = ?", (u_name,)
                )
                cursor.execute(
                    "DELETE FROM user_quests WHERE username = ?", (u_name,)
                )
                conn.commit()
                st.success(f"ลบบัญชี '{u_name}' สำเร็จ!")
                st.rerun()
    else:
      st.info("ยังไม่มีผู้ใช้งานอื่นในระบบ")

  if not all_chars and (
      not is_current_admin or sidebar_action != "➕ สร้างตัวละครหลักใหม่"
  ):
    st.info("ยังไม่มีตัวละครหลักในระบบ กรุณาให้ Admin สร้างตัวละครก่อนครับ")


# ==========================================
# 🏠 ส่วนแสดงผลหน้าแรก (Discovery / Home Hub)
# ==========================================
if not st.session_state.in_chat:
  if is_current_admin and sidebar_action == "👥 จัดการผู้ใช้งานระบบ":
    st.title("👥 ระบบจัดการผู้ใช้งานทั้งหมด")
    st.caption(
        "ดูรายชื่อ แก้ไขรหัสผ่าน หรือลบบัญชีผู้ใช้งานที่สมัครเข้ามาในระบบได้ที่นี่"
    )
    st.divider()

    cursor.execute("SELECT username, is_admin FROM users")
    all_users = cursor.fetchall()

    if all_users:
      for u_name, u_admin in all_users:
        with st.container(border=True):
          role_label = (
              "🛡️ ผู้ดูแลระบบ (Admin)"
              if u_admin == 1
              else "👤 ผู้ใช้งานทั่วไป (User)"
          )
          st.markdown(f"### ชื่อผู้ใช้: `{u_name}` — *({role_label})*")

          with st.form(f"main_manage_user_{u_name}"):
            m_new_pass = st.text_input(
                "ตั้งรหัสผ่านใหม่:", type="password", key=f"mp_{u_name}"
            )
            col_m1, col_m2 = st.columns(2)
            with col_m1:
              m_save = st.form_submit_button(
                  "💾 อัปเดตรหัสผ่าน", use_container_width=True
              )
            with col_m2:
              m_del = st.form_submit_button(
                  "🗑️ ลบบัญชีนี้", use_container_width=True
              )

            if m_save:
              if m_new_pass:
                cursor.execute(
                    "UPDATE users SET password = ? WHERE username = ?",
                    (hash_password(m_new_pass), u_name),
                )
                conn.commit()
                st.success(f"อัปเดตรหัสผ่านของ '{u_name}' สำเร็จ!")
                st.rerun()
              else:
                st.warning("กรุณากรอกรหัสผ่านใหม่")

            if m_del:
              if u_name.lower() == "admin":
                st.error("ไม่อนุญาตให้ลบบัญชี Admin หลัก")
              else:
                cursor.execute(
                    "DELETE FROM users WHERE username = ?", (u_name,)
                )
                cursor.execute(
                    "DELETE FROM messages WHERE username = ?", (u_name,)
                )
                cursor.execute(
                    "DELETE FROM character_status WHERE username = ?", (u_name,)
                )
                cursor.execute(
                    "DELETE FROM user_quests WHERE username = ?", (u_name,)
                )
                conn.commit()
                st.success(f"ลบบัญชี '{u_name}' สำเร็จ!")
                st.rerun()
    else:
      st.info("ยังไม่มีผู้ใช้งานในระบบ")

    st.stop()

  st.title("🔥 จักรวาลยอดนิยม & ตัวละครทั้งหมด")
  st.caption(
      "เลือกตัวละครที่คุณสนใจเพื่อดูข้อมูลพื้นหลังและเริ่มต้นบทสนทนาได้เลยครับ"
  )
  st.divider()

  if not all_chars:
    st.info(
        "📭 ยังไม่มีตัวละครในระบบ กรุณาเข้าสู่ระบบด้วยบัญชี Admin"
        " เพื่อสร้างตัวละครหลักครับ!"
    )
  else:
    cols = st.columns(3)
    for idx, c_name in enumerate(all_chars):
      cursor.execute(
          "SELECT personality, lore, avatar FROM characters WHERE name = ?",
          (c_name,),
      )
      c_data = cursor.fetchone()
      c_pers = c_data[0] if c_data and c_data[0] else "ไม่มีข้อมูลบุคลิก"
      c_lore = c_data[1] if c_data and c_data[1] else "ไม่มีข้อมูลเรื่องราว"
      c_avatar_blob = c_data[2] if c_data else None

      col_target = cols[idx % 3]
      with col_target:
        with st.container(border=True):
          if c_avatar_blob:
            img = Image.open(io.BytesIO(c_avatar_blob))
            st.image(img, use_container_width=True)
          else:
            st.image(
                "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=500",
                use_container_width=True,
            )

          st.markdown(f"### 🌟 {c_name}")
          st.write(
              f"**บุคลิก:** {c_pers[:60]}..."
              if len(c_pers) > 60
              else f"**บุคลิก:** {c_pers}"
          )

          if st.button(
              f"✨ สำรวจโลกของ {c_name}",
              key=f"btn_explore_{c_name}",
              use_container_width=True,
          ):
            st.session_state.selected_preview = c_name
            st.rerun()

    if (
        "selected_preview" in st.session_state
        and st.session_state.selected_preview
    ):
      prev_name = st.session_state.selected_preview
      cursor.execute(
          "SELECT prompt, personality, lore, first_message, avatar FROM characters WHERE name = ?",
          (prev_name,),
      )
      p_data = cursor.fetchone()

      if p_data:
        st.divider()
        st.markdown(f"## 📜 ข้อมูลรายละเอียด: `{prev_name}`")
        p_col1, p_col2 = st.columns([1, 2])
        with p_col1:
          if p_data[4]:
            st.image(
                Image.open(io.BytesIO(p_data[4])), use_container_width=True
            )
          else:
            st.image(
                "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=500",
                use_container_width=True,
            )
        with p_col2:
          st.markdown(f"**🧠 คาแรคเตอร์หลัก:** {p_data[0]}")
          st.markdown(f"**✨ บุคลิก/นิสัย:** {p_data[1]}")
          st.markdown(f"**📖 เรื่องราวพื้นหลัง (Lore):** {p_data[2]}")

          cursor.execute(
              "SELECT sub_name, sub_personality FROM supporting_characters WHERE char_name = ?",
              (prev_name,),
          )
          sub_chars_preview = cursor.fetchall()
          if sub_chars_preview:
            sub_names_str = ", ".join([f"{s[0]}" for s in sub_chars_preview])
            st.markdown(f"**👥 ตัวละครเสริมในเรื่อง:** {sub_names_str}")
          else:
            st.markdown("**👥 ตัวละครเสริมในเรื่อง:** ไม่มี")

          try:
            msgs_preview = json.loads(p_data[3])
            preview_str = " / ".join(
                [f"#{i+1} ({m[:30]}...)" for i, m in enumerate(msgs_preview)]
            )
          except Exception:
            preview_str = "มีข้อความทักทาย"

          st.markdown(f"**💬 รูปแบบข้อความแรก:** {preview_str}")

          if st.button(
              f"🚀 เริ่มต้นบทสนทนากับ {prev_name}",
              type="primary",
              use_container_width=True,
          ):
            st.session_state.current_char = prev_name
            st.session_state.in_chat = True
            del st.session_state.selected_preview
            st.rerun()

  st.stop()


# ==========================================
# 💬 ส่วนห้องแชท (Chat Room) - แยกตามยูสเซอร์
# ==========================================
if st.session_state.in_chat and st.session_state.current_char:
  cursor.execute(
      """
      SELECT prompt, personality, lore, first_message, avatar 
      FROM characters WHERE name = ?
  """,
      (st.session_state.current_char,),
  )
  char_data = cursor.fetchone()

  base_prompt = char_data[0] if char_data and char_data[0] else ""
  char_personality = char_data[1] if char_data and char_data[1] else "ไม่มีข้อมูล"
  char_lore = char_data[2] if char_data and char_data[2] else "ไม่มีข้อมูล"
  char_first_msg_raw = char_data[3] if char_data and char_data[3] else "[]"
  char_avatar_blob = char_data[4] if char_data else None

  char_avatar_img = None
  if char_avatar_blob:
    char_avatar_img = Image.open(io.BytesIO(char_avatar_blob))

  cursor.execute(
      "SELECT sub_name, sub_prompt, sub_personality, sub_lore FROM supporting_characters WHERE char_name = ?",
      (st.session_state.current_char,),
  )
  sub_rows = cursor.fetchall()
  supporting_text = ""
  if sub_rows:
    for s_name, s_prompt, s_pers, s_lore in sub_rows:
      supporting_text += f"\n- ตัวละครเสริม [{s_name}]: คาแรคเตอร์: {s_prompt} | บุคลิก: {s_pers} | เรื่องราว: {s_lore}"
  else:
    supporting_text = "ไม่มีตัวละครเสริมพิเศษ"

  cursor.execute(
      "SELECT affection_score, relationship_level FROM character_status WHERE username = ? AND char_name = ?",
      (current_user, st.session_state.current_char),
  )
  status_row = cursor.fetchone()
  if not status_row:
    cursor.execute(
        "INSERT INTO character_status (username, char_name, affection_score, relationship_level) VALUES (?, ?, 0, 'คนแปลกหน้า')",
        (current_user, st.session_state.current_char),
    )
    conn.commit()
    current_affection = 0
    current_rel_level = "คนแปลกหน้า"
  else:
    current_affection = status_row[0]
    current_rel_level = status_row[1]

  full_system_prompt = f"""
    {base_prompt}

    [ข้อมูลผู้สนทนา / บทบาทของคุณ (User Persona)]:
    {current_user_persona}

    [บุคลิกและนิสัยของตัวละครหลัก]:
    {char_personality}

    [เรื่องราวพื้นหลัง (Background/Lore)]:
    {char_lore}

    [ตัวละครเสริมรอบตัว]:
    {supporting_text}

    [สถานะความสัมพันธ์ปัจจุบันกับผู้ใช้ ({current_user})]: ระดับ "{current_rel_level}" (คะแนนความชอบ: {current_affection}/100)
    
    *กฎการประเมินคะแนนความชอบ (score_change)*:
    - ถ้าผู้ใช้คุยดี เป็นมิตร ทำตามภารกิจ หรือพูดจาถูกใจ: ให้คะแนนบวกเพิ่ม (2 ถึง 10)
    - ถ้าผู้ใช้คุยเฉยๆ ไม่ค่อยน่าสนใจ หรือขัดใจเล็กน้อย: ให้คะแนนติดลบเล็กน้อย (-1 ถึง -3)
    - ถ้าผู้ใช้พูดจาด่าทอ ใช้คำหยาบคาย รังควาน หรือสร้างความไม่พอใจอย่างมาก: ให้คะแนนติดลบเยอะ (-5 ถึง -15) และตัวละครจะต้องแสดงอาการโกรธหรือไม่พอใจตามคาแรคเตอร์ด้วย
    - คะแนนรวมสามารถลดต่ำกว่า 0 ได้ (สูงสุดไม่เกิน 100)
    """

  if "นิยาย" in chat_mode:
    roleplay_instruction = (
        f"{full_system_prompt}\n\n[กฎการตอบ]:\n"
        "1. เขียนตอบสไตล์นิยายบรรยาย มีท่าทาง สีหน้า ความรู้สึก (ใช้เครื่องหมาย *"
        " ครอบการกระทำ)\n"
        "2. สวมบทบาท 100% ตามระดับความสัมพันธ์ปัจจุบัน ห้ามหลุดคาแรคเตอร์\n"
        "3. ในตอนท้ายของการตอบทุกครั้ง ให้แนบข้อมูลประเมินผลเป็น JSON บรรทัดสุดท้ายในรูปแบบนี้เป๊ะๆ:\n"
        '{"score_change": [ตัวเลขคะแนนที่เปลี่ยนแปลง เช่น บวก 5 หรือลบ 3 หรือลบ 10], "new_level": "[ระดับความสัมพันธ์ล่าสุด]", "quest_update": [หมายเลขไอดีภารกิจที่ทำสำเร็จ หรือ null]}'
    )
    temp_val = 1.1
  else:
    roleplay_instruction = (
        f"{full_system_prompt}\n\n[กฎการตอบ]:\n"
        "1. พูดจาภาษาคนธรรมดา เป็นธรรมชาติเหมือนแชทไลน์/ไอจี ตามระดับความสัมพันธ์ปัจจุบัน\n"
        "2. สวมบทบาท 100% ห้ามหลุดคาแรคเตอร์\n"
        "3. ในตอนท้ายของการตอบทุกครั้ง ให้แนบข้อมูลประเมินผลเป็น JSON บรรทัดสุดท้ายในรูปแบบนี้เป๊ะๆ:\n"
        '{"score_change": [ตัวเลขคะแนนที่เปลี่ยนแปลง เช่น บวก 5 หรือลบ 3 หรือลบ 10], "new_level": "[ระดับความสัมพันธ์ล่าสุด]", "quest_update": [หมายเลขไอดีภารกิจที่ทำสำเร็จ หรือ null]}'
    )
    temp_val = 0.9


  def get_random_first_msg(raw_json, char_name):
    try:
      msgs = json.loads(raw_json)
      if msgs and isinstance(msgs, list):
        return random.choice(msgs)
    except Exception:
      pass
    return f"สวัสดีครับ ฉันชื่อ {char_name}"


  cursor.execute(
      "SELECT COUNT(*) FROM messages WHERE username = ? AND char_name = ?",
      (current_user, st.session_state.current_char),
  )
  if cursor.fetchone()[0] == 0:
    init_msg = get_random_first_msg(
        char_first_msg_raw, st.session_state.current_char
    )
    cursor.execute(
        "INSERT INTO messages (username, char_name, role, content, image_blob)"
        " VALUES (?, ?, ?, ?, ?)",
        (current_user, st.session_state.current_char, "assistant", init_msg, None),
    )
    conn.commit()

  cursor.execute(
      "SELECT role, content, image_blob FROM messages WHERE username = ? AND char_name = ?",
      (current_user, st.session_state.current_char),
  )
  current_messages = []
  for row in cursor.fetchall():
    img_obj = None
    if row[2]:
      img_obj = Image.open(io.BytesIO(row[2]))
    current_messages.append(
        {"role": row[0], "content": row[1], "image": img_obj}
    )

  col_av, col_title, col_reset = st.columns([1, 6, 2])
  with col_av:
    if char_avatar_img:
      st.image(char_avatar_img, width=60)
    else:
      st.image("https://api.iconify.design/lucide:user-round.svg", width=50)
  with col_title:
    st.markdown(
        f"### แชทกับ: `{st.session_state.current_char}` (ผู้ใช้:"
        f" `{current_user}`)"
    )
  with col_reset:
    if st.button("🔄 รีเซ็ตแชท", use_container_width=True):
      cursor.execute(
          "DELETE FROM messages WHERE username = ? AND char_name = ?",
          (current_user, st.session_state.current_char),
      )
      cursor.execute(
          """
            UPDATE character_status 
            SET affection_score = 0, relationship_level = 'คนแปลกหน้า' 
            WHERE username = ? AND char_name = ?
        """,
          (current_user, st.session_state.current_char),
      )
      new_random_msg = get_random_first_msg(
          char_first_msg_raw, st.session_state.current_char
      )
      cursor.execute(
          "INSERT INTO messages (username, char_name, role, content, image_blob)"
          " VALUES (?, ?, ?, ?, ?)",
          (
              current_user,
              st.session_state.current_char,
              "assistant",
              new_random_msg,
              None,
          ),
      )
      conn.commit()
      st.success("รีเซ็ตบทสนทนาส่วนตัวสำเร็จ!")
      st.rerun()

  st.divider()

  for message in current_messages:
    if message["role"] == "user":
      with st.chat_message("user", avatar="👤"):
        st.markdown(message["content"])
    else:
      avatar_icon = char_avatar_img if char_avatar_img else "✨"
      with st.chat_message("assistant", avatar=avatar_icon):
        col_badge, col_pop = st.columns([4, 1.2])
        with col_badge:
          st.markdown(
              f'<div class="affection-badge">💖 {current_rel_level} | คะแนน: {current_affection}/100</div>',
              unsafe_allow_html=True,
          )
        with col_pop:
          with st.popover("🎯 ภารกิจ", use_container_width=True):
            st.markdown("#### 🎯 รายการภารกิจทั้งหมด")
            cursor.execute(
                "SELECT id, task_desc, reward_points FROM quests WHERE char_name = ?",
                (st.session_state.current_char,),
            )
            quests = cursor.fetchall()
            if quests:
              for q_id, desc, pts in quests:
                cursor.execute(
                    "SELECT is_completed FROM user_quests WHERE username = ? AND quest_id = ?",
                    (current_user, q_id),
                )
                uq = cursor.fetchone()
                is_comp = uq[0] if uq else 0

                if is_comp:
                  st.markdown(
                      f"- ✅ **[ภารกิจที่ {q_id}]** ~~{desc}~~ — *สำเร็จแล้ว* (+{pts}"
                      " แต้ม)"
                  )
                else:
                  st.markdown(
                      f"- ⏳ **[ภารกิจที่ {q_id}]** {desc} — *ยังไม่สำเร็จ*"
                      f" (รางวัล: {pts} แต้ม)"
                  )
            else:
              st.caption("ยังไม่มีภารกิจในระบบ")

        st.markdown(message["content"])
        if message["image"]:
          st.image(message["image"], width=280)

  if user_input := st.chat_input(
      f"ส่งข้อความหา {st.session_state.current_char}..."
  ):
    cursor.execute(
        "INSERT INTO messages (username, char_name, role, content, image_blob)"
        " VALUES (?, ?, ?, ?, ?)",
        (current_user, st.session_state.current_char, "user", user_input, None),
    )
    conn.commit()

    with st.chat_message("user", avatar="👤"):
      st.markdown(user_input)

    avatar_icon = char_avatar_img if char_avatar_img else "✨"
    with st.chat_message("assistant", avatar=avatar_icon):
      message_placeholder = st.empty()
      message_placeholder.markdown("กำลังพิมพ์...")

      bot_response = None
      attached_photo_bytes = None
      max_retries = 3

      for attempt in range(max_retries):
        try:
          formatted_history = []
          for m in current_messages:
            role_name = "user" if m["role"] == "user" else "model"
            formatted_history.append(
                {"role": role_name, "parts": [{"text": m["content"]}]}
            )

          chat = client.chats.create(
              model=model_name,
              history=formatted_history if formatted_history else None,
              config={
                  "system_instruction": roleplay_instruction,
                  "temperature": temp_val,
              },
          )

          response = chat.send_message(user_input)
          raw_text = response.text

          try:
            if "{" in raw_text and "}" in raw_text:
              parts = raw_text.rsplit("{", 1)
              bot_response = parts[0].strip()
              json_str = "{" + parts[1]
              eval_data = json.loads(json_str)
            else:
              bot_response = raw_text
              eval_data = {
                  "score_change": 0,
                  "new_level": current_rel_level,
                  "quest_update": None,
              }
          except Exception:
            bot_response = raw_text
            eval_data = {
                "score_change": 0,
                "new_level": current_rel_level,
                "quest_update": None,
            }

          score_change = eval_data.get("score_change", 0)
          new_lvl = eval_data.get("new_level", current_rel_level)
          completed_q_id = eval_data.get("quest_update", None)

          quest_bonus = 0
          if completed_q_id:
            cursor.execute(
                "SELECT is_completed FROM user_quests WHERE username = ? AND quest_id = ?",
                (current_user, completed_q_id),
            )
            uq_row = cursor.fetchone()
            already_done = uq_row[0] if uq_row else 0

            if not already_done:
              cursor.execute(
                  "SELECT reward_points FROM quests WHERE id = ?",
                  (completed_q_id,),
              )
              q_info = cursor.fetchone()
              if q_info:
                quest_bonus = q_info[0]
                cursor.execute(
                    """
                    INSERT INTO user_quests (username, quest_id, is_completed) 
                    VALUES (?, ?, 1) 
                    ON CONFLICT(username, quest_id) DO UPDATE SET is_completed = 1
                """,
                    (current_user, completed_q_id),
                )

          updated_score = max(
              0, min(100, current_affection + score_change + quest_bonus)
          )

          cursor.execute(
              """
              UPDATE character_status 
              SET affection_score = ?, relationship_level = ? 
              WHERE username = ? AND char_name = ?
          """,
              (
                  updated_score,
                  new_lvl,
                  current_user,
                  st.session_state.current_char,
              ),
          )
          conn.commit()

          cursor.execute(
              "SELECT photo FROM character_photos WHERE char_name = ?",
              (st.session_state.current_char,),
          )
          photos = cursor.fetchall()
          if photos and random.random() < 0.30:
            selected_photo_row = random.choice(photos)
            attached_photo_bytes = selected_photo_row[0]

          break

        except Exception as e:
          error_msg = str(e)
          if (
              ("503" in error_msg or "UNAVAILABLE" in error_msg)
              and attempt < max_retries - 1
          ):
            message_placeholder.markdown(
                f"⚠️ กำลังเชื่อมต่อใหม่ครั้งที่ {attempt + 2}..."
            )
            time.sleep(1.5)
          else:
            if attempt == max_retries - 1 or not (
                "503" in error_msg or "UNAVAILABLE" in error_msg
            ):
              bot_response = "ขออภัยครับ เกิดข้อผิดพลาดในการประมวลผล"
              break

      if bot_response:
        message_placeholder.markdown(bot_response)
        display_img = None
        if attached_photo_bytes:
          display_img = Image.open(io.BytesIO(attached_photo_bytes))
          st.image(display_img, width=280)

        cursor.execute(
            "INSERT INTO messages (username, char_name, role, content, image_blob)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                current_user,
                st.session_state.current_char,
                "assistant",
                bot_response,
                attached_photo_bytes,
            ),
        )
        conn.commit()
        st.rerun()
