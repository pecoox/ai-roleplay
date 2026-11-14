import streamlit as st
import io
import json
from PIL import Image
from database import check_database_status

def render_admin_sidebar(cursor, conn, all_chars, current_char, is_admin, current_user):
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🛠️ เมนูจัดการระบบ")
    
    actions = ["💬 หน้าหลักแชท"]
    
    if is_admin:
        actions.extend([
            "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติ)",
            "🌐 นำเข้าตัวละครจากข้อมูลเว็บ (Smart Parser)",
            "👥 จัดการตัวละครเสริม",
            "🎯 จัดการภารกิจ (Quests)",
            "🖼️ จัดการคลังรูปภาพตัวละคร",
            "🔍 ตรวจสอบสถานะฐานข้อมูล"
        ])
    else:
        actions.extend([
            "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติ)",
            "🖼️ จัดการคลังรูปภาพตัวละคร"
        ])

    selected_action = st.sidebar.selectbox("เลือกโหมดการทำงาน:", actions)
    return selected_action

def handle_admin_actions(action, cursor, conn, all_chars, active_char, client, model_name, current_user, is_admin):
    if action == "💬 หน้าหลักแชท":
        return

    # 🔍 ตรวจสอบสถานะฐานข้อมูล
    if action == "🔍 ตรวจสอบสถานะฐานข้อมูล":
        st.title("🔍 ตรวจสอบสถานะและสุขภาพฐานข้อมูล")
        st.divider()
        
        is_connected, db_info = check_database_status(conn)
        if is_connected:
            st.success("🟢 สถานะการเชื่อมต่อ: เชื่อมต่อกับ Supabase Cloud สำเร็จและเสถียรปกติ")
            st.metric(label="📊 ขนาดพื้นที่ฐานข้อมูลปัจจุบัน", value=db_info)
            
            cursor.execute("SELECT COUNT(*) FROM users;")
            u_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM characters;")
            c_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM messages;")
            m_count = cursor.fetchone()[0]
            
            col1, col2, col3 = st.columns(3)
            col1.metric("👥 ผู้ใช้งานทั้งหมด", f"{u_count} บัญชี")
            col2.metric("🌟 ตัวละครทั้งหมด", f"{c_count} ตัวละคร")
            col3.metric("💬 ข้อความในแชทสะสม", f"{m_count} ข้อความ")
        else:
            st.error(f"🔴 ขัดข้องในการเชื่อมต่อฐานข้อมูล: {db_info}")
        return

    # ✨ สร้างตัวละครหลักด้วย AI
    if action == "✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติ)":
        st.title("✨ สร้างตัวละครหลักด้วยระบบ AI อัตโนมัติ")
        st.divider()
        with st.form("ai_char_form"):
            char_idea = st.text_input("แนวคิดตัวละครหรือชื่อเรื่องที่อยากได้:", placeholder="เช่น หนุ่มมาเฟียผู้เย็นชาแต่คลั่งรัก, นักเวทย์สาวแห่งหอคอยโบราณ")
            submitted = st.form_submit_button("🚀 ให้ AI สร้างตัวละครให้ทันที", use_container_width=True)
            
            if submitted and char_idea:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=f"ออกแบบตัวละครสำหรับ Roleplay จากโจทย์: '{char_idea}' ขอเป็น JSON format: {{'name': 'ชื่อตัวละคร', 'prompt': 'คำอธิบายคาแรคเตอร์สั้นๆ', 'personality': 'นิสัย', 'lore': 'เรื่องราว', 'first_message': ['ประโยคทักทายที่ 1', 'ประโยคทักทายที่ 2']}}"
                    )
                    raw_res = response.text.strip()
                    if "```json" in raw_res:
                        raw_res = raw_res.split("```json")[1].split("```")[0].strip()
                    elif "```" in raw_res:
                        raw_res = raw_res.split("```")[1].split("```")[0].strip()
                    
                    data = json.loads(raw_res)
                    c_name = data.get("name", "ตัวละครไร้ชื่อ")
                    c_prompt = data.get("prompt", "")
                    c_pers = data.get("personality", "")
                    c_lore = data.get("lore", "")
                    c_first = json.dumps(data.get("first_message", ["*มองหน้าคุณ* \"มีอะไร?\""]), ensure_ascii=False)

                    cursor.execute("""
                        INSERT INTO characters (name, prompt, personality, lore, first_message, creator) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (name) DO UPDATE SET prompt = EXCLUDED.prompt, personality = EXCLUDED.personality, lore = EXCLUDED.lore
                    """, (c_name, c_prompt, c_pers, c_lore, c_first, current_user))
                    conn.commit()
                    st.success(f"🎉 สร้างตัวละคร '{c_name}' สำเร็จเรียบร้อย!")
                    st.rerun()
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดในการสร้างด้วย AI: {str(e)}")
        return

    # 🌐 นำเข้าตัวละครจากข้อมูลเว็บ
    if action == "🌐 นำเข้าตัวละครจากข้อมูลเว็บ (Smart Parser)":
        st.title("🌐 นำเข้าตัวละครจากข้อความ/ข้อมูลเว็บ")
        st.divider()
        with st.form("import_form"):
            i_name = st.text_input("ชื่อตัวละคร")
            i_prompt = st.text_area("รายละเอียด/คาแรคเตอร์ (Prompt)")
            i_pers = st.text_input("บุคลิก/นิสัย")
            i_lore = st.text_area("เรื่องราวพื้นหลัง (Lore)")
            i_first = st.text_area("ประโยคทักทายแรก (คั่นแต่ละประโยคด้วยการขึ้นบรรทัดใหม่)")
            
            if st.form_submit_button("📥 บันทึกนำเข้าตัวละคร", use_container_width=True):
                if i_name:
                    f_list = [line.strip() for line in i_first.split("\n") if line.strip()]
                    f_json = json.dumps(f_list if f_list else ["*มองคุณนิ่งๆ*"], ensure_ascii=False)
                    cursor.execute("""
                        INSERT INTO characters (name, prompt, personality, lore, first_message, creator) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (name) DO UPDATE SET prompt = EXCLUDED.prompt, personality = EXCLUDED.personality, lore = EXCLUDED.lore
                    """, (i_name, i_prompt, i_pers, i_lore, f_json, current_user))
                    conn.commit()
                    st.success(f"นำเข้าตัวละคร '{i_name}' สำเร็จ!")
                    st.rerun()
                else:
                    st.error("กรุณากรอกชื่อตัวละคร")
        return

    # 👥 จัดการตัวละครเสริม
    if action == "👥 จัดการตัวละครเสริม":
        st.title(f"👥 จัดการตัวละครเสริมสำหรับ: `{active_char}`")
        st.divider()
        if not active_char:
            st.warning("กรุณาเลือกตัวละครหลักก่อน")
            return
        
        with st.form("sub_char_form"):
            s_name = st.text_input("ชื่อตัวละครเสริม")
            s_prompt = st.text_input("บทบาทหน้าที่")
            s_pers = st.text_input("นิสัย")
            s_lore = st.text_input("ความเกี่ยวข้อง")
            if st.form_submit_button("➕ เพิ่มตัวละครเสริม"):
                if s_name:
                    cursor.execute("INSERT INTO supporting_characters (char_name, sub_name, sub_prompt, sub_personality, sub_lore) VALUES (%s, %s, %s, %s, %s)", (active_char, s_name, s_prompt, s_pers, s_lore))
                    conn.commit()
                    st.success(f"เพิ่มตัวละครเสริม {s_name} สำเร็จ!")
                    st.rerun()
        return

    # 🎯 จัดการภารกิจ
    if action == "🎯 จัดการภารกิจ (Quests)":
        st.title(f"🎯 จัดการภารกิจสำหรับ: `{active_char}`")
        st.divider()
        if not active_char:
            st.warning("กรุณาเลือกตัวละครหลักก่อน")
            return
            
        with st.form("quest_form"):
            q_desc = st.text_input("รายละเอียดภารกิจ")
            q_pts = st.number_input("แต้มรางวัลที่จะได้รับ", min_value=1, value=50)
            if st.form_submit_button("➕ เพิ่มภารกิจใหม่"):
                if q_desc:
                    cursor.execute("INSERT INTO quests (char_name, task_desc, reward_points) VALUES (%s, %s, %s)", (active_char, q_desc, q_pts))
                    conn.commit()
                    st.success("เพิ่มภารกิจสำเร็จ!")
                    st.rerun()
        return

    # 🖼️ จัดการคลังรูปภาพ
    if action == "🖼️ จัดการคลังรูปภาพตัวละคร":
        st.title(f"🖼️ คลังรูปภาพของ: `{active_char}`")
        st.divider()
        if not active_char:
            st.warning("กรุณาเลือกตัวละครหลักก่อน")
            return
            
        uploaded_file = st.file_uploader("อัปโหลดรูปภาพประกอบแชท (ส่งสุ่มระหว่างคุย)", type=["png", "jpg", "jpeg"])
        if uploaded_file and st.button("📤 อัปโหลดเข้าคลัง"):
            b_data = uploaded_file.getvalue()
            cursor.execute("INSERT INTO character_photos (char_name, photo) VALUES (%s, %s)", (active_char, psycopg2.Binary(b_data)))
            conn.commit()
            st.success("อัปโหลดรูปภาพสำเร็จ!")
            st.rerun()
        return
