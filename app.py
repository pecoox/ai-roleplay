from google import genai
import streamlit as st
import sqlite3
import time
from PIL import Image
import io
import random

st.set_page_config(
    page_title="AI Roleplay - Character Gallery",
    page_icon="🖼️",
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


# 🗄️ ฟังก์ชันฐานข้อมูล SQLite
def init_db():
  conn = sqlite3.connect("roleplay_data.db", check_same_thread=False)
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            name TEXT PRIMARY KEY,
            prompt TEXT,
            lore TEXT,
            avatar BLOB
        )
    """)
  cursor.execute("PRAGMA table_info(characters)")
  char_columns = [col[1] for col in cursor.fetchall()]
  if "lore" not in char_columns:
    cursor.execute("ALTER TABLE characters ADD COLUMN lore TEXT")

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS character_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            char_name TEXT,
            photo BLOB
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            char_name TEXT,
            role TEXT,
            content TEXT,
            image_blob BLOB
        )
    """)
  cursor.execute("PRAGMA table_info(messages)")
  msg_columns = [col[1] for col in cursor.fetchall()]
  if "image_blob" not in msg_columns:
    cursor.execute("ALTER TABLE messages ADD COLUMN image_blob BLOB")

  conn.commit()
  return conn


conn = init_db()
cursor = conn.cursor()

# ตรวจสอบตัวละครเริ่มต้น
cursor.execute("SELECT COUNT(*) FROM characters")
if cursor.fetchone()[0] == 0:
  cursor.execute(
      "INSERT INTO characters (name, prompt, lore, avatar) VALUES (?, ?, ?, ?)",
      (
          "มาร์ค ต้วน",
          (
              "คุณคือ มาร์ค ต้วน (Mark Tuan) ศิลปินหนุ่มตัวจริง"
              " นิสัยอบอุ่น เป็นกันเอง และขี้เล่น"
          ),
          (
              "เป็นเพื่อนสนิทที่รู้จักกันมานาน ชอบแอบเปย์ของกินอร่อยๆ"
              " และคอยเป็นห่วงเสมอ"
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
  st.markdown("### 🛠️ สร้างตัวละครใหม่")

  with st.expander("📌 เปิดฟอร์มสร้างตัวละคร", expanded=False):
    new_name = st.text_input("ชื่อตัวละคร:", placeholder="เช่น เทพเจ้าแห่งแม่น้ำ...")
    new_prompt = st.text_area(
        "คาแรคเตอร์สั้นๆ:",
        placeholder="คุณคือเทพเจ้าขี้เล่น...",
        height=60,
    )
    new_lore = st.text_area(
        "ข้อมูลเชิงลึก (Lore/ประวัติ):",
        placeholder="เนื้อเรื่องย่อ ความสัมพันธ์...",
        height=70,
    )
    new_avatar = st.file_uploader(
        "รูปโปรไฟล์ตัวละคร",
        type=["png", "jpg", "jpeg", "webp"],
        key="new_char_avatar_upload",
    )

    if st.button("🚀 บันทึกสร้างตัวละคร", use_container_width=True):
      if new_name and new_prompt:
        cursor.execute("SELECT name FROM characters WHERE name = ?", (new_name,))
        if not cursor.fetchone():
          avatar_bytes = (
              new_avatar.getvalue() if new_avatar is not None else None
          )
          cursor.execute(
              "INSERT INTO characters (name, prompt, lore, avatar) VALUES (?, ?, ?, ?)",
              (new_name, new_prompt, new_lore, avatar_bytes),
          )
          conn.commit()
          st.session_state.current_char = new_name
          st.success(f"สร้าง '{new_name}' สำเร็จ!")
          st.rerun()
        else:
          st.warning("ชื่อนี้มีอยู่แล้วในระบบ")
      else:
        st.warning("⚠️ กรุณากรอกชื่อและคาแรคเตอร์ให้ครบ")

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

  # 🖼️ คลังรูปภาพประจำตัวละคร (แก้ไขคีย์ให้แยกตามชื่อตัวละคร ป้องกันลูปค้าง)
  st.divider()
  st.subheader(f"🖼️ คลังรูปของ: {st.session_state.current_char}")
  gallery_key = f"gallery_upload_{st.session_state.current_char}"
  uploaded_gallery_photos = st.file_uploader(
      "อัปโหลดรูปภาพเข้าคลัง (ให้ตัวละครสุ่มส่ง)",
      type=["png", "jpg", "jpeg", "webp"],
      accept_multiple_files=True,
      key=gallery_key,
  )

  # ตรวจสอบการอัปโหลดรูปเข้าคลังแบบปลอดภัยไม่ให้เกิดลูป
  if uploaded_gallery_photos:
    # เช็กว่ารูปเหล่านี้เคยถูกบันทึกไปหรือยังเพื่อป้องกันบันทึกซ้ำซ้อนตอนรีรัน
    cursor.execute(
        "SELECT COUNT(*) FROM character_photos WHERE char_name = ?",
        (st.session_state.current_char,),
    )
    current_db_count = cursor.fetchone()[0]

    if len(uploaded_gallery_photos) != current_db_count:
      # ล้างรูปเก่าแล้วใส่ชุดใหม่เข้าไปทั้งหมด
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

  cursor.execute(
      "SELECT COUNT(*) FROM character_photos WHERE char_name = ?",
      (st.session_state.current_char,),
  )
  photo_count = cursor.fetchone()[0]
  st.caption(f"📁 รูปในคลังตอนนี้: {photo_count} รูป")

  if len(char_list) > 1:
    st.divider()
    if st.button("🗑️ ลบตัวละครนี้", use_container_width=True):
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
      conn.commit()
      cursor.execute("SELECT name FROM characters LIMIT 1")
      st.session_state.current_char = cursor.fetchone()[0]
      st.rerun()

# ดึงข้อมูลตัวละครปัจจุบัน
cursor.execute(
    "SELECT prompt, lore, avatar FROM characters WHERE name = ?",
    (st.session_state.current_char,),
)
char_data = cursor.fetchone()
base_prompt = char_data[0] if char_data and char_data[0] else ""
char_lore = char_data[1] if char_data and char_data[1] else ""
char_avatar_blob = char_data[2] if char_data else None

char_avatar_img = None
if char_avatar_blob:
  char_avatar_img = Image.open(io.BytesIO(char_avatar_blob))

full_system_prompt = f"{base_prompt}\n\n[ข้อมูลและประวัติเชิงลึกของตัวละคร (Lore)]:\n{char_lore if char_lore else 'ไม่มีข้อมูลพิเศษ'}"

if "นิยาย" in chat_mode:
  roleplay_instruction = (
      f"{full_system_prompt}\n\n[กฎการตอบ]:\n"
      "1. เขียนตอบสไตล์นิยายบรรยาย มีท่าทาง สีหน้า ความรู้สึก (ใช้เครื่องหมาย *"
      " ครอบการกระทำ)\n"
      "2. สวมบทบาท 100% ห้ามบอกว่าเป็น AI\n"
      "3. เมื่อจบตอน ให้ตั้งคำถามหรือเปิดฉากเพื่อให้ผู้ใช้เลือกตอบต่อ"
  )
  temp_val = 1.1
else:
  roleplay_instruction = (
      f"{full_system_prompt}\n\n[กฎการตอบ]:\n"
      "1. พูดจาภาษาคนธรรมดา เป็นธรรมชาติเหมือนแชทไลน์/ไอจี\n"
      "2. ห้ามใช้คำพูดเชิงบอทหรือคำทางการ\n"
      "3. สวมบทบาท 100% ห้ามหลุดคาแรคเตอร์"
  )
  temp_val = 0.9

# ดึงข้อความแชท
cursor.execute(
    "SELECT role, content, image_blob FROM messages WHERE char_name = ?",
    (st.session_state.current_char,),
)
current_messages = []
for row in cursor.fetchall():
  img_obj = None
  if row[2]:
    img_obj = Image.open(io.BytesIO(row[2]))
  current_messages.append(
      {"role": row[0], "content": row[1], "image": img_obj}
  )

# แสดงหัวข้อและรูปโปรไฟล์ตัวละคร
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
      if message["image"]:
        st.image(message["image"], width=280)

# ช่องพิมพ์ข้อความ
if user_input := st.chat_input(
    f"ส่งข้อความหา {st.session_state.current_char}..."
):
  cursor.execute(
      "INSERT INTO messages (char_name, role, content, image_blob) VALUES (?, ?,"
      " ?, ?)",
      (st.session_state.current_char, "user", user_input, None),
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
        bot_response = response.text

        # สุ่มดึงรูปจากคลังรูปภาพของตัวละครนี้มาส่ง (30%)
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
            bot_response = None
            message_placeholder.error(f"เกิดข้อผิดพลาด: {error_msg}")

    if bot_response:
      message_placeholder.markdown(bot_response)
      display_img = None
      if attached_photo_bytes:
        display_img = Image.open(io.BytesIO(attached_photo_bytes))
        st.image(display_img, width=280)

      cursor.execute(
          "INSERT INTO messages (char_name, role, content, image_blob) VALUES (?,"
          " ?, ?, ?)",
          (
              st.session_state.current_char,
              "assistant",
              bot_response,
              attached_photo_bytes,
          ),
      )
      conn.commit()
