import streamlit as st
import json
import random
import urllib.request
import hashlib
from PIL import Image
import io
from ai_engine import run_with_timer

def render_admin_sidebar(cursor, conn, all_chars, active_char):
    st.markdown("### 🛠️ จัดการระบบ (Admin Only)")
    sidebar_action = st.selectbox(
        "เลือกการจัดการ:",
        [
            "✨ สร้างตัวละครหลักด้วย AI (พรีเมียมขั้นสูง)",
            "🌐 นำเข้าตัวละครจากข้อมูลเว็บ (Smart Parser)",
            "➕ สร้างตัวละครหลักใหม่ (Manual)",
            "✏️ แก้ไขข้อมูลตัวละครหลัก",
            "🗑️ ลบตัวละครหลัก",
            "👥 จัดการตัวละครเสริม",
            "🎯 จัดการภารกิจ (Quest Log)",
            "🖼️ จัดการคลังรูปภาพ",
            "👥 จัดการผู้ใช้งานระบบ"
        ]
    )
    return sidebar_action

def handle_admin_actions(sidebar_action, cursor, conn, all_chars, active_char, client, model_name, current_user):
    if sidebar_action == "✨ สร้างตัวละครหลักด้วย AI (พรีเมียมขั้นสูง)":
        st.markdown("### ✨ สร้างตัวละครหลัก (พรีเมียมขั้นสูง)")
        with st.form("ai_gen_char_form_advanced"):
            ai_target_name = st.text_input("ชื่อดารา หรือ ตัวละครหลัก:", placeholder="เช่น เซอร์เวรัส สเนป, แฮร์รี่ พอตเตอร์...")
            ai_submit_btn = st.form_submit_button("🚀 เริ่มต้นสร้างระดับพรีเมียม", use_container_width=True)

            if ai_submit_btn and ai_target_name:
                run_with_timer(f"AI กำลังประมวลผลคาแรคเตอร์เชิงลึกของ '{ai_target_name}'", 30)
                try:
                    existing_chars_str = ", ".join(all_chars) if all_chars else "ไม่มี"
                    prompt_gen = (
                        f"คุณคือผู้เชี่ยวชาญการสร้างข้อมูลจักรวาลและตัวละครสำหรับ AI Roleplay ระดับโลก\n"
                        f"ตัวละครที่มีอยู่แล้วในระบบ ห้ามสร้างให้ซ้ำซากหรือมีบุคลิกทับซ้อนกัน: [{existing_chars_str}]\n"
                        f"เป้าหมายในการสร้างตัวละครใหม่: '{ai_target_name}'\n\n"
                        f"เงื่อนไขบังคับเข้มงวด:\n"
                        f"1. **ความสมจริงและลึกซึ้ง**: เขียนคาแรคเตอร์ (Prompt), บุคลิก (Personality), และเรื่องราว (Lore) ให้ละเอียด สละสลวย สมจริง เหมือนนิยายขายดี\n"
                        f"2. **องค์ประกอบครบถ้วน**: ต้องมีตัวละครเสริมอย่างน้อย 5 ตัว และภารกิจเริ่มต้นอย่างน้อย 5 ภารกิจ\n\n"
                        f"กรุณาส่งออกเป็นรูปแบบ JSON 1 บรรทัด (ห้ามมี markdown หรือข้อความอื่นปน) โครงสร้างดังนี้:\n"
                        "{\n"
                        f'  "name": "{ai_target_name}",\n'
                        '  "prompt": "คาแรคเตอร์หลักและบทบาทเชิงลึกที่ไม่ซ้ำใคร",\n'
                        '  "personality": "บุคลิกและนิสัยใจคออย่างประณีตชัดเจน",\n'
                        '  "lore": "เรื่องราวพื้นหลังและความสัมพันธ์ที่มีมิติ",\n'
                        '  "first_messages": ["ข้อความเปิดตัวที่ 1", "ข้อความเปิดตัวที่ 2", "ข้อความเปิดตัวที่ 3"],\n'
                        '  "supporting_chars": [\n'
                        '    {"name": "ชื่อตัวเสริม 1", "prompt": "บทบาท", "personality": "นิสัย", "lore": "ความสัมพันธ์"},\n'
                        '    {"name": "ชื่อตัวเสริม 2", "prompt": "บทบาท", "personality": "นิสัย", "lore": "ความสัมพันธ์"},\n'
                        '    {"name": "ชื่อตัวเสริม 3", "prompt": "บทบาท", "personality": "นิสัย", "lore": "ความสัมพันธ์"},\n'
                        '    {"name": "ชื่อตัวเสริม 4", "prompt": "บทบาท", "personality": "นิสัย", "lore": "ความสัมพันธ์"},\n'
                        '    {"name": "ชื่อตัวเสริม 5", "prompt": "บทบาท", "personality": "นิสัย", "lore": "ความสัมพันธ์"}\n'
                        "  ],\n"
                        '  "quests": [\n'
                        '    {"desc": "รายละเอียดภารกิจที่ 1", "pts": 15},\n'
                        '    {"desc": "รายละเอียดภารกิจที่ 2", "pts": 20},\n'
                        '    {"desc": "รายละเอียดภารกิจที่ 3", "pts": 25},\n'
                        '    {"desc": "รายละเอียดภารกิจที่ 4", "pts": 30},\n'
                        '    {"desc": "รายละเอียดภารกิจที่ 5", "pts": 40}\n'
                        "  ]\n"
                        "}"
                    )
                    response = client.models.generate_content(model=model_name, contents=prompt_gen)
                    raw_res = response.text.strip()

                    if "{" in raw_res and "}" in raw_res:
                        json_text = raw_res[raw_res.find("{"):raw_res.rfind("}")+1]
                        char_info = json.loads(json_text)
                        
                        c_name = char_info.get("name", ai_target_name)
                        c_prompt = char_info.get("prompt", "")
                        c_pers = char_info.get("personality", "")
                        c_lore = char_info.get("lore", "")
                        f_msgs = char_info.get("first_messages", ["สวัสดีครับ"])
                        sub_list = char_info.get("supporting_chars", [])
                        quest_list = char_info.get("quests", [])
                        
                        sample_avatar_urls = [
                            "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=600",
                            "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=600",
                            "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=600"
                        ]
                        try:
                            avatar_bytes = urllib.request.urlopen(random.choice(sample_avatar_urls), timeout=5).read()
                        except:
                            avatar_bytes = None

                        cursor.execute(
                            "INSERT OR REPLACE INTO characters (name, prompt, personality, lore, first_message, avatar) VALUES (?, ?, ?, ?, ?, ?)",
                            (c_name, c_prompt, c_pers, c_lore, json.dumps(f_msgs, ensure_ascii=False), avatar_bytes)
                        )
                        for sub in sub_list:
                            cursor.execute(
                                "INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore) VALUES (?, ?, ?, ?, ?)",
                                (c_name, sub.get("name"), sub.get("prompt"), sub.get("personality"), sub.get("lore"))
                            )
                        for q in quest_list:
                            cursor.execute(
                                "INSERT INTO quests (char_name, task_desc, reward_points) VALUES (?, ?, ?)",
                                (c_name, q.get("desc"), q.get("pts", 20))
                            )
                        conn.commit()
                        st.session_state.current_char = c_name
                        st.session_state.in_chat = True
                        st.success(f"🎉 สร้างตัวละคร '{c_name}' สำเร็จเรียบร้อยแล้ว!")
                        st.rerun()
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาด: {e}")

    elif sidebar_action == "🖼️ จัดการคลังรูปภาพ" and active_char:
        st.markdown(f"### 🖼️ จัดการคลังรูปภาพของ: `{active_char}`")
        with st.form(f"upload_photo_form_{active_char}", clear_on_submit=True):
            new_photos = st.file_uploader("อัปโหลดรูปภาพเข้าคลัง:", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
            if st.form_submit_button("📥 บันทึกรูปลงคลัง", use_container_width=True) and new_photos:
                for photo_file in new_photos:
                    p_bytes = photo_file.getvalue()
                    p_hash = hashlib.md5(p_bytes).hexdigest()
                    cursor.execute("INSERT INTO character_photos (char_name, photo, photo_hash) VALUES (?, ?, ?)", (active_char, p_bytes, p_hash))
                conn.commit()
                st.success("อัปโหลดรูปภาพสำเร็จ!")
                st.rerun()

        cursor.execute("SELECT id, photo FROM character_photos WHERE char_name = ?", (active_char,))
        photos_in_db = cursor.fetchall()
        if photos_in_db:
            cols_img = st.columns(3)
            for idx, (p_id, p_blob) in enumerate(photos_in_db):
                with cols_img[idx % 3]:
                    with st.container(border=True):
                        st.image(Image.open(io.BytesIO(p_blob)), use_container_width=True)
                        if st.button("🗑️ ลบรูปนี้", key=f"del_photo_{p_id}", use_container_width=True):
                            cursor.execute("DELETE FROM character_photos WHERE id = ?", (p_id,))
                            conn.commit()
                            st.rerun()

    elif sidebar_action == "👥 จัดการตัวละครเสริม" and active_char:
        st.markdown(f"### 👥 ตัวละครเสริมในเรื่อง: `{active_char}`")
        sub_action = st.radio("เลือกการทำงาน:", ["➕ เพิ่มตัวละครเสริม", "✏️ แก้ไข/เลื่อนขั้น"], key="sub_rad")
        if sub_action == "➕ เพิ่มตัวละครเสริม":
            with st.form("add_sub", clear_on_submit=True):
                s_name = st.text_input("ชื่อตัวละครเสริม:")
                s_p = st.text_area("คาแรคเตอร์:")
                s_pers = st.text_area("บุคลิก:")
                s_l = st.text_area("เรื่องราว:")
                if st.form_submit_button("➕ บันทึก", use_container_width=True) and s_name:
                    cursor.execute("INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore) VALUES (?, ?, ?, ?, ?)", (active_char, s_name, s_p, s_pers, s_l))
                    conn.commit()
                    st.success("บันทึกสำเร็จ!")
                    st.rerun()
        else:
            cursor.execute("SELECT id, sub_name, sub_prompt, sub_personality, sub_lore, sub_avatar FROM supporting_characters WHERE char_name = ?", (active_char,))
            sub_list = cursor.fetchall()
            if sub_list:
                sub_dict = {s[1]: s[0] for s in sub_list}
                sel_sub_name = st.selectbox("เลือกตัวละครเสริม:", list(sub_dict.keys()))
                sel_id = sub_dict[sel_sub_name]
                s_info = next(s for s in sub_list if s[0] == sel_id)
                if st.button(f"⭐ เลื่อนขั้น '{s_info[1]}' ขึ้นเป็นตัวละครหลัก", use_container_width=True):
                    cursor.execute("INSERT OR REPLACE INTO characters (name, prompt, personality, lore, first_message, avatar) VALUES (?, ?, ?, ?, ?, ?)", (s_info[1], s_info[2], s_info[3], s_info[4], json.dumps([f"*หันมามองคุณ* \"มีอะไรเหรอ?\""], ensure_ascii=False), s_info[5]))
                    cursor.execute("DELETE FROM supporting_characters WHERE id = ?", (sel_id,))
                    conn.commit()
                    st.session_state.current_char = s_info[1]
                    st.session_state.in_chat = True
                    st.success("เลื่อนขั้นสำเร็จ!")
                    st.rerun()