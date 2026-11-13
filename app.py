from google import genai
import streamlit as st
import time

st.set_page_config(
    page_title="AI Roleplay - Character Avatar", page_icon="🖼️", layout="centered"
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

st.title("🖼️ AI Roleplay: Custom Character & Avatar")

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

# ระบบจัดการตัวละคร (รองรับการเก็บรูปภาพ Avatar)
if "characters" not in st.session_state:
  st.session_state.characters = {
      "มาร์ค ต้วน": {
          "prompt": (
              "คุณคือ มาร์ค ต้วน (Mark Tuan) ศิลปินหนุ่มตัวจริง"
              " นิสัยอบอุ่น เป็นกันเอง และขี้เล่น"
          ),
          "messages": [],
          "avatar": None,  # เก็บรูปภาพประจำตัว
      }
  }

if "current_char" not in st.session_state:
  st.session_state.current_char = "มาร์ค ต้วน"

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
  # 🖼️ เพิ่มช่องอัปโหลดรูปประจำตัวละคร
  new_avatar = st.file_uploader(
      "อัปโหลดรูปโปรไฟล์ตัวละคร", type=["png", "jpg", "jpeg"]
  )

  if st.button("🚀 สร้างตัวละคร", use_container_width=True):
    if new_name and new_prompt:
      if new_name not in st.session_state.characters:
        st.session_state.characters[new_name] = {
            "prompt": new_prompt,
            "messages": [],
            "avatar": new_avatar,  # บันทึกรูปภาพที่อัปโหลด
        }
        st.session_state.current_char = new_name
        st.success(f"สร้าง '{new_name}' สำเร็จ!")
        st.rerun()
      else:
        st.warning("ชื่อนี้มีอยู่แล้ว")
    else:
      st.warning("กรุณากรอกชื่อและคาแรคเตอร์ให้ครบ")

  st.divider()
  st.subheader("👥 เลือกตัวละคร")
  char_list = list(st.session_state.characters.keys())
  selected_char = st.selectbox(
      "สลับแชทกับ:",
      char_list,
      index=char_list.index(st.session_state.current_char),
  )

  if selected_char != st.session_state.current_char:
    st.session_state.current_char = selected_char
    st.rerun()

  if len(st.session_state.characters) > 1:
    if st.button("🗑️ ลบตัวละครนี้", use_container_width=True):
      del st.session_state.characters[st.session_state.current_char]
      st.session_state.current_char = list(
          st.session_state.characters.keys()
      )[0]
      st.rerun()

# ดึงข้อมูลตัวละครปัจจุบัน
active_char_data = st.session_state.characters[st.session_state.current_char]
base_prompt = active_char_data["prompt"]
char_avatar = active_char_data["avatar"]

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

current_messages = active_char_data["messages"]

# แสดงหัวข้อและรูปโปรไฟล์ตัวละครด้านบนสุดของห้องแชท
col_av, col_title = st.columns([1, 6])
with col_av:
  if char_avatar:
    st.image(char_avatar, width=60)
  else:
    st.image(
        "https://api.iconify.design/lucide:user-round.svg", width=50
    )  # รูปไอคอนสำรอง
with col_title:
  st.markdown(f"### ห้องแชทส่วนตัวกับ: `{st.session_state.current_char}`")
st.divider()

# แสดงประวัติแชท (ใช้รูป Avatar ของตัวละครมาแสดงฝั่ง Assistant)
for message in current_messages:
  if message["role"] == "user":
    with st.chat_message("user", avatar="👤"):
      st.markdown(message["content"])
  else:
    # ถ้ารูปตัวละครมี ให้ใช้รูปลงในแชท ถ้าไม่มีใช้ไอคอนเริ่มต้น
    avatar_icon = char_avatar if char_avatar else "✨"
    with st.chat_message("assistant", avatar=avatar_icon):
      st.markdown(message["content"])

# ช่องพิมพ์ข้อความ
if user_input := st.chat_input(
    f"ส่งข้อความหา {st.session_state.current_char}..."
):
  current_messages.append({"role": "user", "content": user_input})
  with st.chat_message("user", avatar="👤"):
    st.markdown(user_input)

  avatar_icon = char_avatar if char_avatar else "✨"
  with st.chat_message("assistant", avatar=avatar_icon):
    message_placeholder = st.empty()
    message_placeholder.markdown("กำลังพิมพ์...")

    bot_response = None
    max_retries = 3

    for attempt in range(max_retries):
      try:
        formatted_history = []
        for m in current_messages[:-1]:
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
      current_messages.append({"role": "assistant", "content": bot_response})
