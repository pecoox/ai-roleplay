from google import genai
import streamlit as st
import time

st.set_page_config(
    page_title="AI Roleplay - Mark Tuan", page_icon="🎤", layout="centered"
)

st.title("🎤 AI Roleplay: คุยกับมาร์ค ต้วน")

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

# จัดการระบบห้องแชทหลายห้องใน session_state
if "chats" not in st.session_state:
  st.session_state.chats = {"แชทหลักของมาร์ค": []}
if "current_chat" not in st.session_state:
  st.session_state.current_chat = "แชทหลักของมาร์ค"

# แผงควบคุมเมนูด้านข้าง (Sidebar) สำหรับจัดการแชทและตั้งค่า
with st.sidebar:
  st.header("💬 จัดการห้องแชท")

  # ปุ่มสร้างแชทใหม่
  new_chat_name = st.text_input("ชื่อห้องแชทใหม่:", placeholder="เช่น คุยเรื่องเพลง...")
  if st.button("➕ สร้างแชทใหม่"):
    if new_chat_name and new_chat_name not in st.session_state.chats:
      st.session_state.chats[new_chat_name] = []
      st.session_state.current_chat = new_chat_name
      st.rerun()

  st.divider()

  # เลือกห้องแชท
  chat_list = list(st.session_state.chats.keys())
  selected_chat = st.selectbox(
      "เลือกห้องแชท:",
      chat_list,
      index=chat_list.index(st.session_state.current_chat),
  )
  if selected_chat != st.session_state.current_chat:
    st.session_state.current_chat = selected_chat
    st.rerun()

  # ปุ่มลบแชทปัจจุบัน (ห้ามลบถ้าเหลือห้องเดียว)
  if len(st.session_state.chats) > 1:
    if st.button("🗑️ ลบห้องแชทนี้"):
      del st.session_state.chats[st.session_state.current_chat]
      st.session_state.current_chat = list(st.session_state.chats.keys())[0]
      st.rerun()
  else:
    st.caption("ℹ️ ต้องมีห้องแชทอย่างน้อย 1 ห้อง")

  st.divider()
  st.header("⚙️ ตั้งค่าระบบ")
  character_prompt = st.text_area(
      "คาแรคเตอร์:",
      (
          "คุณคือ มาร์ค ต้วน (Mark Tuan) ศิลปินหนุ่ม สุภาพ อบอุ่น"
          " และเป็นกันเองกับแฟนคลับ"
      ),
      height=100,
  )

# ดึงข้อความในห้องแชทปัจจุบันมาแสดง
current_messages = st.session_state.chats[st.session_state.current_chat]

for message in current_messages:
  with st.chat_message(message["role"]):
    st.markdown(message["content"])

# ช่องพิมพ์ข้อความ
if user_input := st.chat_input("พิมพ์ข้อความคุยกับมาร์ค..."):
  current_messages.append({"role": "user", "content": user_input})
  with st.chat_message("user"):
    st.markdown(user_input)

  with st.chat_message("assistant"):
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
            config={"system_instruction": character_prompt},
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
