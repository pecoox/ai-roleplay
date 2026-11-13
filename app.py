from google import genai
import streamlit as st
import sqlite3
import time
from PIL import Image
import io

st.set_page_config(
    page_title="AI Roleplay - Persistent Storage",
    page_icon="💾",
    layout="centered",
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
    </style>
""",
    unsafe_allow_html=True,
)


# 🗄️ ฟังก์ชันจัดการฐานข้อมูล SQLite (เพื่อให้ข้อมูลไม่หายตอนรีเฟรช)
def init_db():
  conn = sqlite3.connect("roleplay_data.db", check_same_thread=False)
  cursor = conn.cursor()
  # สร้างตารางเก็บตัวละคร
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            name TEXT PRIMARY KEY,
            prompt TEXT,
            avatar BLOB
        )
    """)
  # สร้างตารางเก็บประวัติแชท
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            char_name TEXT,
            role TEXT,
            content TEXT
        )
    """)
  conn.commit()
  return conn


conn = init_db()
cursor = conn.cursor()

# ตรวจสอบว่ามีตัวละครเริ่มต้นไหม ถ้ายังไม่มีให้ใส่ตัวละคร 'มาร์ค ต้วน' ลงไป
cursor.execute("SELECT COUNT(*) FROM characters")
if cursor.fetchone()[0] == 0:
  cursor.execute(
      "INSERT INTO characters (name, prompt, avatar) VALUES (?, ?, ?)",
      (
          "มาร์ค ต้วน",
          (
              "คุณคือ มาร์ค ต้วน (Mark Tuan) ศิลปินหนุ่มตัวจริง"
              " นิสัยอบอุ่น เป็นกันเอง และขี้เล่น"
          ),
          None,
      ),
  )
  conn.commit()

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

# จัดการชื่อตัวละครปัจจุบันใน session_state
if "current_char" not in st.session_state:
  cursor.execute("SELECT name FROM characters LIMIT 1")
  row = cursor.fetchone()
  st.session_state.current_char = row[0] if row else "มาร์ค ต้วน"

# แผงควบคุมด้านข้าง (Sidebar)
with st.sidebar:
  st.header("⚙️ ควบคุมระบบ")
  chat_mode = st.radio(
      "เลือกสไตล์การคุย:", ["💬 แชทสั้นๆ เป็นธรรมชาติ", "📖 โหมดนิยายบรรยายยาว"]
  )

  st.divider()
  st.subheader("✨ สร้างตัวละครใหม่ + รูป")
  new_name = st.text_input("ชื่อตัวละคร:", placeholder="เช่น แฟนหนุ่ม, ไอดอล...")
  new_prompt = st.text_area(
      "คาแรคเตอร์:", placeholder="คุณคือเพื่อนสนิทขี้อ้อน...", height=80
  )
  new_avatar = st.file_uploader(
      "อัปโหลดรูปโปรไฟล์ตัวละคร", type=["png", "jpg", "jpeg"]
  )

  if st.button("🚀 สร้างตัวละคร", use_container_width=True):
    if new_name and new_prompt:
      cursor.execute("SELECT name FROM characters WHERE name = ?", (new_name,))
      if not cursor.fetchone():
        avatar_bytes = (
            new_avatar.getvalue() if new_avatar is not None else None
        )
        cursor.execute(
            "INSERT INTO characters (name, prompt, avatar) VALUES (?, ?, ?)",
            (new_name, new_prompt, avatar_bytes),
        )
        conn.commit()
        st.session_state.current_char = new_name
        st.success(f"สร้าง '{new_name}' สำเร็จ!")
        st.rerun()
      else:
        st.warning("ชื่อนี้มีอยู่แล้วในระบบ")
    else:
      st.warning("กรุณากรอกชื่อและคาแรคเตอร์ให้ครบ")

  st.divider()
  st.subheader("👥 เลือกตัวละคร")
  cursor.execute("SELECT name FROM characters")
  char_list = [row[0] for row in cursor.fetchall()]

  if st.session_state.current_char not in char_list and char_list:
    st.session_state.current_char = char_list[0]

  selected_char = st.selectbox(
      "สลับแชทกับ:",
      char_list,
      index=(
          char_list.index(st.session_state.current_char)
          if st.session_state.current_char in char_list
          else 0
      ),
  )

  if selected_char != st.session_state.current_char:
    st.session_state.current_char = selected_char
    st.rerun()

  # ปุ่มลบตัวละคร
  if len(char_list) > 1:
    if st.button("🗑️ ลบตัวละครนี้", use_container_width=True):
      cursor.execute(
          "DELETE FROM characters WHERE name = ?",
          (st.session_state.current_char,),
      )
      cursor.execute(
          "DELETE FROM messages WHERE char_name = ?",
          (st.session_state.current_char,),
      )
      conn.commit()
      cursor.execute("SELECT name FROM characters LIMIT 1")
      st.session_state.current_char = cursor.fetchone()[0]
      st.rerun()
  else:
    st.caption("ℹ️ ต้องมีตัวละครอย่างน้อย 1 ตัว")

# ดึงข้อมูลตัวละครปัจจุบันจากฐานข้อมูล
cursor.execute(
    "SELECT prompt, avatar FROM characters WHERE name = ?",
    (st.session_state.current_char,),
),
char_data = cursor.fetchone()
base_prompt = char_data[0]
char_avatar_blob = char_data[1]

# แปลง BLOB เป็นรูปภาพสำหรับแสดงผล
char_avatar_img = None
if char_avatar_blob:
  char_avatar_img = Image.open(io.BytesIO(char_avatar_blob))

# กำหนด System Instruction ตามโหมด
if "นิยาย" in chat_mode:
  roleplay_instruction = (
      f"{base_prompt}\n\n[กฎการตอบ]:\n"
      "1. เขียนตอบสไตล์นิยายบรรยาย มีท่าทาง สีหน้า ความรู้สึก (ใช้เครื่องหมาย *"
      " ครอบการกระทำ)\n"
      "2. สวมบทบาท 100% ห้ามบอกว่าเป็น AI\n"
      "3. เมื่อจบตอน ให้ตั้งคำถามหรือเปิดฉากเพื่อให้ผู้ใช้เลือกตอบต่อ"
  )
  temp_val = 1.1
else:
  roleplay_instruction = (
      f"{base_prompt}\n\n[กฎการตอบ]:\n"
      "1. พูดจาภาษาคนธรรมดา เป็นธรรมชาติเหมือนแชทไลน์/ไอจี\n"
      "2. ห้ามใช้คำพูดเชิงบอทหรือคำทางการ\n"
      "3. สวมบทบาท 100% ห้ามหลุดคาแรคเตอร์"
  )
  temp_val = 0.9

# ดึงประวัติแชทของตัวละครนี้จากฐานข้อมูล
cursor.execute(
    "SELECT role, content FROM messages WHERE char_name = ?",
    (st.session_state.current_char,),
)
current_messages = [{"role": row[0], "content": row[1]} for row in cursor.fetchall()]

# แสดงหัวข้อและรูปโปรไฟล์ตัวละครด้านบนสุดของห้องแชท
col_av, col_title = st.columns([1, 6])
with col_av:
  if char_avatar_img:
    st.image(char_avatar_img, width=60)
  else:
    st.image("https://api.iconify.design/lucide:user-round.svg", width=50)
with col_title:
  st.markdown(f"### ห้องแชทส่วนตัวกับ: `{st.session_state.current_char}`")
st.divider()

# แสดงประวัติแชท
for message in current_messages:
  if message["role"] == "user":
    with st.chat_message("user", avatar="👤"):
      st.markdown(message["content"])
  else:
    avatar_icon = char_avatar_img if char_avatar_img else "✨"
    with st.chat_message("assistant", avatar=avatar_icon):
      st.markdown(message["content"])

# ช่องพิมพ์ข้อความ
if user_input := st.chat_input(
    f"ส่งข้อความหา {st.session_state.current_char}..."
):
  # บันทึกข้อความผู้ใช้ลงฐานข้อมูล
  cursor.execute(
      "INSERT INTO messages (char_name, role, content) VALUES (?, ?, ?)",
      (st.session_state.current_char, "user", user_input),
  )
  conn.commit()

  with st.chat_message("user", avatar="👤"):
    st.markdown(user_input)

  avatar_icon = char_avatar_img if char_avatar_img else "✨"
  with st.chat_message("assistant", avatar=avatar_icon):
    message_placeholder = st.empty()
    message_placeholder.markdown("กำลังพิมพ์...")

    bot_response = None
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
        bot_response = response.text
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
            bot_response = None
            message_placeholder.error(f"เกิดข้อผิดพลาด: {error_msg}")

    if bot_response:
      message_placeholder.markdown(bot_response)
      # บันทึกข้อความบอทลงฐานข้อมูล
      cursor.execute(
          "INSERT INTO messages (char_name, role, content) VALUES (?, ?, ?)",
          (st.session_state.current_char, "assistant", bot_response),
      )
      conn.commit()
