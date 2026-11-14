import streamlit as st
import json
import random
import urllib.request
import hashlib
from PIL import Image
import io
import time

SYSTEM_VERSION = "v2.9.1-Fixed"
BUILD_DATE = "2026-11-14"

def run_with_timer(title_text, total_seconds=5):
    bar = st.progress(0, text=f"{title_text} (กำลังเริ่มต้น...)")
    for i in range(total_seconds):
        time.sleep(1.0)
        percent = int(((i + 1) / total_seconds) * 100)
        remaining = total_seconds - (i + 1)
        bar.progress(percent, text=f"{title_text} — คาดว่าจะเสร็จในอีก {remaining} วินาที...")
    bar.empty()

def render_admin_sidebar(cursor, conn, all_chars, active_char, is_admin, current_user):
    cursor.execute("SELECT user_name, user_persona, pronoun_speak, pronoun_desc, call_speak, call_desc FROM users WHERE username = ?", (current_user,))
    p_row = cursor.fetchone()
    u_name, u_persona, u_pspeak, u_pdesc, u_cspeak, u_cdesc = p_row if p_row else (current_user, "", "", "", "", "")

    with st.expander("⚙️ ตั้งค่าบทบาทตัวตนของคุณ"):
        if active_char:
            if st.button("✨ ให้ AI สร้างบทบาทให้เข้ากับเรื่องนี้", use_container_width=True):
                run_with_timer("AI กำลังวิเคราะห์และสร้างบทบาทตัวผู้เล่น", 4)
                try:
                    cursor.execute("SELECT prompt, personality, lore FROM characters WHERE name = ?", (active_char,))
                    c_info = cursor.fetchone()
                    c_p, c_pers, c_l = c_info if c_info else ("", "", "")

                    ai_prompt = (
                        f"คุณคือผู้ช่วยสร้างบทบาทผู้เล่น (User Persona) สำหรับนำไปสวมบทบาทร่วมกับตัวละครหลักชื่อ '{active_char}'\n"
                        f"ข้อมูลตัวละครหลัก: {c_p} | นิสัย: {c_pers} | เรื่องราว: {c_l}\n\n"
                        f"กรุณาสร้างข้อมูลผู้เล่นในรูปแบบ JSON 1 บรรทัด (ห้ามมีข้อความอื่นปน) ดังนี้:\n"
                        '{"user_name": "ชื่อตัวละครผู้เล่น", "user_persona": "ประวัติหรือความสัมพันธ์กับตัวละครหลักสั้นๆ", "pronoun_speak": "สรรพนามพูด เช่น ผม/ฉัน", "pronoun_desc": "สรรพนามบรรยาย เช่น เขา/เธอ", "call_speak": "สรรพนามเรียกตัวละคร เช่น คุณ/เธอ", "call_desc": "สรรพนามเรียกตอนบรรยาย เช่น ชายหนุ่ม"}'
                    )
                    api_key = st.secrets.get("GEMINI_API_KEY")
                    if api_key:
                        from google import genai
                        client = genai.Client(api_key=api_key)
                        ai_res = client.models.generate_content(model="gemini-3.5-flash-lite", contents=ai_prompt)
                        res_text = ai_res.text.strip()
                        if "{" in res_text and "}" in res_text:
                            json_str = res_text[res_text.find("{"):res_text.rfind("}")+1]
                            p_data = json.loads(json_str)
                            cursor.execute("""
                                UPDATE users 
                                SET user_name = ?, user_persona = ?, pronoun_speak = ?, pronoun_desc = ?, call_speak = ?, call_desc = ? 
                                WHERE username = ?
                            """, (p_data.get("user_name", u_name), p_data.get("user_persona", u_persona), p_data.get("pronoun_speak", u_pspeak), p_data.get("pronoun_desc", u_pdesc), p_data.get("call_speak", u_cspeak), p_data.get("call_desc", u_cdesc), current_user))
                            conn.commit()
                            st.success("AI สร้างบทบาทให้เรียบร้อยแล้ว!")
                            st.rerun()
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาด: {e}")

        with st.form("user_persona_detailed_form"):
            edit_uname = st.text_input("ชื่อของคุณ:", value=u_name)
            edit_persona = st.text_area("บทบาทของคุณ:", value=u_persona, height=80)
            
            st.markdown("---")
            col_p1, col_p2 = st.columns(2)
            with col_p1: edit_pspeak = st.text_input("สรรพนามพูด:", value=u_pspeak)
            with col_p2: edit_pdesc = st.text_input("สรรพนามบรรยาย:", value=u_pdesc)
            
            col_c1, col_c2 = st.columns(2)
            with col_c1: edit_cspeak = st.text_input("ตัวละครเรียก (พูด):", value=u_cspeak)
            with col_c2: edit_cdesc = st.text_input("ตัวละครเรียก (บรรยาย):", value=u_cdesc)

            if st.form_submit_button("💾 บันทึกบทบาท", use_container_width=True):
                cursor.execute("""
                    UPDATE users 
                    SET user_name = ?, user_persona = ?, pronoun_speak = ?, pronoun_desc = ?, call_speak = ?, call_desc = ? 
                    WHERE username = ?
                """, (edit_uname, edit_persona, edit_pspeak, edit_pdesc, edit_cspeak, edit_cdesc, current_user))
                conn.commit()
                st.success("บันทึกเรียบร้อย!")
                st.rerun()

    st.divider()
    title_text = "🛠️ จัดการระบบ (Admin Only)" if is_admin else "⚙️ จัดการตัวละครของฉัน"
    st.markdown(f"### {title_text}")
    
    actions = [
        "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติ)",
        "🌐 นำเข้าตัวละครจากข้อมูลเว็บ (Smart Parser)",
        "➕ สร้างตัวละครหลักใหม่ (Manual)",
        "✏️ แก้ไขข้อมูลตัวละครหลัก",
        "🗑️ ลบตัวละครหลัก",
        "👥 จัดการตัวละครเสริม",
        "🎯 จัดการภารกิจ (Quest Log)",
        "🖼️ จัดการคลังรูปภาพ",
        "💾 สำรองข้อมูลระบบ (Backup DB)",
        "🔍 ตรวจสอบเวอร์ชันและสถานะระบบ (Version Inspector)"
    ]
    if is_admin:
        actions.append("👥 จัดการผู้ใช้งานระบบ")

    sidebar_action = st.selectbox("เลือกการจัดการ:", actions)
    return sidebar_action

def handle_admin_actions(sidebar_action, cursor, conn, all_chars, active_char, client, model_name, current_user, is_admin):
    
    def get_manageable_chars():
        if is_admin:
            return all_chars
        else:
            cursor.execute("SELECT name FROM characters WHERE creator = ?", (current_user,))
            return [row[0] for row in cursor.fetchall()]

    user_chars = get_manageable_chars()

    if sidebar_action == "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติ)":
        st.markdown("### ✨ สร้างตัวละครหลักด้วย AI")
        with st.form("ai_gen_char_form"):
            ai_target_name = st.text_input("ชื่อดารา หรือ ตัวละครหลัก:", placeholder="เช่น Mark Tuan, เซอร์เวรัส สเนป...")
            ai_submit_btn = st.form_submit_button("🚀 ให้ AI สร้างตัวละครนี้แบบครบชุด", use_container_width=True)

            if ai_submit_btn and ai_target_name:
                run_with_timer("AI กำลังเนรมิตข้อมูลตัวละครหลักและเรื่องราวเชิงลึก", 6)
                try:
                    prompt_gen = (
                        f"คุณคือผู้เชี่ยวชาญการสร้างข้อมูลตัวละครสำหรับ Roleplay กรุณาสร้างข้อมูลแบบละเอียดสำหรับ '{ai_target_name}' ในรูปแบบ JSON 1 บรรทัด (ห้ามมีเครื่องหมาย markdown หรือข้อความอื่นปนเด็ดขาด) โครงสร้างดังนี้:\n"
                        "{\n"
                        f'  "name": "{ai_target_name}",\n'
                        '  "prompt": "คาแรคเตอร์หลักและบทบาทของตัวละครนี้",\n'
                        '  "personality": "บุคลิกและนิสัยใจคอ",\n'
                        '  "lore": "เรื่องราวพื้นหลังและความสัมพันธ์",\n'
                        '  "first_messages": ["ข้อความเปิดตัวแบบที่ 1", "ข้อความเปิดตัวแบบที่ 2", "ข้อความเปิดตัวแบบที่ 3"],\n'
                        '  "sub_name": "ชื่อตัวละครเสริมรอบตัว 1 คน",\n'
                        '  "sub_prompt": "คาแรคเตอร์ตัวละครเสริม",\n'
                        '  "sub_personality": "บุคลิกตัวละครเสริม",\n'
                        '  "quest_desc": "ภารกิจเริ่มต้นชวนทำกิจกรรมร่วมกัน"\n'
                        "}"
                    )
                    response = client.models.generate_content(model=model_name, contents=prompt_gen)
                    raw_res = response.text.strip()

                    if "{" in raw_res and "}" in raw_res:
                        json_text = raw_res[raw_res.find("{"):raw_res.rfind("}")+1]
                        char_info = json.loads(json_text)
                        
                        c_name = char_info.get("name", ai_target_name)
                        c_prompt = char_info.get("prompt", "คุณคือ...")
                        c_pers = char_info.get("personality", "เงียบขรึม...")
                        c_lore = char_info.get("lore", "ประวัติความเป็นมา...")
                        f_msgs = char_info.get("first_messages", [f"สวัสดีครับ ผม {c_name} ยินดีที่ได้รู้จักครับ"])
                        s_name = char_info.get("sub_name", "ผู้จัดการส่วนตัว")
                        s_prompt = char_info.get("sub_prompt", "คอยดูแลตารางงาน")
                        s_pers = char_info.get("sub_personality", "เข้มงวด รักความสะอาด")
                        q_desc = char_info.get("quest_desc", "พูดคุยทำความรู้จักเพื่อเพิ่มความสนิทสนม")

                        cursor.execute(
                            "INSERT OR REPLACE INTO characters (name, prompt, personality, lore, first_message, avatar, creator) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (c_name, c_prompt, c_pers, c_lore, json.dumps(f_msgs, ensure_ascii=False), None, current_user)
                        )
                        cursor.execute(
                            "INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore) VALUES (?, ?, ?, ?, ?)",
                            (c_name, s_name, s_prompt, s_pers, "เป็นบุคคลใกล้ชิดในวงสังคม")
                        )
                        cursor.execute(
                            "INSERT INTO quests (char_name, task_desc, reward_points) VALUES (?, ?, ?)",
                            (c_name, q_desc, 20)
                        )
                        conn.commit()
                        st.session_state.current_char = c_name
                        st.session_state.in_chat = True
                        st.success(f"🎉 สร้างตัวละคร '{c_name}' พร้อมใช้งานสำเร็จเรียบร้อยแล้ว!")
                        st.rerun()
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาด: {e}")

    elif sidebar_action == "🌐 นำเข้าตัวละครจากข้อมูลเว็บ (Smart Parser)":
        st.markdown("### 🌐 นำเข้าตัวละครจากข้อมูลหน้าเว็บ")
        with st.form("smart_parser_form"):
            pasted_text = st.text_area("วางข้อมูลที่ก๊อปปี้มาจากหน้าเว็บที่นี่:", height=250)
            if st.form_submit_button("🚀 แปลงและบันทึกตัวละคร", use_container_width=True) and pasted_text:
                run_with_timer("AI กำลังวิเคราะห์ แยกแยะ และจัดโครงสร้างข้อมูล", 6)
                try:
                    parser_prompt = (
                        f"คุณคือผู้เชี่ยวชาญการแยกแยะและจัดโครงสร้างข้อมูลตัวละครสำหรับ AI Roleplay\n"
                        f"ข้อมูลดิบที่ผู้ใช้นำมาวาง:\n{pasted_text}\n\n"
                        f"กรุณาวิเคราะห์และส่งออกเป็นรูปแบบ JSON 1 บรรทัด (ห้ามมีเครื่องหมาย markdown หรือข้อความอื่นปนเด็ดขาด) โครงสร้างดังนี้:\n"
                        "{\n"
                        '  "name": "ชื่อตัวละครหลัก",\n'
                        '  "prompt": "สรุปคาแรคเตอร์หลัก",\n'
                        '  "personality": "รายละเอียดบุคลิก",\n'
                        '  "lore": "เรื่องราวพื้นหลัง",\n'
                        '  "first_messages": ["ข้อความเปิดตัว 1", "ข้อความเปิดตัว 2"],\n'
                        '  "supporting_chars": [{"name": "ชื่อตัวเสริม", "prompt": "บทบาท", "personality": "นิสัย", "lore": "ประวัติ"}],\n'
                        '  "quests": [{"desc": "ภารกิจ", "pts": 15}]\n'
                        "}"
                    )
                    response = client.models.generate_content(model=model_name, contents=parser_prompt)
                    raw_res = response.text.strip()
                    if "{" in raw_res and "}" in raw_res:
                        parsed_data = json.loads(raw_res[raw_res.find("{"):raw_res.rfind("}")+1])
                        c_name = parsed_data.get("name", "ตัวละครนำเข้า")
                        cursor.execute(
                            "INSERT OR REPLACE INTO characters (name, prompt, personality, lore, first_message, avatar, creator) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (c_name, parsed_data.get("prompt",""), parsed_data.get("personality",""), parsed_data.get("lore",""), json.dumps(parsed_data.get("first_messages",["สวัสดีครับ"]), ensure_ascii=False), None, current_user)
                        )
                        for sub in parsed_data.get("supporting_chars", []):
                            cursor.execute(
                                "INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore) VALUES (?, ?, ?, ?, ?)",
                                (c_name, sub.get("name",""), sub.get("prompt",""), sub.get("personality",""), sub.get("lore",""))
                            )
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
            m_msg1 = st.text_area("ข้อความเปิดตัว #1:", height=60)
            m_msg2 = st.text_area("ข้อความเปิดตัว #2:", height=60)
            m_msg3 = st.text_area("ข้อความเปิดตัว #3:", height=60)
            m_avatar = st.file_uploader("รูปโปรไฟล์ตัวละคร", type=["png", "jpg", "jpeg", "webp"])

            if st.form_submit_button("🚀 บันทึกตัวละคร", use_container_width=True) and m_name:
                avatar_bytes = m_avatar.getvalue() if m_avatar is not None else None
                combined_msgs = json.dumps([m.strip() for m in [m_msg1, m_msg2, m_msg3] if m.strip()], ensure_ascii=False)
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
        st.markdown(f"### ✏️ แก้ไขข้อมูล: `{active_char}`")
        if active_char:
            cursor.execute("SELECT prompt, personality, lore, first_message, avatar FROM characters WHERE name = ?", (active_char,))
            e_data = cursor.fetchone()
            if e_data:
                e_p, e_pers, e_lore, e_fmsg_json, e_avatar = e_data
                try:
                    old_msgs = json.loads(e_fmsg_json)
                except:
                    old_msgs = [e_fmsg_json]

                if st.button("✨ ให้ AI ช่วยขัดเกลา Prompt ให้คมขึ้น (Auto-Refine)", use_container_width=True):
                    run_with_timer("AI กำลังวิเคราะห์และขัดเกลา Prompt", 5)
                    try:
                        refine_prompt = (
                            f"คุณคือผู้เชี่ยวชาญการปรับแต่ง Prompt สำหรับ AI Roleplay\n"
                            f"ข้อมูลปัจจุบันของตัวละคร '{active_char}':\n- คาแรคเตอร์เดิม: {e_p}\n- บุคลิกเดิม: {e_pers}\n- เรื่องราวเดิม: {e_lore}\n\n"
                            f"กรุณาปรับปรุงและขัดเกลาข้อความเหล่านี้ให้มีความคมชัด สละสลวย แต่ต้องรักษาแก่นแท้เดิมไว้ ห้ามเปลี่ยนคาแรคเตอร์\n"
                            f"ส่งออกเป็น JSON 1 บรรทัด:\n"
                            '{"refined_prompt": "...", "refined_personality": "...", "refined_lore": "..."}'
                        )
                        ref_res = client.models.generate_content(model=model_name, contents=refine_prompt)
                        r_text = ref_res.text.strip()
                        if "{" in r_text and "}" in r_text:
                            r_json = json.loads(r_text[r_text.find("{"):r_text.rfind("}")+1])
                            e_p = r_json.get("refined_prompt", e_p)
                            e_pers = r_json.get("refined_personality", e_pers)
                            e_lore = r_json.get("refined_lore", e_lore)
                            st.success("✨ ขัดเกลาสำเร็จ! (กดบันทึกด้านล่างเพื่อยืนยัน)")
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {e}")

                with st.form("edit_char_manual_form"):
                    e_prompt = st.text_area("คาแรคเตอร์:", value=e_p, height=70)
                    e_pers_val = st.text_area("บุคลิก:", value=e_pers, height=70)
                    e_lore_val = st.text_area("เรื่องราว:", value=e_lore, height=70)
                    e_m1 = st.text_area("ข้อความ #1:", value=old_msgs[0] if len(old_msgs) > 0 else "", height=60)
                    e_m2 = st.text_area("ข้อความ #2:", value=old_msgs[1] if len(old_msgs) > 1 else "", height=60)
                    e_m3 = st.text_area("ข้อความ #3:", value=old_msgs[2] if len(old_msgs) > 2 else "", height=60)
                    edit_avatar = st.file_uploader("เปลี่ยนรูปโปรไฟล์", type=["png", "jpg", "jpeg", "webp"])

                    if st.form_submit_button("💾 บันทึกการแก้ไข", use_container_width=True):
                        new_avatar_bytes = edit_avatar.getvalue() if edit_avatar is not None else e_avatar
                        new_combined_msgs = json.dumps([m.strip() for m in [e_m1, e_m2, e_m3] if m.strip()], ensure_ascii=False)
                        cursor.execute(
                            "UPDATE characters SET prompt = ?, personality = ?, lore = ?, first_message = ?, avatar = ? WHERE name = ?",
                            (e_prompt, e_pers_val, e_lore_val, new_combined_msgs, new_avatar_bytes, active_char)
                        )
                        conn.commit()
                        st.success("บันทึกการแก้ไขสำเร็จ!")
                        st.rerun()
        else:
            st.info("กรุณาเลือกตัวละครหลักก่อน")

    elif sidebar_action == "🗑️ ลบตัวละครหลัก":
        st.markdown(f"### 🗑️ ลบตัวละคร: `{active_char}`")
        if active_char:
            st.warning(f"⚠️ การลบตัวละคร '{active_char}' จะลบข้อมูลแชท ภารกิจ และตัวละครเสริมทั้งหมดอย่างถาวร!")
            if st.button(f"🗑️ ยืนยันการลบ '{active_char}'", use_container_width=True):
                cursor.execute("DELETE FROM characters WHERE name = ?", (active_char,))
                cursor.execute("DELETE FROM supporting_characters WHERE char_name = ?", (active_char,))
                cursor.execute("DELETE FROM character_status WHERE char_name = ?", (active_char,))
                cursor.execute("DELETE FROM quests WHERE char_name = ?", (active_char,))
                cursor.execute("DELETE FROM character_photos WHERE char_name = ?", (active_char,))
                cursor.execute("DELETE FROM messages WHERE char_name = ?", (active_char,))
                cursor.execute("DELETE FROM novel_memories WHERE char_name = ?", (active_char,))
                conn.commit()
                st.success(f"ลบตัวละคร '{active_char}' เรียบร้อยแล้ว!")
                st.session_state.current_char = None
                st.session_state.in_chat = False
                st.rerun()
        else:
            st.info("กรุณาเลือกตัวละครหลักก่อน")

    elif sidebar_action == "👥 จัดการตัวละครเสริม":
        st.markdown(f"### 👥 จัดการตัวละครเสริมของ: `{active_char}`")
        if active_char:
            sub_action = st.radio("เลือกการทำงาน:", ["➕ เพิ่มตัวละครเสริม", "✏️ แก้ไขตัวละครเสริม", "🗑️ ลบตัวละครเสริม"], key="sub_rad")
            
            if sub_action == "➕ เพิ่มตัวละครเสริม":
                with st.form("add_sub_form", clear_on_submit=True):
                    s_name = st.text_input("ชื่อตัวละครเสริม:")
                    s_p = st.text_area("คาแรคเตอร์:")
                    s_pers = st.text_area("บุคลิก:")
                    s_l = st.text_area("เรื่องราว:")
                    if st.form_submit_button("➕ บันทึกตัวเสริม", use_container_width=True) and s_name:
                        cursor.execute("INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore) VALUES (?, ?, ?, ?, ?)", (active_char, s_name, s_p, s_pers, s_l))
                        conn.commit()
                        st.success("เพิ่มตัวละครเสริมสำเร็จ!")
                        st.rerun()
            elif sub_action == "✏️ แก้ไขตัวละครเสริม":
                cursor.execute("SELECT id, sub_name FROM supporting_characters WHERE char_name = ?", (active_char,))
                sub_list = cursor.fetchall()
                if sub_list:
                    sub_dict = {s[1]: s[0] for s in sub_list}
                    sel_sub_name = st.selectbox("เลือกตัวเสริมที่ต้องการแก้ไข:", list(sub_dict.keys()), key="edit_sub_sel_name")
                    sel_sub_id = sub_dict[sel_sub_name]
                    cursor.execute("SELECT sub_prompt, sub_personality, sub_lore FROM supporting_characters WHERE id = ?", (sel_sub_id,))
                    sub_info = cursor.fetchone()
                    if sub_info:
                        with st.form("edit_sub_form"):
                            e_s_name = st.text_input("ชื่อตัวละครเสริม:", value=sel_sub_name)
                            e_s_p = st.text_area("คาแรคเตอร์:", value=sub_info[0], height=70)
                            e_s_pers = st.text_area("บุคลิก:", value=sub_info[1], height=70)
                            e_s_l = st.text_area("เรื่องราว:", value=sub_info[2], height=70)
                            if st.form_submit_button("💾 บันทึกการแก้ไขตัวเสริม", use_container_width=True):
                                cursor.execute("UPDATE supporting_characters SET sub_name = ?, sub_prompt = ?, sub_personality = ?, sub_lore = ? WHERE id = ?", (e_s_name, e_s_p, e_s_pers, e_s_l, sel_sub_id))
                                conn.commit()
                                st.success("แก้ไขตัวละครเสริมสำเร็จ!")
                                st.rerun()
                else:
                    st.info("ยังไม่มีตัวละครเสริม")
            else:
                cursor.execute("SELECT id, sub_name FROM supporting_characters WHERE char_name = ?", (active_char,))
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
                    st.info("ยังไม่มีตัวละครเสริม")
        else:
            st.info("กรุณาเลือกตัวละครหลักก่อน")

    elif sidebar_action == "🎯 จัดการภารกิจ (Quest Log)":
        st.markdown(f"### 🎯 จัดการภารกิจของ: `{active_char}`")
        if active_char:
            with st.form("add_q_form", clear_on_submit=True):
                q_desc = st.text_input("รายละเอียดภารกิจใหม่:")
                q_pts = st.slider("คะแนนรางวัล:", 5, 100, 15)
                if st.form_submit_button("➕ เพิ่มภารกิจ", use_container_width=True) and q_desc:
                    cursor.execute("INSERT INTO quests (char_name, task_desc, reward_points) VALUES (?, ?, ?)", (active_char, q_desc, q_pts))
                    conn.commit()
                    st.success("เพิ่มภารกิจสำเร็จ!")
                    st.rerun()
        else:
            st.info("กรุณาเลือกตัวละครหลักก่อน")

    elif sidebar_action == "🖼️ จัดการคลังรูปภาพ":
        st.markdown(f"### 🖼️ จัดการคลังรูปภาพของ: `{active_char}`")
        if active_char:
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
        else:
            st.info("กรุณาเลือกตัวละครหลักก่อน")

    elif sidebar_action == "💾 สำรองข้อมูลระบบ (Backup DB)":
        st.markdown("### 💾 สำรองข้อมูลฐานข้อมูล (Backup Database)")
        st.info("คุณสามารถดาวน์โหลดไฟล์ฐานข้อมูล `roleplay_data.db` เก็บไว้สำรองเพื่อป้องกันข้อมูลสูญหายได้ที่นี่")
        try:
            with open("roleplay_data.db", "rb") as f:
                db_bytes = f.read()
            st.download_button(
                label="📥 ดาวน์โหลดไฟล์ Backup (.db)",
                data=db_bytes,
                file_name="roleplay_data_backup.db",
                mime="application/octet-stream",
                use_container_width=True
            )
        except Exception as e:
            st.warning("ยังไม่พบไฟล์ฐานข้อมูลในระบบ (ระบบจะสร้างให้อัตโนมัติเมื่อมีการใช้งาน)")

    elif sidebar_action == "🔍 ตรวจสอบเวอร์ชันและสถานะระบบ (Version Inspector)":
        st.markdown("### 🔍 ตรวจสอบเวอร์ชันและสถานะระบบ")
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM characters")
        total_chars = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM quests")
        total_quests = cursor.fetchone()[0]

        st.markdown(f"**🏷️ เวอร์ชันปัจจุบัน:** `{SYSTEM_VERSION}` (Build: `{BUILD_DATE}`)")
        st.markdown(f"**🤖 โมเดล AI หลัก:** `{model_name}`")
        st.divider()
        
        st.markdown("#### 📊 สถิติฐานข้อมูลระบบ:")
        col_v1, col_v2, col_v3 = st.columns(3)
        col_v1.metric("ผู้ใช้งานทั้งหมด", f"{total_users} บัญชี")
        col_v2.metric("ตัวละครในระบบ", f"{total_chars} ตัว")
        col_v3.metric("ภารกิจทั้งหมด", f"{total_quests} เควส")
        
        st.markdown("#### 🧩 สถานะโมดูลและฟีเจอร์หลัก:")
        features_status = {
            "🗄️ Database Engine (database.py)": "✅ พร้อมใช้งาน",
            "🛠️ Admin & User Panel (admin_panel.py)": "✅ พร้อมใช้งาน",
            "🌌 Main UI & Chat Engine (app.py)": "✅ พร้อมใช้งาน",
            "🛡️ AI Roleplay Auditor (กรรมการตรวจสอบ)": "✅ เปิดใช้งาน",
            "⚡ Cheat Commands (/+ชอบ, /+ผ่านภารกิจ)": "✅ เปิดใช้งาน",
            "💾 Auto Database Backup": "✅ เปิดใช้งาน"
        }
        for f_name, f_status in features_status.items():
            st.markdown(f"- {f_name}: `{f_status}`")

    elif sidebar_action == "👥 จัดการผู้ใช้งานระบบ" and is_admin:
        st.markdown("### 👥 จัดการผู้ใช้งานระบบ")
        cursor.execute("SELECT username, is_admin FROM users")
        users_list = cursor.fetchall()
        user_dict = {u[0]: bool(u[1]) for u in users_list}
        selected_target_user = st.selectbox("เลือกผู้ใช้งานที่ต้องการจัดการ:", list(user_dict.keys()))
        is_target_admin = user_dict[selected_target_user]
        
        with st.form("manage_user_form"):
            st.markdown(f"**กำลังจัดการผู้ใช้:** `{selected_target_user}`")
            if selected_target_user.lower() == "admin":
                st.info("ℹ️ บัญชี `admin` หลักถูกล็อกสิทธิ์ผู้ดูแลระบบไว้ถาวร")
                new_role_admin = True
            else:
                new_role_admin = st.checkbox("ตั้งค่าเป็นผู้ดูแลระบบ (Admin)", value=is_target_admin)
                
            new_pass = st.text_input("เปลี่ยนรหัสผ่านใหม่ (ปล่อยว่างถ้าไม่เปลี่ยน):", type="password")
            
            sub_col1, sub_col2 = st.columns(2)
            save_user = sub_col1.form_submit_button("💾 บันทึกการแก้ไข", use_container_width=True)
            del_user = sub_col2.form_submit_button("🗑️ ลบผู้ใช้นี้", use_container_width=True)

            if save_user:
                if selected_target_user.lower() == "admin" and not new_role_admin:
                    st.error("ไม่สามารถลดสิทธิ์บัญชี admin หลักได้!")
                else:
                    if new_pass.strip():
                        hashed_p = hashlib.sha256(new_pass.encode()).hexdigest()
                        cursor.execute("UPDATE users SET password = ?, is_admin = ? WHERE username = ?", (hashed_p, 1 if new_role_admin else 0, selected_target_user))
                    else:
                        cursor.execute("UPDATE users SET is_admin = ? WHERE username = ?", (1 if new_role_admin else 0, selected_target_user))
                    conn.commit()
                    st.success(f"อัปเดตข้อมูลผู้ใช้ '{selected_target_user}' สำเร็จ!")
                    st.rerun()

            if del_user:
                if selected_target_user.lower() == "admin":
                    st.error("❌ ไม่อนุญาตให้ลบบัญชีผู้ดูแลระบบหลัก (admin) เด็ดขาด!")
                elif selected_target_user == current_user:
                    st.error("คุณไม่สามารถลบบัญชีตัวเองในขณะที่กำลังใช้งานอยู่ได้!")
                else:
                    cursor.execute("DELETE FROM users WHERE username = ?", (selected_target_user,))
                    conn.commit()
                    st.success(f"ลบบัญชี '{selected_target_user}' เรียบร้อยแล้ว!")
                    st.rerun()
