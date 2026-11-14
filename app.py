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
        padding: 18px 22px !important;
        margin-bottom: 16px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border: 1px solid rgba(255,255,255,0.1);
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
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


# 🗄️ ฟังก์ชันฐานข้อมูล SQLite (รวมตาราง Memory ครบถ้วน)
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

  # 🧠 เพิ่มตารางความทรงจำระยะยาว
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


# 🔄 ระบบจัดการ Session และ Query Params เพื่อกันหลุดเวลา Refresh หน้าเว็บ
query_params = st.query_params

if "logged_in" not in st.session_state:
  if "user" in query_params:
    u_check = query_params["user"]
    cursor.execute("SELECT username, is_admin FROM users WHERE username = ?", (u_check,))
    row = cursor.fetchone()
    if row:
      st.session_state.logged_in = True
      st.session_state.username = row[0]
      st.session_state.is_admin = bool(1 if row[0].lower() == "admin" else row[1])
    else:
      st.session_state.logged_in = False
      st.session_state.username = ""
      st.session_state.is_admin = False
  else:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.is_admin = False

if "in_chat" not in st.session_state:
  st.session_state.in_chat = False


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
            st.query_params["user"] = l_user
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
            st.success("สมัครสมาชิกสำเร็จ! กรุณากดไปที่แท็บ 'เข้าสู่ระบบ'")
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
u_name, u_persona, u_pspeak, u_pdesc, u_cspeak, u_cdesc = p_row if p_row else (current_user, "", "", "", "", "")

cursor.execute("SELECT name FROM characters")
all_chars = [row[0] for row in cursor.fetchall()]

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
        with st.spinner("AI กำลังสร้างบทบาท..."):
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
              cursor.execute(
                  """
                    UPDATE users 
                    SET user_name = ?, user_persona = ?, pronoun_speak = ?, pronoun_desc = ?, call_speak = ?, call_desc = ? 
                    WHERE username = ?
                """,
                  (
                      p_data.get("user_name", u_name),
                      p_data.get("user_persona", u_persona),
                      p_data.get("pronoun_speak", u_pspeak),
                      p_data.get("pronoun_desc", u_pdesc),
                      p_data.get("call_speak", u_cspeak),
                      p_data.get("call_desc", u_cdesc),
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
        edit_cspeak = st.text_input("ตัวละครเรียก (พูด):", value=u_cspeak)
      with col_c2:
        edit_cdesc = st.text_input("ตัวละครเรียก (บรรยาย):", value=u_cdesc)

      if st.form_submit_button("💾 บันทึกบทบาท", use_container_width=True):
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
    if "user" in st.query_params:
      del st.query_params["user"]
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
      "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติ)",
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

  # (เมนู Admin Action ต่างๆ คงเดิมตามโครงสร้างของคุณ)
  if is_current_admin and sidebar_action == "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติ)":
    st.markdown("### ✨ สร้างตัวละครหลักด้วย AI")
    with st.form("ai_gen_char_form"):
      ai_target_name = st.text_input("ชื่อดารา หรือ ตัวละครหลัก:")
      if st.form_submit_button("🚀 ให้ AI สร้างตัวละครนี้แบบครบชุด", use_container_width=True) and ai_target_name:
        with st.spinner("AI กำลังสร้าง..."):
          prompt_gen = f"สร้างข้อมูล JSON ของ '{ai_target_name}' สำหรับ AI Roleplay (name, prompt, personality, lore, first_messages, sub_name, sub_prompt, sub_personality, quest_desc)"
          response = client.models.generate_content(model=model_name, contents=prompt_gen)
          raw_res = response.text.strip()
          if "{" in raw_res and "}" in raw_res:
            char_info = json.loads(raw_res[raw_res.find("{"):raw_res.rfind("}")+1])
            c_name = char_info.get("name", ai_target_name)
            cursor.execute("INSERT OR REPLACE INTO characters (name, prompt, personality, lore, first_message, avatar) VALUES (?, ?, ?, ?, ?, ?)",
                (c_name, char_info.get("prompt",""), char_info.get("personality",""), char_info.get("lore",""), json.dumps(char_info.get("first_messages",["สวัสดี"]), ensure_ascii=False), None))
            conn.commit()
            st.session_state.current_char = c_name
            st.session_state.in_chat = True
            st.success("สร้างสำเร็จ!")
            st.rerun()


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
# 💬 ห้องแชท (รวมระบบ Memory Vault & Novelization ครบถ้วน)
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

  # 🧠 ดึงความทรงจำระยะยาวมาใช้
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
คุณคือนักเขียนนิยายโรแมนติก/ดราม่ามืออาชีพชั้นเยี่ยม และผู้สวมบทบาทตัวละคร '{st.session_state.current_char}'
- ข้อมูลคาแรคเตอร์หลัก: {base_prompt}
- นิสัย: {char_personality}
- เรื่องราวพื้นหลัง (Lore): {char_lore}
- ตัวละครเสริมที่มีในเรื่อง: {supporting_text}

[ความทรงจำระยะยาวของเรื่องราว (Long-term Memory Vault)]:
"{long_term_memory}"

[ผู้สนทนา]: ชื่อ {u_name} | ประวัติ: {u_persona} | สรรพนามพูด: {u_pspeak} | สรรพนามบรรยาย: {u_pdesc} | เรียกผู้ใช้: {u_cspeak}
- ความสัมพันธ์ปัจจุบัน: "{current_rel_level}" (แต้มความชอบสะสม: {current_affection} แต้ม)

[กฎการเขียนบทบาทระดับพรีเมียม]:
1. **การบรรยายเชิงลึก**: บรรยายท่าทาง แววตา จิตวิทยา บรรยากาศรอบตัวอย่างประณีต
2. **จัดย่อหน้าและเว้นบรรทัดให้อ่านง่าย**: เคาะขึ้นบรรทัดใหม่แบ่งฉากอย่างชัดเจน ห้ามเขียนติดเป็นพารากราฟยาว
3. **รูปแบบสัดส่วน**: 
   - บรรยาย ท่าทาง สีหน้า ความคิด ให้كتبไว้ในเครื่องหมาย *...* (แสดงผลสีเทาอ่อน ตัวตรงปกติ)
   - บทพูด ให้ใช้เครื่องหมายคำพูดปกติ "{st.session_state.current_char}: \"...\""
4. **บรรทัดสุดท้ายต้องเป็น JSON รูปแบบนี้เป๊ะๆ ห้ามพลาดเด็ดขาด**:
{{"score_change": 2, "quest_update": null, "memory_update": "[สรุปเหตุการณ์สำคัญสั้นๆ 1 ประโยค]"}}
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
    st.markdown(f"### แชทกับ: `{st.session_state.current_char}`")
  with col_reset:
    col_r1, col_r2 = st.columns(2)
    with col_r1:
      if st.button("🔄 รีเซ็ต", use_container_width=True):
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
      with st.popover("📖 เมนู", use_container_width=True):
        if st.button("📖 แปลงแชทเป็นนิยาย", use_container_width=True):
          with st.spinner("กำลังแปลงแชทเป็นตอนนิยาย..."):
            chat_log_text = "\n".join([f"{m['role']}: {m['content']}" for m in current_messages])
            novel_res = client.models.generate_content(model=model_name, contents=f"จงแปลงบทสนทนานี้เป็นตอนนิยายบรรยาย:\n{chat_log_text}")
            st.markdown("### 📜 ตอนนิยายของคุณ:")
            st.write(novel_res.text)

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
              f'<div class="affection-badge">💖 {current_rel_level} | คะแนน: {current_affection} แต้ม</div>',
              unsafe_allow_html=True,
          )
        with col_pop:
          with st.popover("🎯 ภารกิจ", use_container_width=True):
            st.markdown("#### 🎯 ภารกิจปัจจุบัน")
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
                status_icon = "✅" if is_comp else "⏳"
                st.markdown(f"- {status_icon} **[#{q_id}] {desc}** *(+{pts} แต้ม)*")
            else:
              st.caption("ยังไม่มีภารกิจ")

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

    with st.chat_message(
        "assistant", avatar=char_avatar_img if char_avatar_img else "✨"
    ):
      message_placeholder = st.empty()
      message_placeholder.markdown("กำลังประพันธ์เนื้อเรื่อง...")

      bot_response = ""
      eval_data = {}
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
            config={"system_instruction": roleplay_instruction},
        )
        response = chat.send_message(user_input)
        raw_t = response.text

        if "{" in raw_t and "}" in raw_t:
          clean_t = raw_t[: raw_t.find("{")].strip()
          json_str = raw_t[raw_t.find("{") : raw_t.rfind("}") + 1]
          try:
            eval_data = json.loads(json_str)
            bot_response = clean_t
          except Exception:
            bot_response = raw_t.strip()
            eval_data = {"score_change": 2, "quest_update": None, "memory_update": ""}
        else:
          bot_response = raw_t.strip()
          eval_data = {"score_change": 2, "quest_update": None, "memory_update": ""}
      except Exception as e:
        bot_response = f"*เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}*"
        eval_data = {"score_change": 0, "quest_update": None, "memory_update": ""}

      score_change = eval_data.get("score_change", 2)
      completed_q_id = eval_data.get("quest_update", None)
      memory_update = eval_data.get("memory_update", "")

      # บันทึกความทรงจำระยะยาว
      if memory_update:
        updated_memory_vault = (
            f"{long_term_memory} -> {memory_update}"
            if long_term_memory != "ยังไม่มีเหตุการณ์สำคัญสะสม เริ่มต้นเรื่องราวใหม่"
            else memory_update
        )
        cursor.execute(
            "INSERT OR REPLACE INTO novel_memories (username, char_name, memory_summary) VALUES (?, ?, ?)",
            (current_user, st.session_state.current_char, updated_memory_vault),
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
          (updated_score, new_lvl, current_user, st.session_state.current_char),
      )

      attached_photo_bytes = None
      cursor.execute(
          "SELECT photo FROM character_photos WHERE char_name = ?",
          (st.session_state.current_char,),
      )
      photos = cursor.fetchall()
      if photos and random.random() < 0.30:
        attached_photo_bytes = random.choice(photos)[0]
        st.image(Image.open(io.BytesIO(attached_photo_bytes)), width=280)

      message_placeholder.markdown(bot_response)
      cursor.execute(
          "INSERT INTO messages (username, char_name, role, content, image_blob) VALUES (?, ?, 'assistant', ?, ?)",
          (current_user, st.session_state.current_char, bot_response, attached_photo_bytes),
      )
      conn.commit()
      st.rerun()
