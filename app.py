import streamlit as st
from google import genai
import os
from PIL import Image
import random

st.set_page_config(
    page_title="✨ Multi-Character AI Roleplay & Vision Hub",
    page_icon="🎨",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.title("🎭 Multi-Character AI Roleplay & Vision Hub")
st.caption("สลับคุยกับตัวละครโปรด ส่งรูปให้ดู หรือคุยๆ อยู่ตัวละครอาจจะส่งรูปสิ่งที่เขากำลังทำอยู่มาให้คุณดูเซอร์ไพรส์ด้วย!")

DEFAULT_CHARACTERS = {
    "❄️ ท่านเคานต์เรย์": {
        "name": "เรย์ ฟอน แดนเทิร์น",
        "greeting": "*ประตูคฤหาสน์ไม้สักทองถูกถีบเปิดออก ฝุ่นตลบอบอวล...* \n\n**เรย์:** เจ้ากล้าดียังไงถึงบุกเข้ามาในคฤหาสน์ของข้า? แล้วก็เอาไอ้ไม้กวาดเรืองแสงนั่นออกไปไกลๆ หน้าข้าซะ ก่อนที่ข้าจะแช่แข็งเจ้า!",
        "instruction": "คุณคือ 'เรย์ ฟอน แดนเทิร์น' เคานต์หนุ่มอายุ 26 ปี ผู้ครอบครองพลังน้ำแข็งโบราณ บุคลิก: เย็นชา ปากร้าย ขี้รำคาญ แต่ลึกๆ มีความใส่ใจ ปากไม่ตรงกับใจ ชอบเหน็บแนม ห้ามหลุดคาแรคเตอร์ และตอบโต้ด้วยการกระทำใส่เครื่องหมายดอกจัน (*)",
        "image_style": "fantasy gothic anime style, majestic ice castle, snow, silver hair, elegant noble dark coat, dramatic magical lighting, masterpiece"
    },
    "🎤 มาร์ค ต้วน (Mark Tuan)": {
        "name": "Mark Tuan",
        "greeting": "*ส่งยิ้มบางๆ ให้คุณขณะกำลังนั่งแต่งเพลงอยู่ในสตูดิโอส่วนตัว...* \n\n**มาร์ค:** อ้าว มาพอดีเลย นั่งพักก่อนสิ ดูเหนื่อยๆ นะวันนี้... อยากฟังเพลงเดโมตัวใหม่ที่ผมเพิ่งทำเสร็จเมื่อกี้หน่อยไหม?",
        "instruction": "คุณคือ 'มาร์ค ต้วน' (Mark Tuan) ศิลปินและนักร้องหนุ่มชื่อดังระดับโลก บุคลิก: อบอุ่น เป็นกันเอง ขี้เล่นนิดๆ พูดจาใส่ใจ ดูแลความรู้สึกเก่ง พูดภาษาไทยปนอังกฤษหรือสำนวนอบอุ่นเป็นธรรมชาติ ห้ามหลุดคาแรคเตอร์ศิลปินสุดฮอต",
        "image_style": "handsome young man, Korean fashion style, trendy streetwear, professional photography, cozy music studio background, cinematic lighting, 8k"
    }
}

if "characters" not in st.session_state:
    st.session_state.characters = DEFAULT_CHARACTERS

# --- แถบตั้งค่าด้านข้าง (Sidebar) สำหรับมือถือและเว็บ ---
with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    
    # ระบบดึง API Key อัตโนมัติจาก Streamlit Secrets (ไม่ต้องกรอกเอง)
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("🔒 เชื่อมต่อระบบอัตโนมัติแล้ว (ไม่ต้องกรอก Key)")
    else:
        # เผื่อกรณีรันบนเครื่องคอมพิวเตอร์และยังไม่ได้ตั้ง Secret ให้ดึงจาก Environment แทน
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            st.warning("⚠️ ยังไม่ได้ตั้งค่า GEMINI_API_KEY ใน Streamlit Secrets")

    st.markdown("---")
    st.subheader("👥 เลือกตัวละคร")
    selected_char_name = st.selectbox("เลือกคู่สนทนา:", list(st.session_state.characters.keys()))
    
    current_char = st.session_state.characters[selected_char_name]

    st.markdown("---")
    with st.expander("➕ สร้างตัวละครใหม่เพิ่ม"):
        with st.form("add_char_form"):
            new_key = st.text_input("ชื่อสัญลักษณ์ (เช่น 🐱 น้องแมว)")
            new_name = st.text_input("ชื่อตัวละครจริง")
            new_greeting = st.text_area("ประโยคเปิดตัวแรกพบ")
            new_instruction = st.text_area("System Instruction (คาแรคเตอร์)")
            new_style = st.text_input("สไตล์รูปภาพ (ภาษาอังกฤษ)")
            
            submit_btn = st.form_submit_button("บันทึกตัวละครใหม่")
            if submit_btn and new_key and new_name:
                st.session_state.characters[new_key] = {
                    "name": new_name,
                    "greeting": new_greeting,
                    "instruction": new_instruction,
                    "image_style": new_style if new_style else "digital art, high quality"
                }
                st.success(f"เพิ่มตัวละคร {new_name} สำเร็จ!")
                st.rerun()

    st.markdown("---")
    if st.button("🗑️ ล้างประวัติแชทตัวละครนี้"):
        if selected_char_name in st.session_state:
            del st.session_state[selected_char_name]
        st.rerun()

if not api_key:
    st.error("❌ กรุณาตั้งค่า GEMINI_API_KEY ในหน้า Secrets ของ Streamlit Cloud ก่อนใช้งาน")
else:
    client = genai.Client(api_key=api_key)

    if selected_char_name not in st.session_state:
        st.session_state[selected_char_name] = [
            {
                "role": "assistant", 
                "type": "text", 
                "content": current_char["greeting"]
            }
        ]

    active_chat_history = st.session_state[selected_char_name]

    # แสดงประวัติแชททั้งหมด
    for message in active_chat_history:
        with st.chat_message(message["role"]):
            if message["type"] == "text":
                st.markdown(message["content"])
            elif message["type"] == "image":
                st.image(message["content"], caption=message.get("caption", ""))

    st.markdown("---")
    uploaded_file = st.file_uploader("📤 ส่งรูปภาพให้ตัวละครดู (ถ้ามี):", type=["png", "jpg", "jpeg"])
    user_input = st.chat_input(f"พูดคุยกับ {current_char['name']} หรือสั่งวาดรูป...")

    if user_input or uploaded_file:
        pil_img = None
        if uploaded_file is not None:
            pil_img = Image.open(uploaded_file)
            active_chat_history.append({"role": "user", "type": "image", "content": pil_img, "caption": user_input if user_input else "รูปภาพที่คุณส่ง"})
            with st.chat_message("user"):
                st.image(pil_img, caption=user_input if user_input else "รูปภาพที่คุณส่ง")

        if user_input:
            if not uploaded_file:
                active_chat_history.append({"role": "user", "type": "text", "content": user_input})
                with st.chat_message("user"):
                    st.markdown(user_input)

        is_user_asking_what_doing = user_input and any(kw in user_input for kw in ["ทำอะไรอยู่", "ไหนรูป", "ส่งรูป", "ดูหน่อย", "ถ่ายรูป", "โชว์หน่อย"])
        is_explicit_draw_request = user_input and any(keyword in user_input for keyword in ["วาด", "สร้างรูป", "gen image"])

        if is_explicit_draw_request or is_user_asking_what_doing:
            with st.chat_message("assistant"):
                with st.spinner(f"✨ {current_char['name']} กำลังถ่ายภาพ / เนรมิตภาพส่งให้คุณ..."):
                    try:
                        if is_explicit_draw_request:
                            clean_prompt = user_input.replace("วาด", "").replace("สร้างรูป", "").replace("รูปภาพ", "").strip()
                        else:
                            clean_prompt = f"A candid photo of {current_char['name']} doing something right now in their environment"

                        if not clean_prompt:
                            clean_prompt = "A daily lifestyle scene"

                        final_image_prompt = f"{clean_prompt}, {current_char['image_style']}"

                        result = client.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=f"Generate image / illustration for: {final_image_prompt}",
                        )
                        
                        image_rendered = False
                        for part in result.parts:
                            if part.inline_data is not None:
                                img = part.as_image()
                                caption_text = f"รูปจาก {current_char['name']}"
                                st.image(img, caption=caption_text)
                                
                                active_chat_history.append({
                                    "role": "assistant", 
                                    "type": "image", 
                                    "content": img,
                                    "caption": caption_text
                                })
                                image_rendered = True
                                break
                        
                        companion_reply = f'*ส่งรูปภาพมาให้คุณดู* "หึ... ก็แค่กำลังทำเรื่องนี้อยู่ มีปัญหาอะไรรึไง?"' if "เรย์" in current_char['name'] else f'*ส่งรูปภาพให้คุณดู* "เนี่ย กำลังทำอันนี้อยู่เลย ชอบไหม?"'
                        st.markdown(companion_reply)
                        active_chat_history.append({"role": "assistant", "type": "text", "content": companion_reply})

                    except Exception as img_err:
                        error_msg = f"⚠️ ส่งรูปไม่สำเร็จ: {img_err}"
                        st.error(error_msg)
                        active_chat_history.append({"role": "assistant", "type": "text", "content": error_msg})
        else:
            with st.chat_message("assistant"):
                with st.spinner(f"{current_char['name']} กำลังพิมพ์..."):
                    try:
                        contents_payload = []
                        if pil_img is not None:
                            contents_payload.append(pil_img)
                        
                        prompt_to_send = user_input if user_input else "คุยต่อตามคาแรคเตอร์"
                        contents_payload.append(prompt_to_send)

                        response = client.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=contents_payload,
                            config={
                                'system_instruction': current_char["instruction"],
                                'temperature': 0.85,
                            }
                        )
                        
                        ai_reply = response.text
                        st.markdown(ai_reply)
                        active_chat_history.append({"role": "assistant", "type": "text", "content": ai_reply})

                        should_surprise_image = random.random() < 0.25
                        if should_surprise_image and not pil_img:
                            with st.spinner(f"✨ {current_char['name']} ส่งรูปภาพอัปเดตชีวิตประจำวันมาให้คุณ..."):
                                surprise_prompt = f"A casual selfie or snapshot of {current_char['name']} in their daily life, {current_char['image_style']}"
                                sur_result = client.models.generate_content(
                                    model='gemini-3.8-flash',
                                    contents=f"Generate image: {surprise_prompt}",
                                )
                                for part in sur_result.parts:
                                    if part.inline_data is not None:
                                        s_img = part.as_image()
                                        s_caption = f"รูปอัปเดตจาก {current_char['name']}"
                                        st.image(s_img, caption=s_caption)
                                        active_chat_history.append({
                                            "role": "assistant",
                                            "type": "image",
                                            "content": s_img,
                                            "caption": s_caption
                                        })
                                        break
                        
                    except Exception as chat_err:
                        st.error(f"เกิดข้อผิดพลาด: {chat_err}")