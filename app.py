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
from bs4 import BeautifulSoup

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

    /* 🖋️ ปรับแต่งสไตล์ข้อความบรรยายและการกระทำในแชทให้เป็นสีเทาอ่อน/ตัวเอียง */
    .stChatMessage p em, .stChatMessage em {
        color: #94a3b8 !important;
        font-style: italic !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# 🗄️ ฟังก์ชันฐานข้อมูล SQLite
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


# 📈 ฟังก์ชันคำนวณระดับความสัมพันธ์ เปลี่ยนทุกๆ 100 คะแนนเป๊ะๆ
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

  # 🎭 เมนูตั้งค่าบทบาทตัวตนของคุณ พร้อมฟังก์ชันสร้างด้วย AI
  with st.expander("⚙️ ตั้งค่าบทบาทตัวตนของคุณ"):
    if st.session_state.current_char:
      if st.button("✨ ให้ AI สร้างบทบาทให้เข้ากับเรื่องนี้", use_container_width=True):
        with st.spinner("AI กำลังสร้างบทบาทที่เหมาะสม..."):
          try:
            cursor.execute(
                "SELECT prompt, personality, lore FROM characters WHERE name = ?",
                (st.session_state.current_char,),
            )
            c_info = cursor.fetchone()
            c_p, c_pers, c_l = c_info if c_info else ("", "", "")

            ai_prompt = (
                f"คุณคือผู้ช่วยสร้างบทบาทผู้เล่น (User Persona) สำหรับนำไปสวมบทบาท (Roleplay) ร่วมกับตัวละครหลักชื่อ '{st.session_state.current_char}'\n"
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
            "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติ)",
            "🌐 ดึงข้อมูลตัวละครจากเว็บไซต์ด้วย AI",
            "➕ สร้างตัวละครหลักใหม่ (Manual)",
            "✏️ แก้ไขข้อมูลตัวละครหลัก",
            "👥 จัดการตัวละครเสริม",
            "🎯 จัดการภารกิจ (Quest Log)",
            "🖼️ จัดการคลังรูปภาพ",
            "👥 จัดการผู้ใช้งานระบบ",
        ],
    )
  else:
    sidebar_action = "เลือกตัวละคร"

  # 📌 เลือกตัวละครหลักสำหรับเมนูจัดการ
  if all_chars and sidebar_action not in [
      "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติ)",
      "🌐 ดึงข้อมูลตัวละครจากเว็บไซต์ด้วย AI",
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

  # ✨ 1.5 ฟีเจอร์ใหม่: สร้างตัวละครหลักด้วย AI อัตโนมัติจากชื่อดารา/ตัวละคร
  if is_current_admin and sidebar_action == "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติ)":
    st.markdown("### ✨ สร้างตัวละครหลักด้วย AI")
    st.caption(
        "กรอกชื่อดาราหรือตัวละครที่ต้องการ แล้วให้ AI จัดการสร้างข้อมูลทั้งหมดให้ทันที!"
    )

    with st.form("ai_gen_char_form"):
      ai_target_name = st.text_input(
          "ชื่อดารา หรือ ตัวละครหลัก:",
          placeholder="เช่น Mark Tuan, ทอม Hiddleston...",
      )
      ai_submit_btn = st.form_submit_button(
          "🚀 ให้ AI สร้างตัวละครนี้แบบครบชุด", use_container_width=True
      )

      if ai_submit_btn and ai_target_name:
        with st.spinner(
            f"กำลังให้ AI สร้างข้อมูลทั้งหมดของ '{ai_target_name}'..."
        ):
          try:
            prompt_gen = (
                f"คุณคือผู้เชี่ยวชาญการสร้างข้อมูลตัวละครสำหรับ Roleplay กรุณาสร้างข้อมูลแบบละเอียดสำหรับ '{ai_target_name}' ในรูปแบบ JSON 1 บรรทัด (ห้ามมีเครื่องหมาย markdown หรือข้อความอื่นปนเด็ดขาด) โครงสร้างดังนี้:\n"
                "{\n"
                f'  "name": "{ai_target_name}",\n'
                '  "prompt": "คาแรคเตอร์หลักและบทบาทของตัวละครนี้",\n'
                '  "personality": "บุคลิกและนิสัยใจคอ",\n'
                '  "lore": "เรื่องราวพื้นหลังและความสัมพันธ์",\n'
                '  "first_messages": ["ข้อความเปิดตัวแบบที่ 1", "ข้อความเปิดตัวแบบที่ 2", "ข้อความเปิดตัวแบบที่ 3"],\n'
                '  "sub_name": "ชื่อตัวละครเสริมรอบตัว 1 คน",\n'
                '  "sub_prompt": "คาแรคเตอร์ตัวละครเสริม",\n'
                '  "sub_personality": "บุคลิกตัวละครเสริม",\n'
                '  "quest_desc": "ภารกิจเริ่มต้นชวนทำกิจกรรมร่วมกัน"\n'
                "}"
            )
            response = client.models.generate_content(
                model=model_name, contents=prompt_gen
            )
            raw_res = response.text.strip()

            if "{" in raw_res and "}" in raw_res:
              json_text = raw_res[
                  raw_res.find("{") : raw_res.rfind("}") + 1
              ]
              char_info = json.loads(json_text)

              c_name = char_info.get("name", ai_target_name)
              c_prompt = char_info.get("prompt", "คุณคือ...")
              c_pers = char_info.get("personality", "เงียบขรึม...")
              c_lore = char_info.get("lore", "ประวัติความเป็นมา...")
              f_msgs = char_info.get(
                  "first_messages",
                  [f"สวัสดีครับ ผม {c_name} ยินดีที่ได้รู้จักครับ"],
              )
              s_name = char_info.get("sub_name", "ผู้จัดการส่วนตัว")
              s_prompt = char_info.get("sub_prompt", "คอยดูแลตารางงาน")
              s_pers = char_info.get("sub_personality", "เข้มงวด รักความสะอาด")
              q_desc = char_info.get(
                  "quest_desc", "พูดคุยทำความรู้จักเพื่อเพิ่มความสนิทสนม"
              )

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

              cursor.execute(
                  "INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore) VALUES (?, ?, ?, ?, ?)",
                  (
                      c_name,
                      s_name,
                      s_prompt,
                      s_pers,
                      "เป็นบุคคลใกล้ชิดในวงสังคม",
                  ),
              )

              cursor.execute(
                  "INSERT INTO quests (char_name, task_desc, reward_points) VALUES (?, ?, ?)",
                  (c_name, q_desc, 20),
              )

              conn.commit()
              st.session_state.current_char = c_name
              st.session_state.in_chat = True
              st.success(
                  f"🎉 สร้างตัวละคร '{c_name}' พร้อมใช้งานสำเร็จเรียบร้อยแล้ว!"
              )
              st.rerun()
            else:
              st.error("เกิดข้อผิดพลาดในการประมวลผลข้อมูลจาก AI กรุณาลองใหม่อีกครั้ง")
          except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")

  # 🌐 ฟีเจอร์ใหม่: ดึงข้อมูลตัวละครจากเว็บไซต์ด้วย AI
  elif is_current_admin and sidebar_action == "🌐 ดึงข้อมูลตัวละครจากเว็บไซต์ด้วย AI":
    st.markdown("### 🌐 ดึงข้อมูลตัวละครจากเว็บไซต์")
    st.caption(
        "วางลิงก์เว็บไซต์ แล้วให้ AI ดึงข้อมูลเนื้อหามาวิเคราะห์สร้างตัวละครให้อัตโนมัติ!"
    )

    with st.form("web_scrape_char_form"):
      web_url = st.text_input(
          "ลิงก์เว็บไซต์ (URL):",
          placeholder="https://www.lovecube.ai/?character=...",
      )
      web_submit_btn = st.form_submit_button(
          "🚀 ดึงข้อมูลและสร้างตัวละคร", use_container_width=True
      )

      if web_submit_btn and web_url:
        with st.spinner(
            f"กำลังดึงข้อมูลและให้ AI วิเคราะห์เนื้อหาจาก {web_url}..."
        ):
          try:
            # ดึงเนื้อหา HTML จากเว็บ
            req = urllib.request.Request(
                web_url, headers={"User-Agent": "Mozilla/5.0"}
            )
            html_content = ""
            try:
              with urllib.request.urlopen(req, timeout=10) as response:
                html_content = response.read().decode("utf-8", errors="ignore")
            except Exception:
              html_content = (
                  "ไม่สามารถดึงข้อมูลดิบจากเว็บได้โดยตรง แต่ลิงก์คือ: " + web_url
              )

            # ใช้ BeautifulSoup กวาดเอาเฉพาะข้อความตัวหนังสือ
            soup = BeautifulSoup(html_content, "html.parser")
            for script in soup(["script", "style"]):
              script.decompose()
            text_data = soup.get_text(separator=" ", strip=True)[:15000]

            prompt_gen = (
                f"คุณคือผู้เชี่ยวชาญการแปลงข้อมูลเว็บให้เป็นตัวละคร Roleplay\n"
                f"ลิงก์เว็บ: {web_url}\n"
                f"เนื้อหาที่ดึงมาได้: {text_data}\n\n"
                f"กรุณาสรุปและสร้างข้อมูลตัวละครในรูปแบบ JSON 1 บรรทัด (ห้ามมีเครื่องหมาย markdown หรือข้อความอื่นปนเด็ดขาด) โครงสร้างดังนี้:\n"
                "{\n"
                '  "name": "ชื่อตัวละคร",\n'
                '  "prompt": "คาแรคเตอร์หลักและบทบาทจากเนื้อหาเว็บ",\n'
                '  "personality": "บุคลิกและนิสัยใจคอ",\n'
                '  "lore": "เรื่องราวพื้นหลัง",\n'
                '  "first_messages": ["ข้อความเปิดตัวแบบที่ 1", "ข้อความเปิดตัวแบบที่ 2"],\n'
                '  "sub_name": "ชื่อตัวละครเสริมที่เกี่ยวข้อง 1 คน",\n'
                '  "sub_prompt": "คาแรคเตอร์ตัวละครเสริม",\n'
                '  "sub_personality": "บุคลิกตัวละครเสริม",\n'
                '  "quest_desc": "ภารกิจเริ่มต้น"\n'
                "}"
            )
            response = client.models.generate_content(
                model=model_name, contents=prompt_gen
            )
            raw_res = response.text.strip()

            if "{" in raw_res and "}" in raw_res:
              json_text = raw_res[
                  raw_res.find("{") : raw_res.rfind("}") + 1
              ]
              char_info = json.loads(json_text)

              c_name = char_info.get("name", "ตัวละครจากเว็บ")
              c_prompt = char_info.get("prompt", "คุณคือ...")
              c_pers = char_info.get("personality", "น่าสนใจ...")
              c_lore = char_info.get("lore", "ประวัติความเป็นมา...")
              f_msgs = char_info.get(
                  "first_messages",
                  [f"สวัสดีครับ ผม {c_name} ยินดีที่ได้รู้จักครับ"],
              )
              s_name = char_info.get("sub_name", "ผู้เกี่ยวข้อง")
              s_prompt = char_info.get("sub_prompt", "คอยสนับสนุน")
              s_pers = char_info.get("sub_personality", "เป็นมิตร")
              q_desc = char_info.get("quest_desc", "ทำความรู้จักกันเบื้องต้น")

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

              cursor.execute(
                  "INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore) VALUES (?, ?, ?, ?, ?)",
                  (
                      c_name,
                      s_name,
                      s_prompt,
                      s_pers,
                      "บุคคลในเนื้อเรื่อง",
                  ),
              )

              cursor.execute(
                  "INSERT INTO quests (char_name, task_desc, reward_points) VALUES (?, ?, ?)",
                  (c_name, q_desc, 20),
              )

              conn.commit()
              st.session_state.current_char = c_name
              st.session_state.in_chat = True
              st.success(
                  f"🎉 ดึงข้อมูลและสร้างตัวละคร '{c_name}' จากเว็บไซต์สำเร็จเรียบร้อยแล้ว!"
              )
              st.rerun()
            else:
              st.error(
                  "ไม่สามารถแปลงข้อมูลจากเว็บไซต์ได้ กรุณาลองใหม่อีกครั้งหรือตรวจสอบลิงก์"
              )
          except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการดึงเว็บ: {e}")

  # 1. สร้างตัวละครหลักใหม่ (Manual)
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

  # 2. แก้ไขข้อมูลตัวละครหลัก (Admin Only)
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

  # 3. จัดการตัวละครเสริม (Admin Only)
  elif (
      is_current_admin
      and sidebar_action == "👥 จัดการตัวละครเสริม"
      and active_char
  ):
    st.markdown(f"### 👥 ตัวละครเสริม: {active_char}")
    sub_action = st.radio("เลือกการทำงาน:", ["➕ เพิ่มตัวละครเสริม", "✏️ แก้ไข/ลบตัวละครเสริม"], key=f"sub_radio_{active_char}")

    if sub_action == "➕ เพิ่มตัวละครเสริม":
      with st.form(f"add_sub_char_form_{active_char}", clear_on_submit=True):
        sub_name = st.text_input("ชื่อตัวละครเสริม:")
        sub_prompt = st.text_area("คาแรคเตอร์ตัวละครเสริม:", height=60)
        sub_personality = st.text_area("🧠 บุคลิกตัวละครเสริม:", height=60)
        sub_lore = st.text_area("📖 เรื่องราวพื้นหลัง:", height=60)
        sub_avatar = st.file_uploader(
            "รูปตัวละครเสริม", type=["png", "jpg", "jpeg", "webp"], key=f"sub_av_{active_char}"
        )

        if (
            st.form_submit_button(
                "➕ บันทึกตัวละครเสริม", use_container_width=True
            )
            and sub_name
        ):
          sub_avatar_bytes = (
              sub_avatar.getvalue() if sub_avatar is not None else None
          )
          cursor.execute(
              """
                INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore, sub_avatar)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
              (
                  active_char,
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
          (active_char,),
      )
      sub_list = cursor.fetchall()
      if sub_list:
        sub_dict = {s[1]: s[0] for s in sub_list}
        selected_sub_name = st.selectbox(
            "เลือกตัวละครเสริม:", list(sub_dict.keys()), key=f"sel_sub_{active_char}"
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
                "เปลี่ยนรูปตัวละครเสริม", type=["png", "jpg", "jpeg", "webp"], key=f"edit_sub_av_{selected_sub_id}"
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
      and active_char
  ):
    st.markdown(f"### 🎯 จัดการภารกิจ: {active_char}")
    with st.form(f"add_quest_form_{active_char}", clear_on_submit=True):
      new_quest_desc = st.text_input("รายละเอียดภารกิจใหม่:")
      new_quest_pts = st.slider("คะแนนรางวัลที่จะได้รับ:", 5, 100, 15, key=f"q_pts_{active_char}")
      if st.form_submit_button("➕ เพิ่มภารกิจ", use_container_width=True) and new_quest_desc:
        cursor.execute(
            "INSERT INTO quests (char_name, task_desc, reward_points) VALUES (?, ?, ?)",
            (active_char, new_quest_desc, new_quest_pts),
        )
        conn.commit()
        st.success("เพิ่มภารกิจสำเร็จ!")
        st.rerun()

    st.markdown("---")
    cursor.execute(
        "SELECT id, task_desc, reward_points FROM quests WHERE char_name = ?",
        (active_char,),
    )
    q_list = cursor.fetchall()
    if q_list:
      for q_id, q_desc, q_pts in q_list:
        q_col1, q_col2 = st.columns([4, 1])
        with q_col1:
          st.markdown(f"- **[#{q_id}]** {q_desc} `(+{q_pts} แต้ม)`")
        with q_col2:
          if st.button("🗑️", key=f"del_q_{active_char}_{q_id}"):
            cursor.execute("DELETE FROM quests WHERE id = ?", (q_id,))
            conn.commit()
            st.rerun()
    else:
      st.caption("ยังไม่มีภารกิจในระบบ")

  # 5. จัดการคลังรูปภาพ (Admin Only)
  elif (
      is_current_admin
      and sidebar_action == "🖼️ จัดการคลังรูปภาพ"
      and active_char
  ):
    st.markdown(f"### 🖼️ คลังรูป: {active_char}")

    cursor.execute(
        "SELECT id, photo FROM character_photos WHERE char_name = ?",
        (active_char,),
    )
    photos_in_db = cursor.fetchall()

    if photos_in_db:
      if st.button(
          "🗑️ ล้างรูปทั้งหมดของตัวละครนี้",
          key=f"clear_all_photos_{active_char}",
          use_container_width=True,
      ):
        cursor.execute(
            "DELETE FROM character_photos WHERE char_name = ?", (active_char,)
        )
        conn.commit()
        st.success(f"ลบรูปภาพทั้งหมดของ '{active_char}' เรียบร้อยแล้ว!")
        st.rerun()

    uploaded_gallery_photos = st.file_uploader(
        "อัปโหลดรูปภาพเข้าคลัง",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=f"gallery_upload_{active_char}",
    )

    if uploaded_gallery_photos:
      new_uploaded = False
      for photo in uploaded_gallery_photos:
        p_bytes = photo.getvalue()
        p_hash = hashlib.md5(p_bytes).hexdigest()

        cursor.execute(
            "SELECT COUNT(*) FROM character_photos WHERE char_name = ? AND photo_hash = ?",
            (active_char, p_hash),
        )
        if cursor.fetchone()[0] == 0:
          cursor.execute(
              "INSERT INTO character_photos (char_name, photo, photo_hash) VALUES (?, ?, ?)",
              (active_char, p_bytes, p_hash),
          )
          new_uploaded = True

      if new_uploaded:
        conn.commit()
        st.success("อัปโหลดรูปภาพเข้าคลังสำเร็จ!")
        st.rerun()

    st.markdown("---")
    cursor.execute(
        "SELECT id, photo FROM character_photos WHERE char_name = ?",
        (active_char,),
    )
    photos_in_db = cursor.fetchall()

    if photos_in_db:
      p_cols = st.columns(3)
      for idx, (p_id, p_blob) in enumerate(photos_in_db):
        with p_cols[idx % 3]:
          img_item = Image.open(io.BytesIO(p_blob))
          st.image(img_item, use_container_width=True)
          if st.button(f"🗑️ ลบรูป #{p_id}", key=f"del_photo_{active_char}_{p_id}"):
            cursor.execute("DELETE FROM character_photos WHERE id = ?", (p_id,))
            conn.commit()
            st.rerun()
    else:
      st.caption("ยังไม่มีรูปภาพในคลังของตัวละครนี้")

  # 6. จัดการผู้ใช้งานระบบ (Admin Only)
  elif is_current_admin and sidebar_action == "👥 จัดการผู้ใช้งานระบบ":
    st.markdown("### 👥 รายชื่อผู้ใช้งานทั้งหมด")
    cursor.execute("SELECT username, is_admin FROM users")
    users_list = cursor.fetchall()

    if users_list:
      for u_name_db, u_admin in users_list:
        with st.container(border=True):
          role_label = "🛡️ Admin" if u_admin == 1 else "👤 User"
          st.markdown(f"**ยูสเซอร์:** `{u_name_db}` ({role_label})")

          with st.form(f"manage_user_{u_name_db}"):
            new_p = st.text_input(
                "เปลี่ยนรหัสผ่านใหม่:", type="password", key=f"np_{u_name_db}"
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
                    (hash_password(new_p), u_name_db),
                )
                conn.commit()
                st.success(f"เปลี่ยนรหัสผ่านของ '{u_name_db}' สำเร็จ!")
                st.rerun()
              else:
                st.warning("กรุณากรอกรหัสผ่านใหม่")

            if btn_del_u:
              if (
                  u_name_db.lower() == "admin"
                  and current_user.lower() == u_name_db
              ):
                st.error("ไม่สามารถลบบัญชี Admin หลักของตัวเองได้")
              else:
                cursor.execute(
                    "DELETE FROM users WHERE username = ?", (u_name_db,)
                )
                cursor.execute(
                    "DELETE FROM messages WHERE username = ?", (u_name_db,)
                )
                cursor.execute(
                    "DELETE FROM character_status WHERE username = ?",
                    (u_name_db,),
                )
                cursor.execute(
                    "DELETE FROM user_quests WHERE username = ?", (u_name_db,)
                )
                conn.commit()
                st.success(f"ลบบัญชี '{u_name_db}' สำเร็จ!")
                st.rerun()
    else:
      st.info("ยังไม่มีผู้ใช้งานอื่นในระบบ")

  if not all_chars and (
      not is_current_admin
      and sidebar_action
      not in [
          "➕ สร้างตัวละครหลักใหม่ (Manual)",
          "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติ)",
          "🌐 ดึงข้อมูลตัวละครจากเว็บไซต์ด้วย AI",
      ]
  ):
    st.info("ยังไม่มีตัวละครในระบบ กรุณาสร้างตัวละครหลักก่อนครับ")


# ==========================================
# 🏠 หน้าแรก
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
      for u_name_db, u_admin in all_users:
        with st.container(border=True):
          role_label = (
              "🛡️ ผู้ดูแลระบบ (Admin)"
              if u_admin == 1
              else "👤 ผู้ใช้งานทั่วไป (User)"
          )
          st.markdown(f"### ชื่อผู้ใช้: `{u_name_db}` — *({role_label})*")

          with st.form(f"main_manage_user_{u_name_db}"):
            m_new_pass = st.text_input(
                "ตั้งรหัสผ่านใหม่:", type="password", key=f"mp_{u_name_db}"
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
                    (hash_password(m_new_pass), u_name_db),
                )
                conn.commit()
                st.success(f"อัปเดตรหัสผ่านของ '{u_name_db}' สำเร็จ!")
                st.rerun()
              else:
                st.warning("กรุณากรอกรหัสผ่านใหม่")

            if m_del:
              if u_name_db.lower() == "admin":
                st.error("ไม่อนุญาตให้ลบบัญชี Admin หลัก")
              else:
                cursor.execute(
                    "DELETE FROM users WHERE username = ?", (u_name_db,)
                )
                cursor.execute(
                    "DELETE FROM messages WHERE username = ?", (u_name_db,)
                )
                cursor.execute(
                    "DELETE FROM character_status WHERE username = ?",
                    (u_name_db,),
                )
                cursor.execute(
                    "DELETE FROM user_quests WHERE username = ?", (u_name_db,)
                )
                conn.commit()
                st.success(f"ลบบัญชี '{u_name_db}' สำเร็จ!")
                st.rerun()
    else:
      st.info("ยังไม่มีผู้ใช้งานในระบบ")

    st.stop()

  st.title("🔥 จักรวาลยอดนิยม & ตัวละครทั้งหมด")
  st.divider()

  if not all_chars:
    st.info("📭 ยังไม่มีตัวละครในระบบ กรุณาสร้างตัวละครหลักก่อนครับ")
  else:
    cols = st.columns(3)
    for idx, c_name in enumerate(all_chars):
      cursor.execute(
          "SELECT personality, avatar FROM characters WHERE name = ?", (c_name,)
      )
      c_data = cursor.fetchone()
      with cols[idx % 3]:
        with st.container(border=True):
          if c_data and c_data[1]:
            st.image(Image.open(io.BytesIO(c_data[1])), use_container_width=True)
          else:
            st.image(
                "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=500",
                use_container_width=True,
            )
          st.markdown(f"### 🌟 {c_name}")
          if st.button(
              f"✨ เริ่มแชทกับ {c_name}",
              key=f"b_{c_name}",
              use_container_width=True,
          ):
            st.session_state.current_char = c_name
            st.session_state.in_chat = True
            st.rerun()
  st.stop()


# ==========================================
# 💬 ห้องแชท
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
      ", ".join([f"{s[0]} ({s[1]}, นิสัย: {s[2]})" for s in subs_data])
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

  roleplay_instruction = f"""
คุณคือนักเขียนนิยายโรแมนติก/ดราม่าและผู้สวมบทบาทมืออาชีพ ตัวละครหลักชื่อ '{st.session_state.current_char}'
- ข้อมูลคาแรคเตอร์หลัก: {base_prompt}
- นิสัย: {char_personality}
- เรื่องราวพื้นหลัง (Lore): {char_lore}
- ตัวละครเสริมที่มีในเรื่อง: {supporting_text}

[ผู้สนทนา]: ชื่อ {u_name} | ประวัติ: {u_persona} | สรรพนามพูด: {u_pspeak} | สรรพนามบรรยาย: {u_pdesc} | เรียกผู้ใช้: {u_cspeak}
- ความสัมพันธ์ปัจจุบัน: "{current_rel_level}" (แต้มความชอบสะสม: {current_affection} แต้ม)

[กฎการเขียนบทบาท - เคร่งครัด]:
1. **จัดรูปแบบให้อ่านง่ายเป็นสัดส่วน**: 
   - ส่วนบรรยาย ท่าทาง สีหน้า แววตา และ **ความคิดในใจ (Inner Thoughts)** ให้เขียนไว้ในเครื่องหมายดอกจัน *...* (ระบบจะแสดงผลเป็นสีเทาอ่อนและตัวเอียงอัตโนมัติ)
   - ส่วนบทพูด (Dialogue) ให้อยู่ในเครื่องหมายคำพูดปกติ เช่น "{st.session_state.current_char}: \"...\""
2. **การมีส่วนร่วมของตัวละครเสริม**: ให้ดึงตัวละครเสริมที่มีในเรื่องเข้ามามีบทบาทพูดคุย โต้ตอบ หรือสร้างปฏิกิริยากับตัวละครหลักและผู้เล่นบ้างเพื่อเพิ่มความมีชีวิตชีวา
3. **บรรทัดสุดท้ายต้องเป็น JSON รูปแบบนี้เป๊ะๆ ห้ามพลาดเด็ดขาด**:
{{"score_change": [ตัวเลขเช่น 2 หรือ 5], "quest_update": [หมายเลขไอดีภารกิจที่ทำสำเร็จ หรือ null]}}
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

  col_av, col_title, col_reset = st.columns([1, 6, 2])
  with col_av:
    if char_avatar_img:
      st.image(char_avatar_img, width=60)
    else:
      st.image("https://api.iconify.design/lucide:user-round.svg", width=50)
  with col_title:
    st.markdown(
        f"### แชทกับ: `{st.session_state.current_char}` (ผู้ใช้: `{u_name}`)"
    )
  with col_reset:
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
          """
          DELETE FROM user_quests 
          WHERE username = ? AND quest_id IN (
              SELECT id FROM quests WHERE char_name = ?
          )
      """,
          (current_user, st.session_state.current_char),
      )

      new_m = get_random_first_msg(
          char_first_msg_raw, st.session_state.current_char
      )
      cursor.execute(
          "INSERT INTO messages (username, char_name, role, content) VALUES (?, ?, 'assistant', ?)",
          (current_user, st.session_state.current_char, new_m),
      )
      conn.commit()
      st.rerun()

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

    # 🛠️ ตรวจสอบคำสั่งพิเศษแบบมีเครื่องหมาย / นำหน้า
    is_cheat = False
    bot_response = ""
    score_change = 0
    completed_q_id = None

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
              f"*(สังเกตการณ์ระบบ: ไม่พบภารกิจหมายเลข #{completed_q_id} ในระบบ)*"
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
        eval_data = {"score_change": score_change, "quest_update": completed_q_id}
      else:
        message_placeholder.markdown("กำลังประพันธ์เรื่องราว...")

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
                eval_data = {"score_change": 2, "quest_update": None}
            else:
              bot_response = raw_text
              eval_data = {"score_change": 2, "quest_update": None}
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
              eval_data = {"score_change": 0, "quest_update": None}
        message_placeholder.markdown(bot_response)

      if bot_response:
        score_change = eval_data.get("score_change", score_change)
        completed_q_id = eval_data.get("quest_update", completed_q_id)

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
