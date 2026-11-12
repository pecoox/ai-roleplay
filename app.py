from google import genai
import streamlit as st
import time

st.set_page_config(
    page_title="AI Human-like Roleplay", page_icon="💬", layout="centered"
)

st.title("💬 AI Roleplay: แชทกับตัวละครให้เหมือนคนจริงๆ")

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

# ระบบจัดการตัวละคร
if "characters" not in st.session_state:
  st.session_state.characters = {
      "มาร์ค ต้วน": {
          "prompt": (
              "คุณคือ มาร์ค ต้วน (Mark Tuan) ศิลปินหนุ่มตัวจริง"
              " นิสัยอบอุ่น เป็นกันเอง และขี้เล่น"
          ),
          "messages": [],
      }
  }

if "current_char" not in st.session_state:
  st.session_state.current_char = "มาร์ค ต้วน"

# แผงควบคุมด้านข้าง (Sidebar)
with st.sidebar:
  st.header("✨ สร้างตัวละครใหม่")
  new_name = st.text_input("ชื่อตัวละคร:", placeholder="เช่น แฟนหนุ่ม, เพื่อนสนิท...")
  new_prompt = st.text_area(
      "กำหนดคาแรคเตอร์:",
      placeholder="คุณคือเพื่อนสนิท ขี้เล่น กวนๆ...",
      height=100,
  )

  if st.button("➕ สร้างตัวละคร"):
    if new_name and new_prompt:
      if new_name not in st.session_state.characters:
        st.session_state.characters[new_name] = {
            "prompt": new_prompt,
            "messages": [],
        }
        st.session_state.current_char = new_name
        st.success(f"สร้างตัวละคร '{new_name}' สำเร็จ!")
        st.rerun()
      else:
        st.warning("ชื่อตัวละครนี้มีอยู่แล้ว")
    else:
      st.warning("กรุณากรอกข้อมูลให้ครบ")

  st.divider()
  st.header("👥 เลือกตัวละคร")
  char_list = list(st.session_state.characters.keys())
  selected_char = st.selectbox(
      "เลือกตัวละคร:",
      char_list,
      index=char_list.index(st.session_state.current_char),
  )

  if selected_char != st.session_state.current_char:
    st.session_state.current_char = selected_char
    st.rerun()

  if len(st.session_state.characters) > 1:
    if st.button("🗑️ ลบตัวละครนี้"):
      del st.session_state.characters[st.session_state.current_char]
      st.session_state.current_char = list(
          st.session_state.characters.keys()
      )[0]
      st.rerun()

# ดึงข้อมูลตัวละครปัจจุบัน
active_char_data = st.session_state.characters[st.session_state.current_char]
base_prompt = active_char_data["prompt"]
current_messages = active_char_data["messages"]

# 📌 คำสั่งเสริมบังคับให้ AI ตอบเหมือนคนจริงๆ และเป็นธรรมชาติที่สุด
human_like_instruction = (
    f"{base_prompt}\n\n[กฎเหล็กในการตอบ]:\n"
    "1. สวมบทบาทเป็นตัวละครนั้นแบบ 100% ห้ามหลุดคาแรคเตอร์และห้ามบอกว่าตัวเองเป็น AI"
    " เด็ดขาด\n"
    "2. พูดจาภาษาคนธรรมดา ใช้น้ำเสียงธรรมชาติเหมือนแชทหากันจริงๆ"
    " มีการเว้นวรรคพิมพ์สั้นยาวสลับกันไปตามอารมณ์\n"
    "3. ห้ามตอบแบบทางการ ห้ามใช้ภาษาวิชาการ"
    " ห้ามมีคำพูดลงท้ายแบบหุ่นยนต์หรือบอท เช่น 'มีอะไรให้ช่วยอีกไหมคะ'\n"
    "4. แสดงความรู้สึก สีหน้า ท่าทาง หรือใส่อารมณ์ร่วมในบทสนทนาให้สมจริง"
)

st.subheader(f"💬 กำลังคุยกับ: {st.session_state.current_char}")

# แสดงแชท
for message in current_messages:
  with st.chat_message(message["role"]):
    st.markdown(message["content"])

# ช่องพิมพ์ข้อความ
if user_input := st.chat_input(
    f"พิมพ์คุยกับ {st.session_state.current_char}..."
):
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
            config={
                "system_instruction": human_like_instruction,
                "temperature": 1.0,  # เพิ่มความสร้างสรรค์และเป็นธรรมชาติให้คำตอบไม่จำเจ
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
