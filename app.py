from google import genai
import streamlit as st

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
model_name = "gemini-3.8-flash"

# เมนูด้านข้าง
with st.sidebar:
  st.header("⚙️ ตั้งค่าระบบ")
  character_prompt = st.text_area(
      "คาแรคเตอร์:",
      (
          "คุณคือ มาร์ค ต้วน (Mark Tuan) ศิลปินหนุ่ม สุภาพ อบอุ่น"
          " และเป็นกันเองกับแฟนคลับ"
      ),
      height=120,
  )

# แสดงประวัติแชท
if "messages" not in st.session_state:
  st.session_state.messages = []

for message in st.session_state.messages:
  with st.chat_message(message["role"]):
    st.markdown(message["content"])

# ช่องพิมพ์ข้อความ
if user_input := st.chat_input("พิมพ์ข้อความคุยกับมาร์ค..."):
  st.session_state.messages.append({"role": "user", "content": user_input})
  with st.chat_message("user"):
    st.markdown(user_input)

  with st.chat_message("assistant"):
    message_placeholder = st.empty()
    message_placeholder.markdown("กำลังพิมพ์...")

    try:
      # ใช้ Chat Session แบบต่อเนื่องของ SDK เพื่อความเร็วและจำบทสนทนาได้ดีขึ้น
      chat = client.chats.create(
          model=model_name,
          config={
              "system_instruction": character_prompt,
              "temperature": 0.7,
          },
      )

      # ส่งประวัติเก่าทั้งหมดให้ AI จำแบบรวดเร็ว
      for m in st.session_state.messages[:-1]:
        # จำแนกบทบาทผู้ใช้กับบอท
        role = "user" if m["role"] == "user" else "model"
        # ข้ามส่วนที่เป็นข้อความระบบเก่าชั่วคราวเพื่อความเสถียร
        pass

      # ส่งข้อความล่าสุดเข้าไปคุย
      # (ใช้ประวัติจาก session_state ส่งแบบรวบยอด)
      history_payload = []
      for m in st.session_state.messages[:-1]:
        history_payload.append({
            "role": "user" if m["role"] == "user" else "model",
            "parts": [m["content"]],
        })

      chat = client.chats.create(
          model=model_name,
          history=history_payload,
          config={"system_instruction": character_prompt},
      )

      response = chat.send_message(user_input)
      bot_response = response.text

      message_placeholder.markdown(bot_response)
      st.session_state.messages.append(
          {"role": "assistant", "content": bot_response}
      )

    except Exception as e:
      message_placeholder.error(f"เกิดข้อผิดพลาด: {str(e)}")
