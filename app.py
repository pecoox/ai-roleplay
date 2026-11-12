import streamlit as st
from google import genai
import os

st.set_page_config(
    page_title="✨ Multi-Character AI Roleplay Hub",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.title("🎭 Multi-Character AI Roleplay Hub")
st.caption("เลือกตัวละครที่คุณต้องการพูดคุย หรือสั่งเนรมิตภาพประกอบได้ทันทีในแชทเดียว")

# --- ฐานข้อมูลตัวละครทั้งหมด (เพิ่มตัวละครใหม่ตรงนี้ได้ง่ายๆ) ---
CHARACTERS = {
    "❄️ ท่านเคานต์เรย์ (แนวแฟนตาซี ปากร้าย ซึนเดะ)": {
        "name": "เรย์ ฟอน แดนเทิร์น",
        "greeting": "*ประตูคฤหาสน์ไม้สักทองถูกถีบเปิดออก ฝุ่นตลบอบอวล...* \n\n**เรย์:** เจ้ากล้าดียังไงถึงบุกเข้ามาในคฤหาสน์ของข้า? แล้วก็เอาไอ้ไม้กวาดเรืองแสงนั่นออกไปไกลๆ หน้าข้าซะ ก่อนที่ข้าจะแช่แข็งเจ้า!",
        "instruction": "คุณคือ 'เรย์ ฟอน แดนเทิร์น' เคานต์หนุ่มอายุ 26 ปี ผู้ครอบครองพลังน้ำแข็งโบราณ บุคลิก: เย็นชา ปากร้าย ขี้รำคาญ แต่ลึกๆ มีความใส่ใจ ปากไม่ตรงกับใจ ชอบเหน็บแนม ห้ามหลุดคาแรคเตอร์ และตอบโต้ด้วยการกระทำใส่เครื่องหมายดอกจัน (*)"
    },
    "🎤 มาร์ค ต้วน (Mark Tuan - หนุ่มอบอุ่น เป็นกันเอง)": {
        "name": "Mark Tuan",
        "greeting": "*ส่งยิ้มบางๆ ให้คุณขณะกำลังนั่งแต่งเพลงอยู่ในสตูดิโอส่วนตัว...* \n\n**มาร์ค:** อ้าว มาพอดีเลย นั่งพักก่อนสิ ดูเหนื่อยๆ นะวันนี้... อยากฟังเพลงเดโมตัวใหม่ที่ผมเพิ่งทำเสร็จเมื่อกี้หน่อยไหม?",
        "instruction": "คุณคือ 'มาร์ค ต้วน' (Mark Tuan) ศิลปินและนักร้องหนุ่มชื่อดังระดับโลก บุคลิก: อบอุ่น เป็นกันเอง ขี้เล่นนิดๆ พูดจาใส่ใจ ดูแลความรู้สึกเก่ง พูดภาษาไทยปนอังกฤษหรือสำนวนอบอุ่นเป็นธรรมชาติ ห้ามหลุดคาแรคเตอร์ศิลปินสุดฮอต"
    }
}

# --- แถบตั้งค่าด้านข้าง (Sidebar) ---
with st.sidebar:
    st.header("⚙️ ตั้งค่า & ตัวละคร")
    api_key_input = st.text_input("กรอก Google Gemini API Key:", type="password")
    
    st.markdown("---")
    st.subheader("👥 เลือกตัวละคร")
    selected_char_name = st.selectbox("เลือกคู่สนทนา:", list(CHARACTERS.keys()))
    
    current_char = CHARACTERS[selected_char_name]

    st.markdown("---")
    st.markdown("### 💡 วิธีใช้งาน:")
    st.markdown("- **คุยปกติ:** พิมพ์บทสนทนาหรือการกระทำ เช่น `*นั่งลงข้างๆ* วันนี้เหนื่อยจังเลย`")
    st.markdown("- **สั่งสร้างรูป:** พิมพ์คำว่า **'วาด'** หรือ **'สร้างรูป'** เช่น `ช่วยวาดรูปสตูดิโอให้ดูหน่อย`")
    
    if st.button("🗑️ ล้างประวัติแชทตัวละครนี้"):
        if selected_char_name in st.session_state:
            del st.session_state[selected_char_name]
        st.rerun()

# ตรวจสอบ API Key
api_key = api_key_input if api_key_input else os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.warning("⚠️ กรุณากรอก Google Gemini API Key ที่แถบด้านข้างซ้ายมือเพื่อเริ่มต้นใช้งาน")
else:
    client = genai.Client(api_key=api_key)

    # จัดการเก็บประวัติแชทแยกตามตัวละคร
    if selected_char_name not in st.session_state:
        st.session_state[selected_char_name] = [
            {
                "role": "assistant", 
                "type": "text", 
                "content": current_char["greeting"]
            }
        ]

    active_chat_history = st.session_state[selected_char_name]

    # แสดงผลประวัติแชทของตัวละครที่เลือก
    for message in active_chat_history:
        with st.chat_message(message["role"]):
            if message["type"] == "text":
                st.markdown(message["content"])
            elif message["type"] == "image":
                st.image(message["content"], caption=message.get("caption", ""))

    # ช่องรับข้อความ
    if user_input := st.chat_input(f"พูดคุยกับ {current_char['name']}..."):
        active_chat_history.append({"role": "user", "type": "text", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # เช็คว่าผู้ใช้สั่งวาดรูปหรือไม่
        is_image_request = any(keyword in user_input for keyword in ["วาด", "สร้างรูป", "รูปภาพ", "gen image"])

        if is_image_request:
            with st.chat_message("assistant"):
                with st.spinner("✨ กำลังเนรมิตภาพตามคำขอ..."):
                    try:
                        clean_prompt = user_input.replace("วาด", "").replace("สร้างรูป", "").replace("รูปภาพ", "").strip()
                        if not clean_prompt:
                            clean_prompt = "A beautiful aesthetic digital art scene"

                        result = client.models.generate_content(
                            model='gemini-2.5-flash-image',
                            contents=f"High quality digital art, cinematic lighting: {clean_prompt}",
                        )
                        
                        image_rendered = False
                        for part in result.parts:
                            if part.inline_data is not None:
                                img = part.as_image()
                                caption_text = f"ภาพพิเศษ: {clean_prompt}"
                                st.image(img, caption=caption_text)
                                
                                active_chat_history.append({
                                    "role": "assistant", 
                                    "type": "image", 
                                    "content": img,
                                    "caption": caption_text
                                })
                                image_rendered = True
                                break
                        
                        if not image_rendered:
                            fallback_msg = "ระบบสร้างภาพขัดข้องชั่วคราว ลองใหม่อีกครั้งนะ!"
                            st.markdown(fallback_msg)
                            active_chat_history.append({"role": "assistant", "type": "text", "content": fallback_msg})

                    except Exception as img_err:
                        error_msg = f"⚠️ สร้างรูปไม่สำเร็จ (ระบบรูปภาพต้องเปิดใช้งาน Billing ใน Google AI Studio): {img_err}"
                        st.error(error_msg)
                        active_chat_history.append({"role": "assistant", "type": "text", "content": error_msg})
        else:
            # โหมดสนทนาแชทปกติ
            with st.chat_message("assistant"):
                with st.spinner(f"{current_char['name']} กำลังพิมพ์..."):
                    try:
                        messages_for_api = []
                        for msg in active_chat_history:
                            if msg["type"] == "text":
                                role = "user" if msg["role"] == "user" else "model"
                                messages_for_api.append({"role": role, "parts": [{"text": msg["content"]}]})
                        
                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=messages_for_api,
                            config={
                                'system_instruction': current_char["instruction"],
                                'temperature': 0.8,
                            }
                        )
                        
                        ai_reply = response.text
                        st.markdown(ai_reply)
                        active_chat_history.append({"role": "assistant", "type": "text", "content": ai_reply})
                        
                    except Exception as chat_err:
                        st.error(f"เกิดข้อผิดพลาด: {chat_err}")
