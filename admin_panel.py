import streamlit as st
import json
import random
import urllib.request
import hashlib
from PIL import Image
import io
from ai_engine import run_with_timer

def render_admin_sidebar(cursor, conn, all_chars, active_char, is_admin, current_user):
    title_text = "🛠️ จัดการระบบ (Admin Only)" if is_admin else "⚙️ จัดการตัวละครของฉัน"
    st.markdown(f"### {title_text}")
    
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
            *(["👥 จัดการผู้ใช้งานระบบ"] if is_admin else [])
        ]
    )
    return sidebar_action

def handle_admin_actions(sidebar_action, cursor, conn, all_chars, active_char, client, model_name, current_user, is_admin):
    
    # ฟังก์ชันดึงเฉพาะตัวละครที่ผู้ใช้มีสิทธิ์จัดการ
    def get_manageable_chars():
        if is_admin:
            return all_chars
        else:
            cursor.execute("SELECT name FROM characters WHERE creator = ?", (current_user,))
            return [row[0] for row in cursor.fetchall()]

    user_chars = get_manageable_chars()

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
                            "INSERT OR REPLACE INTO characters (name, prompt, personality, lore, first_message, avatar, creator) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (c_name, c_prompt, c_pers, c_lore, json.dumps(f_msgs, ensure_ascii=False), avatar_bytes, current_user)
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

    elif sidebar_action == "🌐 นำเข้าตัวละครจากข้อมูลเว็บ (Smart Parser)":
        st.markdown("### 🌐 นำเข้าตัวละครจากข้อมูลหน้าเว็บ")
        with st.form("smart_parser_form"):
            pasted_text = st.text_area("วางข้อมูลที่ก๊อปปี้มาจากหน้าเว็บที่นี่:", height=250)
            if st.form_submit_button("🚀 แปลงและบันทึกตัวละคร", use_container_width=True) and pasted_text:
                run_with_timer("AI กำลังวิเคราะห์ข้อมูล", 4)
                try:
                    parser_prompt = f"คุณคือผู้เชี่ยวชาญการจัดโครงสร้างข้อมูลตัวละคร\nข้อมูลดิบ:\n{pasted_text}\n\nส่งออกเป็น JSON 1 บรรทัด:\n{{\"name\": \"...\", \"prompt\": \"...\", \"personality\": \"...\", \"lore\": \"...\", \"first_messages\": [\"...\"], \"supporting_chars\": [{{\"name\": \"...\", \"prompt\": \"...\", \"personality\": \"...\", \"lore\": \"...\"}}], \"quests\": [{{\"desc\": \"...\", \"pts\": 15}}]}}"
                    response = client.models.generate_content(model=model_name, contents=parser_prompt)
                    raw_res = response.text.strip()
                    if "{" in raw_res and "}" in raw_res:
                        parsed_data = json.loads(raw_res[raw_res.find("{"):raw_res.rfind("}")+1])
                        c_name = parsed_data.get("name", "ตัวละครนำเข้า")
                        cursor.execute("INSERT OR REPLACE INTO characters (name, prompt, personality, lore, first_message, avatar, creator) VALUES (?, ?, ?, ?, ?, ?, ?)", (c_name, parsed_data.get("prompt",""), parsed_data.get("personality",""), parsed_data.get("lore",""), json.dumps(parsed_data.get("first_messages",["สวัสดีครับ"]), ensure_ascii=False), None, current_user))
                        for sub in parsed_data.get("supporting_chars", []):
                            cursor.execute("INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore) VALUES (?, ?, ?, ?, ?)", (c_name, sub.get("name",""), sub.get("prompt",""), sub.get("personality",""), sub.get("lore","")))
                        for q in parsed_data.get("quests", [{"desc": "พูดคุยทำความรู้จัก", "pts": 20}]):
                            cursor.execute("INSERT INTO quests (char_name, task_desc, reward_points) VALUES (?, ?, ?)", (c_name, q.get("desc",""), q.get("pts",20)))
                        conn.commit()
                        st.session_state.current_char = c_name
                        st.session_state.in_chat = True
                        st.success(f"นำเข้า '{c_name}' สำเร็จ!")
                        st.rerun()
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาด: {e}")

    elif sidebar_action == "➕ สร้างตัวละครหลักใหม่ (Manual)":
        st.markdown("### 📌 สร้างตัวละครหลัก (Manual)")
        with st.form("create_char_manual_form"):
            m_name = st.text_input("ชื่อตัวละครหลัก:")
            m_prompt = st.text_area("คาแรคเตอร์:", height=60)
            m_pers = st.text_area("บุคลิก:", height=60)
            m_lore = st.text_area("เรื่องราว:", height=60)
            
            st.markdown("---")
            st.markdown("##### 💬 ข้อความเปิดตัวแรก (3 แบบ สำหรับสุ่ม):")
            m_msg1 = st.text_area("ข้อความเปิดตัว #1:", height=60)
            m_msg2 = st.text_area("ข้อความเปิดตัว #2:", height=60)
            m_msg3 = st.text_area("ข้อความเปิดตัว #3:", height=60)
            
            m_avatar = st.file_uploader("รูปโปรไฟล์ตัวละคร", type=["png", "jpg", "jpeg", "webp"])

            if st.form_submit_button("🚀 บันทึกตัวละคร", use_container_width=True) and m_name:
                avatar_bytes = m_avatar.getvalue() if m_avatar is not None else None
                combined_msgs = json.dumps([m.strip() for m in [m_msg1, m_msg2, m_msg3] if m.strip()], ensure_ascii=False)
                if not combined_msgs or combined_msgs == "[]":
                    combined_msgs = json.dumps(["*ปรายตามองคุณด้วยความเรียบเฉย* \"มีธุระอะไร?\""], ensure_ascii=False)

                cursor.execute(
                    "INSERT OR REPLACE INTO characters (name, prompt, personality, lore, first_message, avatar, creator) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (m_name, m_prompt, m_pers, m_lore, combined_msgs, avatar_bytes, current_user)
                )
                conn.commit()
                st.session_state.current_char = m_name
                st.session_state.in_chat = True
                st.success(f"สร้างตัวละคร '{m_name}' สำเร็จ!")
                st.rerun()

    elif sidebar_action == "✏️ แก้ไขข้อมูลตัวละครหลัก":
        st.markdown("### ✏️ แก้ไขข้อมูลตัวละครหลัก")
        if user_chars:
            edit_target = st.selectbox("เลือกตัวละครของฉัน:", user_chars, key="edit_target_sel")
            cursor.execute("SELECT prompt, personality, lore, first_message, avatar FROM characters WHERE name = ?", (edit_target,))
            e_data = cursor.fetchone()
            if e_data:
                e_p, e_pers, e_lore, e_fmsg_json, e_avatar = e_data
                try:
                    old_msgs = json.loads(e_fmsg_json)
                except:
                    old_msgs = [e_fmsg_json]

                with st.form("edit_char_manual_form"):
                    e_prompt = st.text_area("คาแรคเตอร์:", value=e_p, height=70)
                    e_pers_val = st.text_area("บุคลิก:", value=e_pers, height=70)
                    e_lore_val = st.text_area("เรื่องราว:", value=e_lore, height=70)
                    
                    st.markdown("---")
                    st.markdown("##### 💬 แก้ไขข้อความเปิดตัว (3 แบบ):")
                    e_m1 = st.text_area("ข้อความ #1:", value=old_msgs[0] if len(old_msgs) > 0 else "", height=60)
                    e_m2 = st.text_area("ข้อความ #2:", value=old_msgs[1] if len(old_msgs) > 1 else "", height=60)
                    e_m3 = st.text_area("ข้อความ #3:", value=old_msgs[2] if len(old_msgs) > 2 else "", height=60)
                    
                    edit_avatar = st.file_uploader("เปลี่ยนรูปโปรไฟล์", type=["png", "jpg", "jpeg", "webp"])

                    if st.form_submit_button("💾 บันทึกการแก้ไข", use_container_width=True):
                        new_avatar_bytes = edit_avatar.getvalue() if edit_avatar is not None else e_avatar
                        new_combined_msgs = json.dumps([m.strip() for m in [e_m1, e_m2, e_m3] if m.strip()], ensure_ascii=False)
                        
                        cursor.execute(
                            "UPDATE characters SET prompt = ?, personality = ?, lore = ?, first_message = ?, avatar = ? WHERE name = ?",
                            (e_prompt, e_pers_val, e_lore_val, new_combined_msgs, new_avatar_bytes, edit_target)
                        )
                        conn.commit()
                        st.success("บันทึกการแก้ไขสำเร็จ!")
                        st.rerun()
        else:
            st.info("คุณยังไม่ได้สร้างตัวละครส่วนตัว")

    elif sidebar_action == "🗑️ ลบตัวละครหลัก":
        st.markdown("### 🗑️ ลบตัวละครหลัก")
        if user_chars:
            del_target = st.selectbox("เลือกตัวละครของฉัน:", user_chars, key="del_target_sel")
            if st.button("🗑️ ยืนยันการลบตัวละครนี้", use_container_width=True):
                cursor.execute("DELETE FROM characters WHERE name = ?", (del_target,))
                cursor.execute("DELETE FROM supporting_characters WHERE char_name = ?", (del_target,))
                cursor.execute("DELETE FROM character_status WHERE char_name = ?", (del_target,))
                cursor.execute("DELETE FROM quests WHERE char_name = ?", (del_target,))
                cursor.execute("DELETE FROM character_photos WHERE char_name = ?", (del_target,))
                cursor.execute("DELETE FROM messages WHERE char_name = ?", (del_target,))
                conn.commit()
                st.success(f"ลบตัวละคร '{del_target}' เรียบร้อยแล้ว!")
                st.session_state.current_char = None
                st.session_state.in_chat = False
                st.rerun()
        else:
            st.info("คุณยังไม่ได้สร้างตัวละครส่วนตัว")

    elif sidebar_action == "👥 จัดการตัวละครเสริม":
        st.markdown("### 👥 จัดการตัวละครเสริม")
        if user_chars:
            sub_target_char = st.selectbox("เลือกตัวละครของฉัน:", user_chars, key="sub_char_sel")
            sub_action = st.radio("เลือกการทำงาน:", ["➕ เพิ่มตัวละครเสริม", "✏️ แก้ไขตัวละครเสริม", "🗑️ ลบตัวละครเสริม"], key="sub_rad")
            
            if sub_action == "➕ เพิ่มตัวละครเสริม":
                with st.form("add_sub_form", clear_on_submit=True):
                    s_name = st.text_input("ชื่อตัวละครเสริม:")
                    s_p = st.text_area("คาแรคเตอร์:")
                    s_pers = st.text_area("บุคลิก:")
                    s_l = st.text_area("เรื่องราว:")
                    s_avatar = st.file_uploader("รูปภาพตัวละครเสริม", type=["png", "jpg", "jpeg", "webp"], key="add_sub_img")

                    if st.form_submit_button("➕ บันทึกตัวเสริม", use_container_width=True) and s_name:
                        s_avatar_bytes = s_avatar.getvalue() if s_avatar is not None else None
                        cursor.execute("INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore, sub_avatar) VALUES (?, ?, ?, ?, ?, ?)", (sub_target_char, s_name, s_p, s_pers, s_l, s_avatar_bytes))
                        conn.commit()
                        st.success("เพิ่มตัวละครเสริมสำเร็จ!")
                        st.rerun()
            elif sub_action == "✏️ แก้ไขตัวละครเสริม":
                cursor.execute("SELECT id, sub_name, sub_prompt, sub_personality, sub_lore, sub_avatar FROM supporting_characters WHERE char_name = ?", (sub_target_char,))
                sub_list = cursor.fetchall()
                if sub_list:
                    sub_dict = {s[1]: s[0] for s in sub_list}
                    sel_sub_name = st.selectbox("เลือกตัวเสริมที่ต้องการแก้ไข:", list(sub_dict.keys()), key="edit_sub_sel_name")
                    sel_sub_id = sub_dict[sel_sub_name]
                    sub_info = next(s for s in sub_list if s[0] == sel_sub_id)

                    with st.form("edit_sub_form"):
                        e_s_name = st.text_input("ชื่อตัวละครเสริม:", value=sub_info[1])
                        e_s_p = st.text_area("คาแรคเตอร์:", value=sub_info[2], height=70)
                        e_s_pers = st.text_area("บุคลิก:", value=sub_info[3], height=70)
                        e_s_l = st.text_area("เรื่องราว:", value=sub_info[4], height=70)
                        e_s_avatar = st.file_uploader("เปลี่ยนรูปภาพตัวละครเสริม", type=["png", "jpg", "jpeg", "webp"], key="edit_sub_img")

                        if st.form_submit_button("💾 บันทึกการแก้ไขตัวเสริม", use_container_width=True):
                            new_s_avatar_bytes = e_s_avatar.getvalue() if e_s_avatar is not None else sub_info[5]
                            cursor.execute("UPDATE supporting_characters SET sub_name = ?, sub_prompt = ?, sub_personality = ?, sub_lore = ?, sub_avatar = ? WHERE id = ?", (e_s_name, e_s_p, e_s_pers, e_s_l, new_s_avatar_bytes, sel_sub_id))
                            conn.commit()
                            st.success("แก้ไขตัวละครเสริมสำเร็จ!")
                            st.rerun()
                else:
                    st.info("ยังไม่มีตัวละครเสริมในตัวละครนี้ให้แก้ไข")
            else:
                cursor.execute("SELECT id, sub_name FROM supporting_characters WHERE char_name = ?", (sub_target_char,))
                sub_list = cursor.fetchall()
                if sub_list:
                    sub_dict = {s[1]: s[0] for s in sub_list}
                    sel_sub_name = st.selectbox("เลือกตัวเสริมที่ต้องการลบ:", list(sub_dict.keys()))
                    if st.button("🗑️ ยืนยันลบตัวเสริมนี้", use_container_width=True):
                        cursor.execute("DELETE FROM supporting_characters WHERE id = ?", (sub_dict[sel_sub_name],))
                        conn.commit()
                        st.success("ลบตัวละครเสริมสำเร็จ!")
                        st.rerun()
                else:
                    st.info("ยังไม่มีตัวละครเสริมในตัวละครนี้")
        else:
            st.info("คุณยังไม่ได้สร้างตัวละครส่วนตัว")

    elif sidebar_action == "🎯 จัดการภารกิจ (Quest Log)":
        st.markdown("### 🎯 จัดการภารกิจ (Quest Log)")
        if user_chars:
            q_target_char = st.selectbox("เลือกตัวละครของฉัน:", user_chars, key="q_char_sel")
            q_action = st.radio("เลือกการทำงาน:", ["➕ เพิ่มภารกิจ", "✏️ แก้ไขภารกิจ", "🗑️ ลบภารกิจ"], key="q_rad")

            if q_action == "➕ เพิ่มภารกิจ":
                with st.form("add_q_form", clear_on_submit=True):
                    q_desc = st.text_input("รายละเอียดภารกิจใหม่:")
                    q_pts = st.slider("คะแนนรางวัล:", 5, 100, 15)
                    if st.form_submit_button("➕ เพิ่มภารกิจ", use_container_width=True) and q_desc:
                        cursor.execute("INSERT INTO quests (char_name, task_desc, reward_points) VALUES (?, ?, ?)", (q_target_char, q_desc, q_pts))
                        conn.commit()
                        st.success("เพิ่มภารกิจสำเร็จ!")
                        st.rerun()
            elif q_action == "✏️ แก้ไขภารกิจ":
                cursor.execute("SELECT id, task_desc, reward_points FROM quests WHERE char_name = ?", (q_target_char,))
                q_list = cursor.fetchall()
                if q_list:
                    q_dict = {f"{q[1]} ({q[2]} แต้ม)": q[0] for q in q_list}
                    sel_q_label = st.selectbox("เลือกภารกิจที่ต้องการแก้ไข:", list(q_dict.keys()))
                    sel_q_id = q_dict[sel_q_label]
                    q_info = next(q for q in q_list if q[0] == sel_q_id)

                    with st.form("edit_q_form"):
                        eq_desc = st.text_input("รายละเอียดภารกิจ:", value=q_info[1])
                        eq_pts = st.slider("คะแนนรางวัล:", 5, 100, int(q_info[2]))
                        if st.form_submit_button("💾 บันทึกการแก้ไขภารกิจ", use_container_width=True):
                            cursor.execute("UPDATE quests SET task_desc = ?, reward_points = ? WHERE id = ?", (eq_desc, eq_pts, sel_q_id))
                            conn.commit()
                            st.success("แก้ไขภารกิจสำเร็จ!")
                            st.rerun()
                else:
                    st.info("ยังไม่มีภารกิจในตัวละครนี้ให้แก้ไข")
            else:
                cursor.execute("SELECT id, task_desc FROM quests WHERE char_name = ?", (q_target_char,))
                q_list = cursor.fetchall()
                if q_list:
                    q_dict = {q[1]: q[0] for q in q_list}
                    sel_q_desc = st.selectbox("เลือกภารกิจที่ต้องการลบ:", list(q_dict.keys()))
                    if st.button("🗑️ ยืนยันลบภารกิจนี้", use_container_width=True):
                        cursor.execute("DELETE FROM quests WHERE id = ?", (q_dict[sel_q_desc],))
                        conn.commit()
                        st.success("ลบภารกิจสำเร็จ!")
                        st.rerun()
                else:
                    st.info("ยังไม่มีภารกิจในตัวละครนี้")
        else:
            st.info("คุณยังไม่ได้สร้างตัวละครส่วนตัว")

    elif sidebar_action == "🖼️ จัดการคลังรูปภาพ":
        st.markdown("### 🖼️ จัดการคลังรูปภาพ")
        if user_chars:
            img_target_char = st.selectbox("เลือกตัวละครของฉัน:", user_chars, key="img_char_sel")
            with st.form(f"upload_photo_form_{img_target_char}", clear_on_submit=True):
                new_photos = st.file_uploader("อัปโหลดรูปภาพเข้าคลัง:", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
                if st.form_submit_button("📥 บันทึกรูปลงคลัง", use_container_width=True) and new_photos:
                    for photo_file in new_photos:
                        p_bytes = photo_file.getvalue()
                        p_hash = hashlib.md5(p_bytes).hexdigest()
                        cursor.execute("INSERT INTO character_photos (char_name, photo, photo_hash) VALUES (?, ?, ?)", (img_target_char, p_bytes, p_hash))
                    conn.commit()
                    st.success("อัปโหลดรูปภาพสำเร็จ!")
                    st.rerun()

            cursor.execute("SELECT id, photo FROM character_photos WHERE char_name = ?", (img_target_char,))
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
        else:
            st.info("คุณยังไม่ได้สร้างตัวละครส่วนตัว")

    elif sidebar_action == "👥 จัดการผู้ใช้งานระบบ" and is_admin:
        st.markdown("### 👥 รายชื่อผู้ใช้งานทั้งหมด")
        cursor.execute("SELECT username, is_admin FROM users")
        for u, adm in cursor.fetchall():
            st.markdown(f"- `{u}` ({'Admin' if adm else 'User'})")
