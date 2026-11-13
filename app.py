from google import genai
import streamlit as st
import time

st.set_page_config(
    page_title="AI Novel & Roleplay", page_icon="📖", layout="centered"
)

st.title("📖 AI Roleplay & Novel Style: สไตล์นิยายบรรยาย")

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
  st.header("⚙️ ตั้งค่าสไตล์การคุย")
  # เลือกโหมดการตอบ
  chat_mode = st.radio(
      "เลือกรูปแบบการตอบ:",
      ["💬 แชทสั้นๆ เป็นธรรมชาติ", "📖 โหมดนิยายบรรยายยาว & ชวนคุยต่อเนื่อง"],
  )

  st.divider()
  st.header("✨ สร้างตัวละครใหม่")
  new_name = st.text_input(
      "ชื่อตัวละคร:", placeholder="เช่น พระเอกนิยาย, แฟนหนุ่ม..."
  )
  new_prompt = st.text_area(
      "กำหนดคาแรคเตอร์:",
      placeholder="คุณคือมาเฟียหนุ่มผู้เย็นชาแต่คลั่งรัก...",
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

# 📌 ปรับแต่งคำสั่งตามโหมดที่เลือก
if "นิยาย" in chat_mode:
  roleplay_instruction = (
      f"{base_prompt}\n\n[กฎเหล็กสำหรับโหมดนิยายบรรยาย]:\n"
      "1. เขียนตอบให้มีความยาวมากขึ้นในรูปแบบ 'นิยายแชท/บทบรรยาย' (Novel"
      " Style) มีการบรรยายท่าทาง สีหน้า แววตา หรือบรรยากาศรอบตัวประกอบด้วย"
      " (ใช้เครื่องหมายดอกจัน * หรือวงเล็บ เพื่อสื่อถึงการกระทำ เช่น *เขยิบเข้าไปใกล้*)"
      "\n2. สวมบทบาทเป็นตัวละครนั้นแบบ 100% ห้ามบอกว่าเป็น AI เด็ดขาด\n3."
      " เมื่อบรรยายจบเรื่องราวในแต่ละตอน ให้ 'ตั้งคำถามหรือเปิดฉากสนทนา' เพื่อโยนบทกลับมาให้ผู้ใช้เป็นคนตัดสินใจเลือกตอบหรือกระทำต่อ"
      " เพื่อดำเนินเรื่องราวร่วมกันต่อไป"
  )
  temperature_val = 1.1
else:
  roleplay_instruction = (
      f"{base_prompt}\n\n[กฎเหล็กสำหรับโหมดแชทปกติ]:\n"
      "1. สวมบทบาทเป็นตัวละครนั้นแบบ 100% ห้ามบอกว่าเป็น AI เด็ดขาด\n"
      "2. พูดจาภาษาคนธรรมดา ใช้น้ำเสียงธรรมชาติเหมือนแชทหากันจริงๆ"
      " พิมพ์ตอบสั้นกระชับเป็นธรรมชาติ\n"
      "3. ห้ามมีคำพูดลงท้ายแบบบอท เช่น 'มีอะไรให้ช่วยอีกไหมคะ'"
  )
  temperature_val = 0.9

current_messages = active_char_data["messages"]
st.subheader(f"📖 กำลังสวมบทบาทกับ: {st.session_state.current_char}")

# แสดงแชท
for message in current_messages:
  with st.chat_message(message["role"]):
    st.markdown(message["content"])

# ช่องพิมพ์ข้อความ
if user_input := st.chat_input(
    f"พิมพ์โต้ตอบกับ {st.session_state.current_char}..."
):
  current_messages.append({"role": "user", "content": user_input})
  with st.chat_message("user"):
    st.markdown(user_input)

  with st.chat_message("assistant"):
    message_placeholder = st.empty()
    message_placeholder.markdown("กำลังร้อยเรียงเรื่องราว...")

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
                "temperature": temperature_val,
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
