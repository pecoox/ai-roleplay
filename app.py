from google import genai
import streamlit as st

# ตั้งค่าหน้าเว็บ
st.set_page_config(
    page_title="AI Roleplay - Mark Tuan", page_icon="🎤", layout="centered"
)

st.title("🎤 AI Roleplay: คุยกับมาร์ค ต้วน")

# ดึง API Key จาก Streamlit Secrets
try:
  api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
  api_key = None

if not api_key:
  st.warning("⚠️ ยังไม่ได้ตั้งค่า GEMINI_API_KEY ใน Streamlit Secrets")
  st.stop()

# เชื่อมต่อกับ Google GenAI SDK (อัปเดตใช้รุ่น gemini-3.8-flash ตามระบบแนะนำ)
client = genai.Client(api_key=api_key)
model_name = "gemini-3.8-flash"

# แผงควบคุมเมนูด้านข้าง (Sidebar) สำหรับตั้งค่า
with st.sidebar:
  st.header("⚙️ ตั้งค่าระบบ")
  # ช่องใส่บทบาทตัวละคร
  character_prompt = st.text_area(
      "กำหนดคาแรคเตอร์ตัวละคร:",
      (
          "คุณคือ มาร์ค ต้วน (Mark Tuan) ศิลปินหนุ่มสุดฮอต สุภาพ อบอุ่น"
          " ขี้เล่นนิดๆ และพูดจาเป็นกันเองกับแฟนคลับเสมอ"
      ),
      height=150,
  )

  st.divider()
  st.subheader("🖼️ ส่งรูปภาพให้ตัวละครดู (ถ้ามี):")
  uploaded_file = st.file_uploader(
      "อัปโหลดรูปภาพ", type=["png", "jpg", "jpeg"]
  )

# ช่องแชท
if "messages" not in st.session_state:
  st.session_state.messages = []

for message in st.session_state.messages:
  with st.chat_message(message["role"]):
    st.markdown(message["content"])
    if "image" in message:
      st.image(message["image"], width=250)

# รับข้อความจากผู้ใช้
if user_input := st.chat_input("พิมพ์ข้อความคุยกับมาร์ค..."):
  st.session_state.messages.append({"role": "user", "content": user_input})
  with st.chat_message("user"):
    st.markdown(user_input)

  # สร้างข้อความตอบกลับจาก AI
  with st.chat_message("assistant"):
    message_placeholder = st.empty()
    message_placeholder.markdown("มาร์คกำลังพิมพ์...")

    try:
      # เตรียมเนื้อหาที่จะส่งไปหา AI (รองรับทั้งข้อความและรูปภาพ)
      contents = []

      image_data = None
      if uploaded_file is not None:
        image_bytes = uploaded_file.getvalue()
        image_data = image_bytes
        contents.append(
            {"mime_type": uploaded_file.type, "data": image_bytes}
        )

      chat_history = []
      for m in st.session_state.messages[:-1]:
        chat_history.append(f"{m['role']}: {m['content']}")

      full_prompt = (
          f"System Instruction: {character_prompt}\n\n"
          + "\n".join(chat_history)
          + f"\nuser: {user_input}"
      )
      contents.append(full_prompt)

      # เรียกใช้งานโมเดล gemini-3.8-flash
      response = client.models.generate_content(
          model=model_name,
          contents=contents,
      )

      bot_response = response.text
      message_placeholder.markdown(bot_response)

      if image_data:
        st.session_state.messages.append(
            {"role": "assistant", "content": bot_response, "image": image_data}
        )
      else:
        st.session_state.messages.append(
            {"role": "assistant", "content": bot_response}
        )

    except Exception as e:
      error_msg = str(e)
      if "503" in error_msg or "UNAVAILABLE" in error_msg:
        message_placeholder.error(
            "⚠️ เซิร์ฟเวอร์หนาแน่นชั่วคราว (Error 503) ลองกดส่งข้อความใหม่อีกครั้งนะครับ"
        )
      else:
        message_placeholder.error(f"เกิดข้อผิดพลาด: {error_msg}")
