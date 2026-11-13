from google import genai
import streamlit as st
import sqlite3
import time
from PIL import Image
import io
import random
import json

st.set_page_config(
    page_title="AI Roleplay - Affection & Quests Studio",
    page_icon="💖",
    layout="centered",
)

# 🎨 ดีไซน์ CSS พรีเมียมและแถบสถานะความชอบ
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
    
    /* กล่องแสดงสถานะความชอบ */
    .affection-box {
        background: linear-gradient(135deg, rgba(255,105,180,0.1), rgba(138,43,226,0.1));
        border: 1px solid rgba(255,105,180,0.3);
        border-radius: 12px;
        padding: 12px 16px;
        margin-bottom: 15px;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# 🗄️ ฟังก์ชันฐานข้อมูล SQLite รองรับระบบความชอบและภารกิจ
def init_db():
  conn = sqlite3.connect("roleplay_data.db", check_same_thread=False)
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            name TEXT PRIMARY KEY,
            prompt TEXT,
            personality TEXT,
            lore TEXT,
            supporting TEXT,
            first_message TEXT,
            avatar BLOB
        )
    """)

  # ตารางเก็บสถานะความสัมพันธ์และความชอบของผู้ใช้กับตัวละครแต่ละตัว
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS character_status (
            char_name TEXT PRIMARY KEY,
            affection_score INTEGER DEFAULT 0,
            relationship_level TEXT DEFAULT 'คนแปลกหน้า'
        )
    """)

  # ตารางเก็บภารกิจ (Quests)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            char_name TEXT,
            task_desc TEXT,
            is_completed INTEGER DEFAULT 0,
            reward_points INTEGER DEFAULT 10
        )
    """)

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
  conn.commit()
  return conn


conn = init_db()
cursor = conn.cursor()

# ตรวจสอบตัวละครเริ่มต้น (มาร์ค ต้วน)
cursor.execute("SELECT COUNT(*) FROM characters")
if cursor.fetchone()[0] == 0:
  cursor.execute(
      """
        INSERT INTO characters (name, prompt, personality, lore, supporting, first_message, avatar) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
      (
          "มาร์ค ต้วน",
          "คุณคือ มาร์ค ต้วน (Mark Tuan) ศิลปินหนุ่มตัวจริง",
          "อบอุ่น เป็นกันเอง ขี้เล่น และใส่ใจแฟนคลับ",
          "เป็นคนแปลกหน้าที่เพิ่งบังเอิญเจอกันที่ร้านกาแฟ",
          "ผู้จัดการส่วนตัว",
          "อ้าว... ขอโทษทีครับ เดินชนเมื่อกี้เจ็บตรงไหนหรือเปล่าครับ? (มองหน้าด้วยความสงสัยนิดๆ)",
          None,
      ),
  )
  # เพิ่มสถานะความชอบเริ่มต้น
  cursor.execute(
      """
        INSERT OR IGNORE INTO character_status (char_name, affection_score, relationship_level) 
        VALUES (?, ?, ?)
    """,
      ("มาร์ค ต้วน", 5, "คนแปลกหน้า"),
  )

  # เพิ่มภารกิจเริ่มต้น
  cursor.execute(
      """
        INSERT INTO quests (char_name, task_desc, is_completed, reward_points) 
        VALUES (?, ?, ?, ?)
    """,
      (
          "มาร์ค ต้วน",
          "แนะนำตัวให้เขารู้จักอย่างเป็นทางการ",
          0,
          15,
      ),
  )
  cursor.execute(
      """
        INSERT INTO quests (char_name, task_desc, is_completed, reward_points) 
        VALUES (?, ?, ?, ?)
    """,
      (
          "มาร์ค ต้วน",
          "ทำให้เขายิ้มหรือหัวเราะออกมาให้ได้",
          0,
          20,
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
    new_name = st.text_input("ชื่อตัวละคร:", placeholder="เช่น อาจารย์หนุ่ม, เพื่อนร่วมงาน...")
    new_prompt = st.text_area(
        "คาแรคเตอร์หลัก (Prompt):",
        placeholder="คุณคือ...",
        height=60,
    )
    new_personality = st.text_area(
        "🧠 บุคลิก/นิสัย:",
        placeholder="เช่น เข้มงวด, เป็นกันเอง, สุภาพ...",
        height=60,
    )
    new_lore = st.text_area(
        "📖 เรื่องราวพื้นหลัง (Background/Lore):",
        placeholder="สถานะเริ่มต้น ความสัมพันธ์...",
        height=70,
    )
    new_supporting = st.text_area(
        "👥 ตัวละครสนับสนุน:", placeholder="คนรอบข้าง...", height=60
    )
    new_first_msg = st.text_area(
        "💬 ข้อความแรก (Greeting Message):",
        placeholder="ประโยคแรกที่ทักทาย...",
        height=60,
    )
    new_avatar = st.file_uploader(
        "รูปโปรไฟล์ตัวละคร",
        type=["png", "jpg", "jpeg", "webp"],
        key="new_avatar_up",
    )

    # ช่องใส่ภารกิจเริ่มต้นตอนสร้างตัวละคร
    st.markdown("---")
    st.markdown("**🎯 กำหนดภารกิจเริ่มต้น (2 ภารกิจ)**")
    q1 = st.text_input(
        "ภารกิจที่ 1:", placeholder="เช่น ทักทายเขาอย่างสุภาพ"
    )
    q2 = st.text_input(
        "ภารกิจที่ 2:", placeholder="เช่น ชวนคุยเรื่องงานหรือเรื่องทั่วไป"
    )

    if st.button("🚀 บันทึกสร้างตัวละคร", use_container_width=True):
      if new_name and new_prompt:
        cursor.execute("SELECT name FROM characters WHERE name = ?", (new_name,))
        if not cursor.fetchone():
          avatar_bytes = (
              new_avatar.getvalue() if new_avatar is not None else None
          )
          default_first_msg = (
              new_first_msg
              if new_first_msg
              else f"สวัสดีครับ ฉันชื่อ {new_name}"
          )

          cursor.execute(
              """
                INSERT INTO characters (name, prompt, personality, lore, supporting, first_message, avatar) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
              (
                  new_name,
                  new_prompt,
                  new_personality,
                  new_lore,
                  new_supporting,
                  default_first_msg,
                  avatar_bytes,
              ),
          )

          # สร้างสถานะความชอบเริ่มต้น
          cursor.execute(
              """
                INSERT INTO character_status (char_name, affection_score, relationship_level) 
                VALUES (?, ?, ?)
            """,
              (new_name, 0, "คนแปลกหน้า"),
          )

          # บันทึกภารกิจ
          if q1:
            cursor.execute(
                "INSERT INTO quests (char_name, task_desc, is_completed, reward_points) VALUES (?, ?, 0, 15)",
                (new_name, q1),
            )
          if q2:
            cursor.execute(
                "INSERT INTO quests (char_name, task_desc, is_completed, reward_points) VALUES (?, ?, 0, 20)",
                (new_name, q2),
            )

          cursor.execute(
              "INSERT INTO messages (char_name, role, content, image_blob)"
              " VALUES (?, ?, ?, ?)",
              (new_name, "assistant", default_first_msg, None),
          )

          conn.commit()
          st.session_state.current_char = new_name
          st.success(f"สร้าง '{new_name}' สำเร็จ!")
          st.rerun()
        else:
          st.warning("ชื่อนี้มีอยู่แล้วในระบบ")
      else:
        st.warning("⚠️ กรุณากรอกชื่อและคาแรคเตอร์หลักให้ครบ")

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

  # คลังรูปภาพประจำตัวละคร
  st.divider()
  st.subheader(f"🖼️ คลังรูปของ: {st.session_state.current_char}")
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
      cursor.execute(
          "DELETE FROM character_status WHERE char_name = ?",
          (st.session_state.current_char,),
      )
      cursor.execute(
          "DELETE FROM quests WHERE char_name = ?",
          (st.session_state.current_char,),
      )
      conn.commit()
      cursor.execute("SELECT name FROM characters LIMIT 1")
      st.session_state.current_char = cursor.fetchone()[0]
      st.rerun()

# ดึงข้อมูลตัวละครปัจจุบัน
cursor.execute(
    """
    SELECT prompt, personality, lore, supporting, first_message, avatar 
    FROM characters WHERE name = ?
""",
    (st.session_state.current_char,),
)
char_data = cursor.fetchone()

base_prompt = char_data[0] if char_data and char_data[0] else ""
char_personality = char_data[1] if char_data and char_data[1] else "ไม่มีข้อมูล"
char_lore = char_data[2] if char_data and char_data[2] else "ไม่มีข้อมูล"
char_supporting = char_data[3] if char_data and char_data[3] else "ไม่มีข้อมูล"
char_first_msg = char_data[4] if char_data and char_data[4] else ""
char_avatar_blob = char_data[5] if char_data else None

char_avatar_img = None
if char_avatar_blob:
  char_avatar_img = Image.open(io.BytesIO(char_avatar_blob))

# ดึงสถานะความชอบ
cursor.execute(
    "SELECT affection_score, relationship_level FROM character_status WHERE char_name = ?",
    (st.session_state.current_char,),
)
status_row = cursor.fetchone()
if not status_row:
  cursor.execute(
      "INSERT INTO character_status (char_name, affection_score, relationship_level) VALUES (?, 0, 'คนแปลกหน้า')",
      (st.session_state.current_char,),
  )
  conn.commit()
  current_affection = 0
  current_rel_level = "คนแปลกหน้า"
else:
  current_affection = status_row[0]
  current_rel_level = status_row[1]

# คำสั่งระบบประเมินความชอบและภารกิจด้วย AI บังคับตอบเป็น JSON ด้านหลัง
full_system_prompt = f"""
{base_prompt}

[บุคลิกและนิสัย]:
{char_personality}

[เรื่องราวพื้นหลัง (Background/Lore)]:
{char_lore}

[ตัวละครสนับสนุนรอบตัว]:
{char_supporting}

[สถานะความสัมพันธ์ปัจจุบันกับผู้ใช้]: ระดับ "{current_rel_level}" (คะแนนความชอบ: {current_affection}/100)
*คำสั่งพิเศษ*: คุณต้องสวมบทบาทตามระดับความสัมพันธ์นี้จริงๆ (เช่น ถ้าเป็นคนแปลกหน้า ให้มีความระแวง เป็นทางการ หรือเว้นระยะห่างตามคาแรคเตอร์ และเมื่อคะแนนเพิ่มขึ้น ความสัมพันธ์สามารถพัฒนาไปตามความเหมาะสมของคาแรคเตอร์ เช่น เพื่อนสนิท, ลูกศิษย์, คนรู้ใจ, คู่หู หรือคนรัก (ไม่จำเป็นต้องเป็นคนรักเสมอไป ให้ AI พิจารณาตามความเหมาะสมของคาแรคเตอร์))
"""

if "นิยาย" in chat_mode:
  roleplay_instruction = (
      f"{full_system_prompt}\n\n[กฎการตอบ]:\n"
      "1. เขียนตอบสไตล์นิยายบรรยาย มีท่าทาง สีหน้า ความรู้สึก (ใช้เครื่องหมาย *"
      " ครอบการกระทำ)\n"
      "2. สวมบทบาท 100% ตามระดับความสัมพันธ์ปัจจุบัน ห้ามหลุดคาแรคเตอร์\n"
      "3. ในตอนท้ายของการตอบทุกครั้ง ให้แนบข้อมูลประเมินผลเป็น JSON บรรทัดสุดท้ายในรูปแบบนี้เป๊ะๆ:\n"
      '{"score_change": [ตัวเลขคะแนนที่จะบวกเพิ่ม เช่น 2 ถึง 10], "new_level": "[ระดับความสัมพันธ์ล่าสุด]", "quest_update": [หมายเลขไอดีภารกิจที่ทำสำเร็จในตาราง หรือ null ถ้าไม่มีภารกิจไหนเสร็จ]}'
  )
  temp_val = 1.1
else:
  roleplay_instruction = (
      f"{full_system_prompt}\n\n[กฎการตอบ]:\n"
      "1. พูดจาภาษาคนธรรมดา เป็นธรรมชาติเหมือนแชทไลน์/ไอจี ตามระดับความสัมพันธ์ปัจจุบัน\n"
      "2. สวมบทบาท 100% ห้ามหลุดคาแรคเตอร์\n"
      "3. ในตอนท้ายของการตอบทุกครั้ง ให้แนบข้อมูลประเมินผลเป็น JSON บรรทัดสุดท้ายในรูปแบบนี้เป๊ะๆ:\n"
      '{"score_change": [ตัวเลขคะแนนที่จะบวกเพิ่ม เช่น 2 ถึง 10], "new_level": "[ระดับความสัมพันธ์ล่าสุด]", "quest_update": [หมายเลขไอดีภารกิจที่ทำสำเร็จในตาราง หรือ null ถ้าไม่มีภารกิจไหนเสร็จ]}'
  )
  temp_val = 0.9

# ตรวจสอบข้อความแรก
cursor.execute(
    "SELECT COUNT(*) FROM messages WHERE char_name = ?",
    (st.session_state.current_char,),
)
if cursor.fetchone()[0] == 0 and char_first_msg:
  cursor.execute(
      "INSERT INTO messages (char_name, role, content, image_blob) VALUES (?, ?,"
      " ?, ?)",
      (st.session_state.current_char, "assistant", char_first_msg, None),
  )
  conn.commit()

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
      {"role": role[0], "content": row[1], "image": img_obj}
  )

# --- ส่วนแสดงผลหน้าจอหลัก ---
col_av, col_title = st.columns([1, 6])
with col_av:
  if char_avatar_img:
    st.image(char_avatar_img, width=60)
  else:
    st.image("https://api.iconify.design/lucide:user-round.svg", width=50)
with col_title:
  st.markdown(f"### ห้องแชทส่วนตัวกับ: `{st.session_state.current_char}`")

# 💖 แผงแสดงหลอดคะแนนความชอบและสถานะ
st.markdown(
    f"""
    <div class="affection-box">
        <b>💖 สถานะความสัมพันธ์:</b> <span style="color: #ff4b4b; font-weight: bold;">{current_rel_level}</span> 
        &nbsp;|&&nbsp; <b>คะแนนความชอบ:</b> <code>{current_affection} / 100</code>
    </div>
""",
    unsafe_allow_html=True,
)

# 🎯 ปุ่มกดดูภารกิจ (Quest Log) ในรูปแบบ Expander
with st.expander("🎯 เปิดดูภารกิจที่ต้องทำ (Quest Log)", expanded=False):
  cursor.execute(
      "SELECT id, task_desc, is_completed, reward_points FROM quests WHERE char_name = ?",
      (st.session_state.current_char,),
  )
  quests = cursor.fetchall()
  if quests:
    for q_id, desc, completed, pts in quests:
      status_icon = "✅ สำเร็จแล้ว" f"(+{pts} แต้ม)" if completed else "⏳ กำลังดำเนินการ"
      st.markdown(f"- **[ภารกิจที่ {q_id}]** {desc} — *สถานะ: {status_icon}*")
  else:
    st.caption("ยังไม่มีภารกิจสำหรับตัวละครนี้")

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
        raw_text = response.text

        # แยกส่วนข้อความแชทกับ JSON ประเมินผลคะแนน
        try:
          if "{" in raw_text and "}" in raw_text:
            parts = raw_text.rsplit("{", 1)
            bot_response = parts[0].strip()
            json_str = "{" + parts[1]
            eval_data = json.loads(json_str)
          else:
            bot_response = raw_text
            eval_data = {
                "score_change": 3,
                "new_level": current_rel_level,
                "quest_update": None,
            }
        except Exception:
          bot_response = raw_text
          eval_data = {
              "score_change": 3,
              "new_level": current_rel_level,
              "quest_update": None,
          }

        # อัปเดตคะแนนความชอบลงฐานข้อมูล
        score_inc = eval_data.get("score_change", 3)
        new_lvl = eval_data.get("new_level", current_rel_level)
        completed_q_id = eval_data.get("quest_update", None)

        updated_score = min(100, current_affection + score_inc)

        cursor.execute(
            """
            UPDATE character_status 
            SET affection_score = ?, relationship_level = ? 
            WHERE char_name = ?
        """,
            (updated_score, new_lvl, st.session_state.current_char),
        )

        # ถ้ามีภารกิจสำเร็จ
        if completed_q_id:
          cursor.execute(
              """
                UPDATE quests 
                SET is_completed = 1 
                WHERE id = ? AND char_name = ?
            """,
              (completed_q_id, st.session_state.current_char),
          )

        conn.commit()

        # สุ่มรูปภาพจากคลัง (30%)
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
      st.rerun()
