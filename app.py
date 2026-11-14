from google import genai
import streamlit as st
import sqlite3
import time
from PIL import Image
import io
import random
import json
import hashlib
import urllib.request
import urllib.error
import re

st.set_page_config(
    page_title="AI Roleplay - Novel Universe Hub",
    page_icon="🌌",
    layout="wide",
)

# 🎨 ดีไซน์ CSS พรีเมียม
st.markdown(
    """
    <style>
    .stChatMessage {
        border-radius: 20px !important;
        padding: 18px 22px !important;
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

    /* 🖋️ บังคับข้อความบรรยายให้เป็นสีเทาอ่อน และเป็นตัวตรงปกติ ไม่อียง */
    .stChatMessage p em, .stChatMessage em {
        color: #94a3b8 !important;
        font-style: normal !important;
    }
    
    .stChatMessage p {
        line-height: 1.7 !important;
        margin-bottom: 12px !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# 🗄️ ฟังก์ชันฐานข้อมูล SQLite พร้อมตารางรองรับครบทุกฟีเจอร์
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
  if "is_admin" not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
  if "user_name" not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN user_name TEXT DEFAULT ''")
  if "user_persona" not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN user_persona TEXT DEFAULT ''")
  if "pronoun_speak" not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN pronoun_speak TEXT DEFAULT ''")
  if "pronoun_desc" not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN pronoun_desc TEXT DEFAULT ''")
  if "call_speak" not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN call_speak TEXT DEFAULT ''")
  if "call_desc" not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN call_desc TEXT DEFAULT ''")

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
    cursor.execute(
        "ALTER TABLE character_photos ADD COLUMN photo_hash TEXT DEFAULT ''"
    )

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
except Exception:
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
      (0, "คนแปลกหน้า"),
      (100, "คนรู้จัก"),
      (200, "เพื่อนใหม่"),
      (300, "เพื่อนสนิท"),
      (400, "คนรู้ใจ"),
      (500, "คู่ชีวิต / คนสำคัญ"),
      (600, "พาร์ทเนอร์รู้ใจ"),
      (700, "โซลเมท"),
      (800, "ความผูกพันลึกซึ้ง"),
      (900, "รักแท้ไร้ขีดจำกัด"),
  ]
  idx = min(score // 100, len(levels) - 1)
  return levels[idx][1]


# ⏳ ฟังก์ชันจำลองการรอพร้อมแสดงผล Progress Bar และเวลาถอยหลังแบบละเอียด
def run_with_timer(title_text, total_seconds=25):
  bar = st.progress(0, text=f"{title_text} (กำลังเริ่มต้นกระบวนการ...)")
  for i in range(total_seconds):
    time.sleep(1.0)
    percent = int(((i + 1) / total_seconds) * 100)
    remaining = total_seconds - (i + 1)
    bar.progress(
        percent,
        text=(
            f"{title_text} — คาดว่าจะเสร็จในอีกประมาณ {remaining}"
            " วินาที (กำลังประมวลผลข้อมูลเชิงลึกและสร้างสรรค์องค์ประกอบ)..."
        ),
    )
  bar.empty()


if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
if "username" not in st.session_state:
  st.session_state.username = ""
if "is_admin" not in st.session_state:
  st.session_state.is_admin = False

# ==========================================
# 🔐 หน้าจอเข้าสู่ระบบ / สมัครสมาชิก
# ==========================================
if not st.session_state.logged_in:
  st.title("🌌 AI Roleplay - Novel Universe Hub")
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
                """
                    INSERT INTO users (username, password, is_admin, user_name, user_persona, pronoun_speak, pronoun_desc, call_speak, call_desc) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r_user,
                    hash_password(r_pass),
                    assigned_admin,
                    r_user,
                    "เป็นนักเรียนฮอกวอตส์รุ่นเดียวกับเดรโก",
                    "ผม / ฉัน",
                    "เธอ / เขา",
                    "คุณ",
                    "เขา",
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

cursor.execute(
    """
    SELECT user_name, user_persona, pronoun_speak, pronoun_desc, call_speak, call_desc 
    FROM users WHERE username = ?
""",
    (current_user,),
)
p_row = cursor.fetchone()
if p_row:
  u_name, u_persona, u_pspeak, u_pdesc, u_cspeak, u_cdesc = p_row
else:
  u_name, u_persona, u_pspeak, u_pdesc, u_cspeak, u_cdesc = (
      current_user,
      "",
      "",
      "",
      "",
      "",
  )

cursor.execute("SELECT name FROM characters")
all_chars = [row[0] for row in cursor.fetchall()]

if "in_chat" not in st.session_state:
  st.session_state.in_chat = False

if (
    "current_char" not in st.session_state
    or st.session_state.current_char not in all_chars
):
  st.session_state.current_char = all_chars[0] if all_chars else None

with st.sidebar:
  st.markdown(f"👤 **ผู้ใช้งาน:** `{current_user}`")
  if is_current_admin:
    st.markdown("🛡️ **สถานะ:** `ผู้ดูแลระบบ (Admin)`")
  else:
    st.markdown("👤 **สถานะ:** `ผู้ใช้งานทั่วไป (User)`")

  st.divider()

  with st.expander("⚙️ ตั้งค่าบทบาทตัวตนของคุณ"):
    if st.session_state.current_char:
      if st.button("✨ ให้ AI สร้างบทบาทให้เข้ากับเรื่องนี้", use_container_width=True):
        run_with_timer("AI กำลังวิเคราะห์และสร้างบทบาทตัวผู้เล่น", 3)
        try:
          cursor.execute(
              "SELECT prompt, personality, lore FROM characters WHERE name = ?",
              (st.session_state.current_char,),
          )
          c_info = cursor.fetchone()
          c_p, c_pers, c_l = c_info if c_info else ("", "", "")

          ai_prompt = (
              f"คุณคือผู้ช่วยสร้างบทบาทผู้เล่น (User Persona) สำหรับนำไปสวมบทบาทร่วมกับตัวละครหลักชื่อ '{st.session_state.current_char}'\n"
              f"ข้อมูลตัวละครหลัก: {c_p} | นิสัย: {c_pers} | เรื่องราว: {c_l}\n\n"
              f"กรุณาสร้างข้อมูลผู้เล่นในรูปแบบ JSON 1 บรรทัด (ห้ามมีข้อความอื่นปน) ดังนี้:\n"
              '{"user_name": "ชื่อตัวละครผู้เล่น", "user_persona": "ประวัติหรือความสัมพันธ์กับตัวละครหลักสั้นๆ", "pronoun_speak": "สรรพนามพูด เช่น ผม/ฉัน", "pronoun_desc": "สรรพนามบรรยาย เช่น เขา/เธอ", "call_speak": "สรรพนามเรียกตัวละคร เช่น คุณ/เธอ", "call_desc": "สรรพนามเรียกตอนบรรยาย เช่น ชายหนุ่ม"}'
          )
          ai_res = client.models.generate_content(
              model=model_name, contents=ai_prompt
          )
          res_text = ai_res.text.strip()
          if "{" in res_text and "}" in res_text:
            json_str = res_text[res_text.find("{") : res_text.rfind("}") + 1]
            p_data = json.loads(json_str)
            u_name = p_data.get("user_name", u_name)
            u_persona = p_data.get("user_persona", u_persona)
            u_pspeak = p_data.get("pronoun_speak", u_pspeak)
            u_pdesc = p_data.get("pronoun_desc", u_pdesc)
            u_cspeak = p_data.get("call_speak", u_cspeak)
            u_cdesc = p_data.get("call_desc", u_cdesc)

            cursor.execute(
                """
                    UPDATE users 
                    SET user_name = ?, user_persona = ?, pronoun_speak = ?, pronoun_desc = ?, call_speak = ?, call_desc = ? 
                    WHERE username = ?
                """,
                (
                    u_name,
                    u_persona,
                    u_pspeak,
                    u_pdesc,
                    u_cspeak,
                    u_cdesc,
                    current_user,
                ),
            )
            conn.commit()
            st.success("AI สร้างบทบาทให้เรียบร้อยแล้ว!")
            st.rerun()
        except Exception as e:
          st.error(f"เกิดข้อผิดพลาด: {e}")

    with st.form("user_persona_detailed_form"):
      edit_uname = st.text_input("ชื่อของคุณ:", value=u_name)
      edit_persona = st.text_area("บทบาทของคุณ:", value=u_persona, height=80)

      st.markdown("---")
      col_p1, col_p2 = st.columns(2)
      with col_p1:
        edit_pspeak = st.text_input("สรรพนามตอนพูด:", value=u_pspeak)
      with col_p2:
        edit_pdesc = st.text_input("สรรพนามตอนบรรยาย:", value=u_pdesc)

      col_c1, col_c2 = st.columns(2)
      with col_c1:
        edit_cspeak = st.text_input("ตัวละครเรียก (ตอนพูด):", value=u_cspeak)
      with col_c2:
        edit_cdesc = st.text_input("ตัวละครเรียก (ตอนบรรยาย):", value=u_cdesc)

      save_persona_btn = st.form_submit_button(
          "💾 บันทึกบทบาท", use_container_width=True
      )
      if save_persona_btn:
        cursor.execute(
            """
                UPDATE users 
                SET user_name = ?, user_persona = ?, pronoun_speak = ?, pronoun_desc = ?, call_speak = ?, call_desc = ? 
                WHERE username = ?
            """,
            (
                edit_uname,
                edit_persona,
                edit_pspeak,
                edit_pdesc,
                edit_cspeak,
                edit_cdesc,
                current_user,
            ),
        )
        conn.commit()
        st.success("บันทึกเรียบร้อย!")
        st.rerun()

  if st.button("🚪 ออกจากระบบ", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.is_admin = False
    st.session_state.in_chat = False
    st.rerun()

  st.divider()
  if st.button("🏠 กลับสู่หน้าแรก", use_container_width=True):
    st.session_state.in_chat = False
    st.session_state.current_char = None
    st.rerun()

  st.divider()

  if is_current_admin:
    st.markdown("### 🛠️ จัดการระบบ (Admin Only)")
    sidebar_action = st.selectbox(
        "เลือกการจัดการ:",
        [
            "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติแบบพรีเมียมขั้นสูง)",
            "🌐 นำเข้าตัวละครจากข้อมูลเว็บ (Smart Parser)",
            "➕ สร้างตัวละครหลักใหม่ (Manual)",
            "✏️ แก้ไขข้อมูลตัวละครหลัก",
            "🗑️ ลบตัวละครหลัก",
            "👥 จัดการตัวละครเสริม",
            "🎯 จัดการภารกิจ (Quest Log)",
            "🖼️ จัดการคลังรูปภาพ",
            "👥 จัดการผู้ใช้งานระบบ",
        ],
    )
  else:
    sidebar_action = "เลือกตัวละคร"

  if all_chars and sidebar_action not in [
      "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติแบบพรีเมียมขั้นสูง)",
      "🌐 นำเข้าตัวละครจากข้อมูลเว็บ (Smart Parser)",
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
        key="global_char_selector",
    )
    if (
        not st.session_state.current_char
        or selected_char != st.session_state.current_char
    ):
      st.session_state.current_char = selected_char
      st.rerun()

  st.divider()
  active_char = st.session_state.current_char

  # ✨ ระบบสร้างตัวละครหลักด้วย AI อัตโนมัติแบบพรีเมียมขั้นสูง (ป้องกันตัวซ้ำซาก, 5 ตัวเสริม, 5 ภารกิจ, รูปภาพ)
  if (
      is_current_admin
      and sidebar_action == "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติแบบพรีเมียมขั้นสูง)"
  ):
    st.markdown("### ✨ สร้างตัวละครหลัก (พรีเมียมขั้นสูง)")
    st.caption(
        "ระบบจะตรวจสอบตัวละครเดิมในระบบเพื่อป้องกันความซ้ำซาก"
        " สร้างเนื้อหาเชิงลึก ตัวละครเสริม 5 ตัว ภารกิจ 5 เควสต์"
        " และสังเคราะห์คลังภาพพรีเมียมให้อัตโนมัติ"
    )

    with st.form("ai_gen_char_form_advanced"):
      ai_target_name = st.text_input(
          "ชื่อดารา หรือ ตัวละครหลัก:",
          placeholder="เช่น เซอร์เวรัส สเนป, แฮร์รี่ พอตเตอร์...",
      )
      ai_submit_btn = st.form_submit_button(
          "🚀 เริ่มต้นสร้างระดับพรีเมียม (ใช้เวลา ~40 วินาที)",
          use_container_width=True,
      )

      if ai_submit_btn and ai_target_name:
        run_with_timer(
            f"AI กำลังประมวลผลคาแรคเตอร์เชิงลึกของ '{ai_target_name}'", 35
        )
        try:
          existing_chars_str = ", ".join(all_chars) if all_chars else "ไม่มี"
          prompt_gen = (
              f"คุณคือผู้เชี่ยวชาญการสร้างข้อมูลจักรวาลและตัวละครสำหรับ AI Roleplay ระดับโลก\n"
              f"ตัวละครที่มีอยู่แล้วในระบบ ห้ามสร้างให้ซ้ำซากหรือมีบุคลิกทับซ้อนกัน: [{existing_chars_str}]\n"
              f"เป้าหมายในการสร้างตัวละครใหม่: '{ai_target_name}'\n\n"
              f"เงื่อนไขบังคับเข้มงวด:\n"
              f"1. **ความสมจริงและลึกซึ้ง**: เขียนคาแรคเตอร์ (Prompt), บุคลิก (Personality), และเรื่องราว (Lore) ให้ละเอียด สละสลวย สมจริง เหมือนนิยายขายดี ห้ามส่งแบบส่งๆ เด็ดขาด\n"
              f"2. **ควบคุมความซับซ้อน**: โครงสร้างต้องชัดเจน เข้าใจง่าย ไม่ยุ่งเหยิงหรือซับซ้อนเกินไปจน AI สับสน\n"
              f"3. **องค์ประกอบครบถ้วน**: ต้องมีตัวละครเสริมอย่างน้อย 5 ตัว และภารกิจเริ่มต้นอย่างน้อย 5 ภารกิจ\n\n"
              f"กรุณาส่งออกเป็นรูปแบบ JSON 1 บรรทัด (ห้ามมี markdown หรือข้อความอื่นปนเด็ดขาด) โครงสร้างดังนี้:\n"
              "{\n"
              f'  "name": "{ai_target_name}",\n'
              '  "prompt": "คาแรคเตอร์หลักและบทบาทเชิงลึกที่ไม่ซ้ำใคร",\n'
              '  "personality": "บุคลิกและนิสัยใจคออย่างประณีตชัดเจน",\n'
              '  "lore": "เรื่องราวพื้นหลังและความสัมพันธ์ที่มีมิติ",\n'
              '  "first_messages": ["ข้อความเปิดตัวที่ 1", "ข้อความเปิดตัวที่ 2", "ข้อความเปิดตัวที่ 3"],\n'
              '  "supporting_chars": [\n'
              '    {"name": "ชื่อตัวเสริม 1", "prompt": "บทบาท", "personality": "นิสัย", "lore": "ความสัมพันธ์"},\n'
              '    {"name": "ชื่อตัวเสริม 2", "prompt": "บทบาท", "personality": "นิสัย", "lore": "ความสัมพันธ์"},\n'
              '    {"name": "ชื่อตัวเสริม 3", "prompt": "บทบาท", "personality": "นิสัย", "lore": "ความสัมพันธ์"},\n'
              '    {"name": "ชื่อตัวเสริม 4", "prompt": "บทบาท", "personality": "นิสัย", "lore": "ความสัมพันธ์"},\n'
              '    {"name": "ชื่อตัวเสริม 5", "prompt": "บทบาท", "personality": "นิสัย", "lore": "ความสัมพันธ์"}\n'
              "  ],\n"
              '  "quests": [\n'
              '    {"desc": "รายละเอียดภารกิจที่ 1", "pts": 15},\n'
              '    {"desc": "รายละเอียดภารกิจที่ 2", "pts": 20},\n'
              '    {"desc": "รายละเอียดภารกิจที่ 3", "pts": 25},\n'
              '    {"desc": "รายละเอียดภารกิจที่ 4", "pts": 30},\n'
              '    {"desc": "รายละเอียดภารกิจที่ 5", "pts": 40}\n'
              "  ]\n"
              "}"
          )
          response = client.models.generate_content(
              model=model_name, contents=prompt_gen
          )
          raw_res = response.text.strip()

          if "{" in raw_res and "}" in raw_res:
            json_text = raw_res[raw_res.find("{") : raw_res.rfind("}") + 1]
            char_info = json.loads(json_text)

            c_name = char_info.get("name", ai_target_name)
            c_prompt = char_info.get("prompt", "คุณคือ...")
            c_pers = char_info.get("personality", "น่าสนใจ...")
            c_lore = char_info.get("lore", "ประวัติ...")
            f_msgs = char_info.get(
                "first_messages",
                [f"สวัสดีครับ ผม {c_name} ยินดีที่ได้รู้จักครับ"],
            )
            sub_list = char_info.get("supporting_chars", [])
            quest_list = char_info.get("quests", [])

            sample_avatar_urls = [
                "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=600",
                "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=600",
                "https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?w=600",
                "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=600",
                "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=600",
            ]

            try:
              avatar_url = random.choice(sample_avatar_urls)
              avatar_bytes = urllib.request.urlopen(avatar_url, timeout=5).read()
            except Exception:
              avatar_bytes = None

            cursor.execute(
                "INSERT OR REPLACE INTO characters (name, prompt, personality, lore, first_message, avatar) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    c_name,
                    c_prompt,
                    c_pers,
                    c_lore,
                    json.dumps(f_msgs, ensure_ascii=False),
                    avatar_bytes,
                ),
            )

            for sub in sub_list:
              cursor.execute(
                  "INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore) VALUES (?, ?, ?, ?, ?)",
                  (
                      c_name,
                      sub.get("name", "ตัวละครเสริม"),
                      sub.get("prompt", "บทบาท"),
                      sub.get("personality", "นิสัย"),
                      sub.get("lore", "ความสัมพันธ์"),
                  ),
              )

            for q in quest_list:
              cursor.execute(
                  "INSERT INTO quests (char_name, task_desc, reward_points) VALUES (?, ?, ?)",
                  (c_name, q.get("desc", "ทำภารกิจร่วมกัน"), q.get("pts", 20)),
              )

            for _ in range(5):
              try:
                p_url = random.choice(sample_avatar_urls)
                p_bytes = urllib.request.urlopen(p_url, timeout=5).read()
                p_hash = hashlib.md5(p_bytes).hexdigest()
                cursor.execute(
                    "INSERT INTO character_photos (char_name, photo, photo_hash) VALUES (?, ?, ?)",
                    (c_name, p_bytes, p_hash),
                )
              except Exception:
                pass

            conn.commit()
            st.session_state.current_char = c_name
            st.session_state.in_chat = True
            st.success(
                f"🎉 สร้างตัวละคร '{c_name}' พร้อมตัวละครเสริม 5 ตัว ภารกิจ 5 เควสต์ และคลังภาพพรีเมียมสำเร็จเรียบร้อยแล้ว!"
            )
            st.rerun()
          else:
            st.error("เกิดข้อผิดพลาดในการประมวลผลข้อมูลจาก AI")
        except Exception as e:
          st.error(f"เกิดข้อผิดพลาด: {e}")

  elif is_current_admin and sidebar_action == "🌐 นำเข้าตัวละครจากข้อมูลเว็บ (Smart Parser)":
    st.markdown("### 🌐 นำเข้าตัวละครจากข้อมูลหน้าเว็บ")
    with st.form("smart_parser_form"):
      pasted_text = st.text_area(
          "วางข้อมูลที่ก๊อปปี้มาจากหน้าเว็บที่นี่:", height=250
      )
      parse_submit_btn = st.form_submit_button(
          "🚀 แปลงและบันทึกตัวละครเข้าสู่ระบบ", use_container_width=True
      )

      if parse_submit_btn and pasted_text:
        run_with_timer("AI กำลังวิเคราะห์ แยกแยะ และจัดโครงสร้างข้อมูล", 6)
        try:
          parser_prompt = (
              f"คุณคือผู้เชี่ยวชาญการแยกแยะและจัดโครงสร้างข้อมูลตัวละครสำหรับ AI Roleplay\n"
              f"ข้อมูลดิบที่ผู้ใช้นำมาวาง:\n{pasted_text}\n\n"
              f"กรุณาวิเคราะห์และส่งออกเป็นรูปแบบ JSON 1 บรรทัด (ห้ามมีเครื่องหมาย markdown หรือข้อความอื่นปนเด็ดขาด) โครงสร้างดังนี้:\n"
              "{\n"
              '  "name": "ชื่อตัวละครหลัก",\n'
              '  "prompt": "สรุปคาแรคเตอร์หลัก",\n'
              '  "personality": "รายละเอียดบุคลิก",\n'
              '  "lore": "เรื่องราวพื้นหลัง",\n'
              '  "first_messages": ["ข้อความเปิดตัว 1", "ข้อความเปิดตัว 2"],\n'
              '  "supporting_chars": [{"name": "ชื่อตัวเสริม", "prompt": "บทบาท", "personality": "นิสัย", "lore": "ประวัติ"}],\n'
              '  "quests": [{"desc": "ภารกิจ", "pts": 15}]\n'
              "}"
          )
          response = client.models.generate_content(
              model=model_name, contents=parser_prompt
          )
          raw_res = response.text.strip()

          if "{" in raw_res and "}" in raw_res:
            json_text = raw_res[raw_res.find("{") : raw_res.rfind("}") + 1]
            parsed_data = json.loads(json_text)

            c_name = parsed_data.get("name", "ตัวละครนำเข้า")
            c_prompt = parsed_data.get("prompt", "คุณคือ...")
            c_pers = parsed_data.get("personality", "น่าสนใจ...")
            c_lore = parsed_data.get("lore", "ประวัติ...")
            f_msgs = parsed_data.get(
                "first_messages",
                [f"สวัสดีครับ ผม {c_name} ยินดีที่ได้รู้จักครับ"],
            )
            sub_list = parsed_data.get("supporting_chars", [])
            quest_list = parsed_data.get("quests", [])

            cursor.execute(
                "INSERT OR REPLACE INTO characters (name, prompt, personality, lore, first_message, avatar) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    c_name,
                    c_prompt,
                    c_pers,
                    c_lore,
                    json.dumps(f_msgs, ensure_ascii=False),
                    None,
                ),
            )
            for sub in sub_list:
              cursor.execute(
                  "INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore) VALUES (?, ?, ?, ?, ?)",
                  (
                      c_name,
                      sub.get("name", "ตัวละครเสริม"),
                      sub.get("prompt", "บทบาท"),
                      sub.get("personality", "นิสัย"),
                      sub.get("lore", "ประวัติ"),
                  ),
              )
            if quest_list:
              for q in quest_list:
                cursor.execute(
                    "INSERT INTO quests (char_name, task_desc, reward_points) VALUES (?, ?, ?)",
                    (c_name, q.get("desc", "ทำภารกิจ"), q.get("pts", 15)),
                )
            else:
              cursor.execute(
                  "INSERT INTO quests (char_name, task_desc, reward_points) VALUES (?, ?, ?)",
                  (c_name, "พูดคุยทำความรู้จักเพื่อเพิ่มความสนิทสนม", 20),
              )

            conn.commit()
            st.session_state.current_char = c_name
            st.session_state.in_chat = True
            st.success(f"🎉 นำเข้าตัวละคร '{c_name}' สำเร็จเรียบร้อยแล้ว!")
            st.rerun()
          else:
            st.error("ไม่สามารถแปลงข้อมูลได้ กรุณาลองใหม่อีกครั้ง")
        except Exception as e:
          st.error(f"เกิดข้อผิดพลาด: {e}")

  elif is_current_admin and sidebar_action == "🗑️ ลบตัวละครหลัก":
    st.markdown("### 🗑️ ลบตัวละครหลักที่ไม่ต้องการ")
    if all_chars:
      with st.form("delete_char_form"):
        target_char_to_delete = st.selectbox(
            "เลือกตัวละครที่ต้องการลบ:", all_chars
        )
        if st.form_submit_button(
            "🗑️ ยืนยันการลบตัวละครนี้", use_container_width=True
        ):
          cursor.execute(
              "DELETE FROM characters WHERE name = ?", (target_char_to_delete,)
          )
          cursor.execute(
              "DELETE FROM supporting_characters WHERE char_name = ?",
              (target_char_to_delete,),
          )
          cursor.execute(
              "DELETE FROM character_status WHERE char_name = ?",
              (target_char_to_delete,),
          )
          cursor.execute(
              "DELETE FROM quests WHERE char_name = ?",
              (target_char_to_delete,),
          )
          cursor.execute(
              "DELETE FROM character_photos WHERE char_name = ?",
              (target_char_to_delete,),
          )
          cursor.execute(
              "DELETE FROM messages WHERE char_name = ?",
              (target_char_to_delete,),
          )
          cursor.execute(
              "DELETE FROM novel_memories WHERE char_name = ?",
              (target_char_to_delete,),
          )
          conn.commit()
          st.success(
              f"🗑️ ลบตัวละคร '{target_char_to_delete}' เรียบร้อยแล้ว!"
          )
          st.session_state.current_char = None
          st.session_state.in_chat = False
          time.sleep(1)
          st.rerun()
    else:
      st.info("ไม่มีตัวละครในระบบให้ลบ")

  elif is_current_admin and sidebar_action == "➕ สร้างตัวละครหลักใหม่ (Manual)":
    st.markdown("### 📌 สร้างตัวละครหลัก (แบบกำหนดเอง)")
    with st.form("create_char_form"):
      new_name = st.text_input("ชื่อตัวละครหลัก:")
      new_prompt = st.text_area("คาแรคเตอร์หลัก (Prompt):", height=60)
      new_personality = st.text_area("🧠 บุคลิก/นิสัย:", height=60)
      new_lore = st.text_area("📖 เรื่องราวพื้นหลัง (Lore):", height=70)
      msg_1 = st.text_area("#1 แบบที่ 1:", height=70)
      msg_2 = st.text_area("#2 แบบที่ 2:", height=70)
      msg_3 = st.text_area("#3 แบบที่ 3:", height=70)
      new_avatar = st.file_uploader(
          "รูปโปรไฟล์", type=["png", "jpg", "jpeg", "webp"]
      )

      if st.form_submit_button("🚀 บันทึก", use_container_width=True):
        if new_name and new_prompt:
          avatar_bytes = (
              new_avatar.getvalue() if new_avatar is not None else None
          )
          combined_msgs = json.dumps(
              [m.strip() for m in [msg_1, msg_2, msg_3] if m.strip()],
              ensure_ascii=False,
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
          st.success("สำเร็จ!")
          st.rerun()

  elif (
      is_current_admin
      and sidebar_action == "✏️ แก้ไขข้อมูลตัวละครหลัก"
      and active_char
  ):
    cursor.execute(
        "SELECT prompt, personality, lore, first_message, avatar FROM characters WHERE name = ?",
        (active_char,),
    )
    curr_data = cursor.fetchone()
    if curr_data:
      c_prompt, c_pers, c_lore, c_fmsg_json, c_avatar = curr_data
      try:
        old_msgs = json.loads(c_fmsg_json)
      except Exception:
        old_msgs = [c_fmsg_json]

      st.markdown("### ✏️ แก้ไขข้อมูลตัวละครหลัก")
      if st.button("✨ ให้ AI ช่วยขัดเกลา Prompt ให้คมขึ้น (Auto-Refine)", use_container_width=True):
        run_with_timer("AI กำลังวิเคราะห์และขัดเกลา Prompt โดยรักษาแก่นเดิม", 5)
        try:
          refine_prompt = (
              f"คุณคือผู้เชี่ยวชาญการปรับแต่ง Prompt สำหรับ AI Roleplay\n"
              f"ข้อมูลปัจจุบันของตัวละคร '{active_char}':\n"
              f"- คาแรคเตอร์เดิม: {c_prompt}\n"
              f"- บุคลิกเดิม: {c_pers}\n"
              f"- เรื่องราวเดิม: {c_lore}\n\n"
              f"กรุณาปรับปรุงและขัดเกลาข้อความเหล่านี้ให้มีความคมชัด สละสลวย และช่วยให้ AI สวมบทบาทได้อย่างเป็นธรรมชาติยิ่งขึ้น แต่ **ต้องรักษาแก่นแท้ (Core Identity) เดิมไว้ห้ามให้เปลี่ยนเป็นคาแรคเตอร์อื่นเด็ดขาด**\n"
              f"ส่งออกผลลัพธ์ในรูปแบบ JSON 1 บรรทัด (ห้ามมี markdown อื่นปน) โครงสร้างดังนี้:\n"
              '{"refined_prompt": "คาแรคเตอร์ที่ขัดเกลาแล้ว", "refined_personality": "บุคลิกที่ขัดเกลาแล้ว", "refined_lore": "เรื่องราวที่ขัดเกลาแล้ว"}'
          )
          ref_res = client.models.generate_content(
              model=model_name, contents=refine_prompt
          )
          r_text = ref_res.text.strip()
          if "{" in r_text and "}" in r_text:
            r_json = json.loads(r_text[r_text.find("{") : r_text.rfind("}") + 1])
            c_prompt = r_json.get("refined_prompt", c_prompt)
            c_pers = r_json.get("refined_personality", c_pers)
            c_lore = r_json.get("refined_lore", c_lore)
            st.success("✨ AI ขัดเกลาข้อมูลเรียบร้อยแล้ว (กดบันทึกด้านล่างเพื่อยืนยัน)")
        except Exception as e:
          st.error(f"เกิดข้อผิดพลาดในการขัดเกลา: {e}")

      with st.form(f"edit_char_form_{active_char}"):
        edit_prompt = st.text_area(
            "คาแรคเตอร์หลัก:", value=c_prompt, height=60
        )
        edit_pers = st.text_area("บุคลิก:", value=c_pers, height=60)
        edit_lore = st.text_area("เรื่องราว:", value=c_lore, height=70)
        edit_m1 = st.text_area(
            "ข้อความ 1:", value=old_msgs[0] if len(old_msgs) > 0 else "", height=70
        )
        edit_m2 = st.text_area(
            "ข้อความ 2:", value=old_msgs[1] if len(old_msgs) > 1 else "", height=70
        )
        edit_m3 = st.text_area(
            "ข้อความ 3:", value=old_msgs[2] if len(old_msgs) > 2 else "", height=70
        )
        edit_avatar = st.file_uploader(
            "เปลี่ยนรูปโปรไฟล์",
            type=["png", "jpg", "jpeg", "webp"],
            key=f"edit_av_{active_char}",
        )

        if st.form_submit_button("💾 บันทึกการแก้ไข", use_container_width=True):
          new_avatar_bytes = (
              edit_avatar.getvalue() if edit_avatar is not None else c_avatar
          )
          new_combined_msgs = json.dumps(
              [m.strip() for m in [edit_m1, edit_m2, edit_m3] if m.strip()],
              ensure_ascii=False,
          )
          cursor.execute(
              """
                UPDATE characters SET prompt = ?, personality = ?, lore = ?, first_message = ?, avatar = ? WHERE name = ?
            """,
              (
                  edit_prompt,
                  edit_pers,
                  edit_lore,
                  new_combined_msgs,
                  new_avatar_bytes,
                  active_char,
              ),
          )
          conn.commit()
          st.success("อัปเดตสำเร็จ!")
          st.rerun()

  # 👥 จัดการตัวละครเสริม (พร้อมระบบดันตัวละครเสริมขึ้นเป็นตัวละครหลัก + ซิงค์ความทรงจำ)
  elif (
      is_current_admin
      and sidebar_action == "👥 จัดการตัวละครเสริม"
      and active_char
  ):
    st.markdown(f"### 👥 ตัวละครเสริมในเรื่อง: `{active_char}`")
    sub_action = st.radio(
        "เลือกการทำงาน:",
        ["➕ เพิ่มตัวละครเสริม", "✏️ แก้ไข/ลบตัวละครเสริม หรือเลื่อนขั้น"],
        key=f"sub_radio_{active_char}",
    )

    if sub_action == "➕ เพิ่มตัวละครเสริม":
      with st.form(f"add_sub_char_form_{active_char}", clear_on_submit=True):
        sub_name = st.text_input("ชื่อตัวละครเสริม:")
        sub_prompt = st.text_area("คาแรคเตอร์ตัวละครเสริม:", height=60)
        sub_personality = st.text_area("🧠 บุคลิกตัวละครเสริม:", height=60)
        sub_lore = st.text_area("📖 เรื่องราวพื้นหลัง:", height=60)
        if (
            st.form_submit_button(
                "➕ บันทึกตัวละครเสริม", use_container_width=True
            )
            and sub_name
        ):
          cursor.execute(
              """
                INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore)
                VALUES (?, ?, ?, ?, ?)
            """,
              (
                  active_char,
                  sub_name,
                  sub_prompt,
                  sub_personality,
                  sub_lore,
              ),
          )
          conn.commit()
          st.success(f"เพิ่มตัวละครเสริม '{sub_name}' สำเร็จ!")
          st.rerun()
    else:
      cursor.execute(
          "SELECT id, sub_name, sub_prompt, sub_personality, sub_lore, sub_avatar FROM supporting_characters WHERE char_name = ?",
          (active_char,),
      )
      sub_list = cursor.fetchall()
      if sub_list:
        sub_dict = {s[1]: s[0] for s in sub_list}
        selected_sub_name = st.selectbox(
            "เลือกตัวละครเสริม:", list(sub_dict.keys()), key=f"sel_sub_{active_char}"
        )
        selected_sub_id = sub_dict[selected_sub_name]

        curr_sub_info = next(s for s in sub_list if s[0] == selected_sub_id)
        s_id, s_name, s_p, s_pers, s_l, s_av = curr_sub_info

        st.markdown("---")
        if st.button(
            f"⭐ เลื่อนขั้น '{s_name}' ขึ้นเป็นตัวละครหลัก (Main Character)",
            use_container_width=True,
        ):
          default_first_msg = json.dumps(
              [
                  f"*หันมามองคุณด้วยแววตาคุ้นเคย* \"อ้าว... นึกว่าจะลืมกันไปซะแล้วสิ ทักทายกันแบบนี้หมายความว่ายังไงล่ะ?\""
              ],
              ensure_ascii=False,
          )
          cursor.execute(
              """
                INSERT OR REPLACE INTO characters (name, prompt, personality, lore, first_message, avatar)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
              (
                  s_name,
                  s_p,
                  s_pers,
                  f"อดีตตัวละครเสริมในเรื่องของ {active_char}. {s_l}",
                  default_first_msg,
                  s_av,
              ),
          )

          cursor.execute(
              "SELECT memory_summary FROM novel_memories WHERE username = ? AND char_name = ?",
              (current_user, active_char),
          )
          old_mem = cursor.fetchone()
          if old_mem:
            transferred_memory = f"[โอนย้ายความทรงจำจากจักรวาล {active_char}] {old_mem[0]}"
            cursor.execute(
                "INSERT OR REPLACE INTO novel_memories (username, char_name, memory_summary) VALUES (?, ?, ?)",
                (current_user, s_name, transferred_memory),
            )

          cursor.execute(
              "DELETE FROM supporting_characters WHERE id = ?", (selected_sub_id,)
          )
          conn.commit()

          st.session_state.current_char = s_name
          st.session_state.in_chat = True
          st.success(
              f"✨ เลื่อนขั้น '{s_name}' ขึ้นเป็นตัวละครหลักสำเร็จ! พร้อมโอนย้ายความทรงจำเรียบร้อยแล้ว"
          )
          time.sleep(1.2)
          st.rerun()

        with st.form(f"edit_sub_form_{selected_sub_id}"):
          e_sub_name = st.text_input("ชื่อตัวละครเสริม:", value=s_name)
          e_sub_prompt = st.text_area("คาแรคเตอร์:", value=s_p, height=60)
          e_sub_pers = st.text_area("บุคลิก:", value=s_pers, height=60)
          e_sub_lore = st.text_area("เรื่องราว:", value=s_l, height=60)

          col_sub_e1, col_sub_e2 = st.columns(2)
          with col_sub_e1:
            submit_edit_sub = st.form_submit_button(
                "💾 บันทึกการแก้ไข", use_container_width=True
            )
          with col_sub_e2:
            submit_del_sub = st.form_submit_button(
                "🗑️ ลบตัวละครเสริม", use_container_width=True
            )

          if submit_edit_sub:
            cursor.execute(
                """
                    UPDATE supporting_characters 
                    SET sub_name = ?, sub_prompt = ?, sub_personality = ?, sub_lore = ? 
                    WHERE id = ?
                """,
                (
                    e_sub_name,
                    e_sub_prompt,
                    e_sub_pers,
                    e_sub_lore,
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
        st.info("ยังไม่มีตัวละครเสริมในเรื่องนี้")

  elif (
      is_current_admin
      and sidebar_action == "🎯 จัดการภารกิจ (Quest Log)"
      and active_char
  ):
    st.markdown(f"### 🎯 จัดการภารกิจ: {active_char}")
    with st.form(f"add_quest_form_{active_char}", clear_on_submit=True):
      new_quest_desc = st.text_input("รายละเอียดภารกิจใหม่:")
      new_quest_pts = st.slider("คะแนนรางวัลที่จะได้รับ:", 5, 100, 15)
      if (
          st.form_submit_button("➕ เพิ่มภารกิจ", use_container_width=True)
          and new_quest_desc
      ):
        cursor.execute(
            "INSERT INTO quests (char_name, task_desc, reward_points) VALUES (?, ?, ?)",
            (active_char, new_quest_desc, new_quest_pts),
        )
        conn.commit()
        st.success("เพิ่มภารกิจสำเร็จ!")
        st.rerun()

  elif is_current_admin and sidebar_action == "👥 จัดการผู้ใช้งานระบบ":
    st.markdown("### 👥 รายชื่อผู้ใช้งานทั้งหมด")
    cursor.execute("SELECT username, is_admin FROM users")
    users_list = cursor.fetchall()
    if users_list:
      for u_name_db, u_admin in users_list:
        with st.container(border=True):
          role_label = "🛡️ Admin" if u_admin == 1 else "👤 User"
          st.markdown(f"**ยูสเซอร์:** `{u_name_db}` ({role_label})")


# ==========================================
# 🏠 หน้าแรก
# ==========================================
if not st.session_state.in_chat:
  st.title("🔥 จักรวาลยอดนิยม & ตัวละครทั้งหมด")
  st.divider()

  if not all_chars:
    st.info("📭 ยังไม่มีตัวละครในระบบ กรุณาสร้างตัวละครหลักก่อนครับ")
  else:
    cols = st.columns(3)
    for idx, c_name in enumerate(all_chars):
      cursor.execute(
          "SELECT prompt, personality, lore, avatar FROM characters WHERE name = ?",
          (c_name,),
      )
      c_data = cursor.fetchone()
      c_prompt, c_pers, c_lore, c_av = (
          (c_data[0], c_data[1], c_data[2], c_data[3])
          if c_data
          else ("", "", "", None)
      )

      with cols[idx % 3]:
        with st.container(border=True):
          if c_av:
            st.image(Image.open(io.BytesIO(c_av)), use_container_width=True)
          else:
            st.image(
                "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=500",
                use_container_width=True,
            )
          st.markdown(f"### 🌟 {c_name}")

          btn_col1, btn_col2 = st.columns(2)
          with btn_col1:
            with st.popover("📖 ดูข้อมูล", use_container_width=True):
              st.markdown(f"### 🌟 {c_name}")
              st.markdown(f"**📌 คาแรคเตอร์:**\n{c_prompt}")
              st.markdown(f"**🧠 บุคลิก/นิสัย:**\n{c_pers}")
              st.markdown(f"**📖 เรื่องราวพื้นหลัง:**\n{c_lore}")
          with btn_col2:
            if st.button(
                "✨ แชท", key=f"b_{c_name}", use_container_width=True
            ):
              st.session_state.current_char = c_name
              st.session_state.in_chat = True
              st.rerun()
  st.stop()


# ==========================================
# 💬 ห้องแชท (พร้อมระบบครบครัน)
# ==========================================
if st.session_state.in_chat and st.session_state.current_char:
  cursor.execute(
      "SELECT prompt, personality, lore, first_message, avatar FROM characters WHERE name = ?",
      (st.session_state.current_char,),
  )
  char_data = cursor.fetchone()

  base_prompt = char_data[0] if char_data else ""
  char_personality = char_data[1] if char_data else ""
  char_lore = char_data[2] if char_data else ""
  char_first_msg_raw = char_data[3] if char_data else "[]"
  char_avatar_img = (
      Image.open(io.BytesIO(char_data[4]))
      if (char_data and char_data[4])
      else None
  )

  cursor.execute(
      "SELECT sub_name, sub_prompt, sub_personality FROM supporting_characters WHERE char_name = ?",
      (st.session_state.current_char,),
  )
  subs_data = cursor.fetchall()
  supporting_text = (
      ", ".join(
          [f"{s[0]} (บทบาท: {s[1]}, นิสัย: {s[2]})" for s in subs_data]
      )
      or "ไม่มี"
  )

  cursor.execute(
      "INSERT OR IGNORE INTO character_status (username, char_name, affection_score, relationship_level) VALUES (?, ?, 0, 'คนแปลกหน้า')",
      (current_user, st.session_state.current_char),
  )
  conn.commit()

  cursor.execute(
      "SELECT affection_score, relationship_level FROM character_status WHERE username = ? AND char_name = ?",
      (current_user, st.session_state.current_char),
  )
  status_row = cursor.fetchone()
  current_affection, current_rel_level = (
      (status_row[0], status_row[1]) if status_row else (0, "คนแปลกหน้า")
  )

  cursor.execute(
      "SELECT memory_summary FROM novel_memories WHERE username = ? AND char_name = ?",
      (current_user, st.session_state.current_char),
  )
  mem_row = cursor.fetchone()
  long_term_memory = (
      mem_row[0]
      if mem_row
      else "ยังไม่มีเหตุการณ์สำคัญสะสม เริ่มต้นเรื่องราวใหม่"
  )

  roleplay_instruction = f"""
คุณคือนักเขียนนิยายโรแมนติก/ดราม่ามืออาชีพชั้นเยี่ยม และผู้สวมบทบาทตัวละครหลัก '{st.session_state.current_char}'
- ข้อมูลคาแรคเตอร์หลัก: {base_prompt}
- นิสัย: {char_personality}
- เรื่องราวพื้นหลัง (Lore): {char_lore}
- รายชื่อตัวละครเสริมที่มีส่วนร่วมในฉากนี้: {supporting_text}

[ความทรงจำระยะยาวของเรื่องราว (Long-term Memory Vault)]:
"{long_term_memory}"

[ผู้สนทนา]: ชื่อ {u_name} | ประวัติ: {u_persona} | สรรพนามพูด: {u_pspeak} | สรรพนามบรรยาย: {u_pdesc} | เรียกผู้ใช้: {u_cspeak}
- ความสัมพันธ์ปัจจุบัน: "{current_rel_level}" (แต้มความชอบสะสม: {current_affection} แต้ม)

[กฎการเขียนบทบาทระดับพรีเมียม (บทสนทนาสมจริง & ตัวละครเสริมมีบทบาท)]:
1. **การมีส่วนร่วมของตัวละครเสริม**: ให้ดึงตัวละครเสริมที่มีรายชื่อข้างต้นเข้ามามีบทบาทพูดคุย โต้ตอบ ขัดจังหวะ หรือสร้างปฏิกิริยาร่วมกับตัวละครหลักและผู้เล่นในฉากอย่างสม่ำเสมอ
2. **การบรรยายเชิงลึก (Deep Descriptive Writing)**: บรรยายท่าทาง แววตา บรรยากาศ และจิตวิทยาอย่างประณีต
3. **จัดย่อหน้าและเว้นบรรทัดให้อ่านง่าย**: ห้ามเขียนพารากราฟยาวติดกัน ให้เคาะบรรทัดใหม่แบ่งฉากชัดเจน
4. **รูปแบบสัดส่วน**: 
   - ส่วนบรรยาย ท่าทาง สีหน้า และความคิดในใจ ให้อยู่ในเครื่องหมาย *...* (แสดงผลเป็นสีเทาอ่อน ตัวตรงปกติ ไม่อียง)
   - บทพูด ให้ใช้เครื่องหมายคำพูดปกติ เช่น `{st.session_state.current_char}: "..."` หรือตามชื่อตัวละครเสริม
5. **บรรทัดสุดท้ายต้องเป็น JSON รูปแบบนี้เป๊ะๆ ห้ามพลาดเด็ดขาด**:
{{"score_change": [ตัวเลขเช่น 2 หรือ 5], "quest_update": [หมายเลขไอดีภารกิจ หรือ null], "memory_update": "[สรุปเหตุการณ์สำคัญสั้นๆ 1 ประโยค]"}}
"""


  def get_random_first_msg(raw_json, char_name):
    try:
      msgs = json.loads(raw_json)
      if msgs:
        return random.choice(msgs)
    except Exception:
      pass
    return f"*ปรายตามองคุณด้วยความเรียบเฉย ก่อนจะแค่นหัวเราะในลำคอเบาๆ* \"มีธุระอะไร ถึงได้มาเกาะแกะอยู่แถวนี้ล่ะ?\""


  cursor.execute(
      "SELECT COUNT(*) FROM messages WHERE username = ? AND char_name = ?",
      (current_user, st.session_state.current_char),
  )
  if cursor.fetchone()[0] == 0:
    init_msg = get_random_first_msg(
        char_first_msg_raw, st.session_state.current_char
    )
    cursor.execute(
        "INSERT INTO messages (username, char_name, role, content) VALUES (?, ?, 'assistant', ?)",
        (current_user, st.session_state.current_char, init_msg),
    )
    conn.commit()

  cursor.execute(
      """
      SELECT role, content, image_blob FROM (
          SELECT role, content, image_blob, id FROM messages 
          WHERE username = ? AND char_name = ? 
          ORDER BY id DESC LIMIT 15
      ) ORDER BY id ASC
  """,
      (current_user, st.session_state.current_char),
  )

  current_messages = [
      {
          "role": r[0],
          "content": r[1],
          "image": Image.open(io.BytesIO(r[2])) if r[2] else None,
      }
      for r in cursor.fetchall()
  ]

  col_av, col_title, col_reset = st.columns([1, 4, 3])
  with col_av:
    if char_avatar_img:
      st.image(char_avatar_img, width=50)
    else:
      st.image("https://api.iconify.design/lucide:user-round.svg", width=50)
  with col_title:
    st.markdown(
        f"### แชทกับ: `{st.session_state.current_char}` (ผู้ใช้: `{u_name}`)"
    )
  with col_reset:
    col_r1, col_r2 = st.columns(2)
    with col_r1:
      if st.button("🔄 รีเซ็ตแชท", use_container_width=True):
        cursor.execute(
            "DELETE FROM messages WHERE username = ? AND char_name = ?",
            (current_user, st.session_state.current_char),
        )
        cursor.execute(
            "UPDATE character_status SET affection_score = 0, relationship_level = 'คนแปลกหน้า' WHERE username = ? AND char_name = ?",
            (current_user, st.session_state.current_char),
        )
        cursor.execute(
            "DELETE FROM novel_memories WHERE username = ? AND char_name = ?",
            (current_user, st.session_state.current_char),
        )
        conn.commit()
        st.rerun()
    with col_r2:
      with st.popover("📖 เมนูลับ", use_container_width=True):
        st.markdown("#### ✨ ฟีเจอร์พิเศษพรีเมียม")
        if st.button("📖 แปลงแชทเป็นตอนนิยาย", use_container_width=True):
          with st.spinner("กำลังแปลงแชทเป็นตอนนิยาย..."):
            chat_log_text = "\n".join(
                [f"{m['role']}: {m['content']}" for m in current_messages]
            )
            novel_res = client.models.generate_content(
                model=model_name,
                contents=f"คุณคือนักเขียนนิยายมืออาชีพ จงนำบทสนทนา Roleplay ต่อไปนี้มาเรียบเรียงใหม่ให้เป็น 'ตอนนิยายบรรยาย' ที่สละสลวยต่อเนื่อง อ่านสนุก บรรยายอารมณ์และความรู้สึกเต็มอิ่ม โดยตัดบทสนทนาคำสั่งออก:\n{chat_log_text}",
            )
            st.markdown("### 📜 ตอนนิยายของคุณ:")
            st.write(novel_res.text)

        if st.button("📓 ส่องไดอารี่ตัวละคร", use_container_width=True):
          with st.spinner("กำลังเปิดดูบันทึกส่วนตัว..."):
            diary_res = client.models.generate_content(
                model=model_name,
                contents=f"คุณคือตัวละคร '{st.session_state.current_char}' เขียนไดอารี่ส่วนตัวระบายความรู้สึกที่มีต่อผู้เล่น ('{u_name}') หลังจากผ่านเหตุการณ์ล่าสุด ความสัมพันธ์ตอนนี้คือ '{current_rel_level}':\nความทรงจำล่าสุด: {long_term_memory}",
            )
            st.markdown("### 📔 บันทึกส่วนตัวของตัวละคร:")
            st.info(diary_res.text)

  if is_current_admin:
    with st.expander(
        "🛡️ [Admin Panel] AI กรรมการตรวจและประเมินบทบาทแบบละเอียดขั้นสุด"
    ):
      st.caption(
          "กดปุ่มด้านล่างเพื่อให้ AI กรรมการตรวจวิเคราะห์บทสนทนาอย่างเจาะลึก"
          " (ใช้เวลาประมวลผลประมาณ 6 วินาทีเพื่อความแม่นยำสูงสุด)"
      )
      if st.button(
          "🧪 รัน AI กรรมการตรวจบทบาท (ละเอียดขั้นสุด)", use_container_width=True
      ):
        run_with_timer("AI กรรมการกำลังตรวจสอบบทสนทนาและจิตวิทยาตัวละคร", 6)
        try:
          recent_chat_log = "\n".join(
              [f"{m['role']}: {m['content']}" for m in current_messages[-8:]]
          )
          audit_prompt = (
              f"คุณคือ AI Game Master ผู้เชี่ยวชาญระดับสูงในการตรวจสอบและวิเคราะห์การสวมบทบาท (Advanced Roleplay & Psychological Audit)\n"
              f"ข้อมูลตัวละครหลัก '{st.session_state.current_char}':\n"
              f"- คาแรคเตอร์: {base_prompt}\n"
              f"- บุคลิก: {char_personality}\n"
              f"- เรื่องราว (Lore): {char_lore}\n\n"
              f"บทสนทนาล่าสุด 8 ข้อความ:\n{recent_chat_log}\n\n"
              f"กรุณาวิเคราะห์และรายงานผลอย่างละเอียดเป็นภาษาไทย โดยครอบคลุมประเด็นต่อไปนี้:\n"
              f"1. **คะแนนความเข้าบทบาท (0-10):** [พร้อมให้เหตุผลรองรับ]\n"
              f"2. **การวิเคราะห์เชิงลึก (In-depth Analysis):** [วิเคราะห์ความต่อเนื่องของพล็อต, การรักษาคาแรคเตอร์, จิตวิทยาตัวละคร, และความสมจริงของภาษาบรรยาย]\n"
              f"3. **จุดที่ควรปรับปรุง & แนวทางแก้ไข (Constructive Feedback):** [แนะนำจุดที่ยังดูแข็งทื่อ พร้อมระบุวิธีปรับแก้ System Prompt หรือท่าทีของบอทให้มีความเป็นธรรมชาติสูงสุด]"
          )
          audit_res = client.models.generate_content(
              model=model_name, contents=audit_prompt
          )
          st.markdown("### 📊 รายงานผลการประเมินเจาะลึกจาก AI กรรมการ:")
          st.info(audit_res.text)
        except Exception as e:
          st.error(f"เกิดข้อผิดพลาดในการตรวจสอบ: {e}")

  st.divider()

  for message in current_messages:
    if message["role"] == "user":
      with st.chat_message("user", avatar="👤"):
        st.markdown(message["content"])
    else:
      with st.chat_message(
          "assistant", avatar=char_avatar_img if char_avatar_img else "✨"
      ):
        col_badge, col_pop = st.columns([4, 1.2])
        with col_badge:
          st.markdown(
              f'<div class="affection-badge">💖 {current_rel_level} | คะแนนสะสม: {current_affection} แต้ม</div>',
              unsafe_allow_html=True,
          )
        with col_pop:
          with st.popover("🎯 ภารกิจ", use_container_width=True):
            st.markdown("#### 🎯 รายการภารกิจ")
            cursor.execute(
                "SELECT id, task_desc, reward_points FROM quests WHERE char_name = ?",
                (st.session_state.current_char,),
            )
            quests_in_db = cursor.fetchall()
            if quests_in_db:
              for q_id, desc, pts in quests_in_db:
                cursor.execute(
                    "SELECT is_completed FROM user_quests WHERE username = ? AND quest_id = ?",
                    (current_user, q_id),
                )
                uq = cursor.fetchone()
                is_comp = uq[0] if uq else 0
                if is_comp:
                  st.markdown(
                      f"- ✅ **[#{q_id}]** ~~{desc}~~ — *สำเร็จแล้ว* (+{pts}"
                      " แต้ม)"
                  )
                else:
                  st.markdown(
                      f"- ⏳ **[#{q_id}]** {desc} — *ยังไม่สำเร็จ* (รางวัล:"
                      f" {pts} แต้ม)"
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
        "INSERT INTO messages (username, char_name, role, content) VALUES (?, ?, 'user', ?)",
        (current_user, st.session_state.current_char, user_input),
    )
    conn.commit()

    with st.chat_message("user", avatar="👤"):
      st.markdown(user_input)

    is_cheat = False
    bot_response = ""
    score_change = 0
    completed_q_id = None
    new_mem_snippet = None

    if user_input.startswith("/+ชอบ "):
      is_cheat = True
      try:
        score_change = int(user_input.replace("/+ชอบ ", "").strip())
        bot_response = (
            f"*(สังเกตการณ์ระบบ: เพิ่มแต้มความชอบสะสมให้ {score_change}"
            " คะแนนเรียบร้อย)*"
        )
      except Exception:
        bot_response = "*(รูปแบบคำสั่งไม่ถูกต้อง ใช้ตัวอย่าง: `/+ชอบ 100`)*"
    elif user_input.startswith("/+ผ่านภารกิจ "):
      is_cheat = True
      try:
        completed_q_id = int(user_input.replace("/+ผ่านภารกิจ ", "").strip())
        cursor.execute(
            "SELECT task_desc, reward_points FROM quests WHERE id = ? AND char_name = ?",
            (completed_q_id, st.session_state.current_char),
        )
        q_data = cursor.fetchone()
        if q_data:
          bot_response = f"*(สังเกตการณ์ระบบ: ทำภารกิจที่ #{completed_q_id} '{q_data[0]}' สำเร็จ! รับไป {q_data[1]} แต้ม)*"
        else:
          bot_response = (
              f"*(สังเกตการณ์ระบบ: ไม่พบภารกิจหมายเลข #{completed_q_id})*"
          )
          completed_q_id = None
      except Exception:
        bot_response = (
            "*(รูปแบบคำสั่งไม่ถูกต้อง ใช้ตัวอย่าง: `/+ผ่านภารกิจ 1`)*"
        )

    with st.chat_message(
        "assistant", avatar=char_avatar_img if char_avatar_img else "✨"
    ):
      message_placeholder = st.empty()

      if is_cheat:
        time.sleep(0.3)
        message_placeholder.markdown(bot_response)
        eval_data = {
            "score_change": score_change,
            "quest_update": completed_q_id,
            "memory_update": None,
        }
      else:
        message_placeholder.markdown(
            "AI กำลังเรียบเรียงและประพันธ์เนื้อเรื่องระดับพรีเมียม..."
        )
        bot_response = None
        eval_data = {}
        max_retries = 3

        for attempt in range(max_retries):
          try:
            formatted_history = [
                {
                    "role": "user" if m["role"] == "user" else "model",
                    "parts": [{"text": m["content"]}],
                }
                for m in current_messages
            ]

            chat = client.chats.create(
                model=model_name,
                history=formatted_history if formatted_history else None,
                config={
                    "system_instruction": roleplay_instruction,
                    "temperature": 1.1,
                },
            )

            response = chat.send_message(user_input)
            raw_text = response.text

            if "{" in raw_text and "}" in raw_text:
              parts = raw_text.rsplit("{", 1)
              bot_response = parts[0].strip()
              try:
                eval_data = json.loads("{" + parts[1])
              except Exception:
                eval_data = {
                    "score_change": 2,
                    "quest_update": None,
                    "memory_update": None,
                }
            else:
              bot_response = raw_text
              eval_data = {
                  "score_change": 2,
                  "quest_update": None,
                  "memory_update": None,
              }
            break

          except Exception as e:
            if attempt < max_retries - 1:
              message_placeholder.markdown(
                  f"⚠️ กำลังเชื่อมต่อใหม่ครั้งที่ {attempt + 2}..."
              )
              time.sleep(1.5)
            else:
              bot_response = (
                  f"ขออภัยครับ เกิดข้อผิดพลาดในการเชื่อมต่อ: `{str(e)}`"
              )
              eval_data = {
                  "score_change": 0,
                  "quest_update": None,
                  "memory_update": None,
              }
        message_placeholder.markdown(bot_response)

      if bot_response:
        score_change = eval_data.get("score_change", score_change)
        completed_q_id = eval_data.get("quest_update", completed_q_id)
        new_mem_snippet = eval_data.get("memory_update", None)

        if new_mem_snippet:
          updated_memory_vault = (
              f"{long_term_memory} -> {new_mem_snippet}"
              if long_term_memory != "ยังไม่มีเหตุการณ์สำคัญสะสม เริ่มต้นเรื่องราวใหม่"
              else new_mem_snippet
          )
          cursor.execute(
              "INSERT OR REPLACE INTO novel_memories (username, char_name, memory_summary) VALUES (?, ?, ?)",
              (
                  current_user,
                  st.session_state.current_char,
                  updated_memory_vault,
              ),
          )

        quest_bonus = 0
        if completed_q_id:
          cursor.execute(
              "SELECT is_completed FROM user_quests WHERE username = ? AND quest_id = ?",
              (current_user, completed_q_id),
          )
          uq_row = cursor.fetchone()
          if not uq_row or uq_row[0] == 0:
            cursor.execute(
                "SELECT reward_points FROM quests WHERE id = ?",
                (completed_q_id,),
            )
            q_info = cursor.fetchone()
            if q_info:
              quest_bonus = q_info[0]
              cursor.execute(
                  "INSERT OR REPLACE INTO user_quests (username, quest_id, is_completed) VALUES (?, ?, 1)",
                  (current_user, completed_q_id),
              )

        updated_score = max(0, current_affection + score_change + quest_bonus)
        new_lvl = get_relationship_level(updated_score)

        cursor.execute(
            "UPDATE character_status SET affection_score = ?, relationship_level = ? WHERE username = ? AND char_name = ?",
            (
                updated_score,
                new_lvl,
                current_user,
                st.session_state.current_char,
            ),
        )

        attached_photo_bytes = None
        cursor.execute(
            "SELECT photo FROM character_photos WHERE char_name = ?",
            (st.session_state.current_char,),
        )
        photos = cursor.fetchall()
        if photos and random.random() < 0.30:
          attached_photo_bytes = random.choice(photos)[0]

        if attached_photo_bytes:
          st.image(Image.open(io.BytesIO(attached_photo_bytes)), width=280)

        cursor.execute(
            "INSERT INTO messages (username, char_name, role, content, image_blob) VALUES (?, ?, 'assistant', ?, ?)",
            (
                current_user,
                st.session_state.current_char,
                bot_response,
                attached_photo_bytes,
            ),
        )
        conn.commit()
        st.rerun()
