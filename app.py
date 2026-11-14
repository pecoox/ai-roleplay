from google import genai
import streamlit as st
from PIL import Image
import io
import random
import json
from database import init_db, hash_password, get_relationship_level
from admin_panel import render_admin_sidebar, handle_admin_actions, run_with_timer

st.set_page_config(page_title="AI Roleplay - Universe & Character Hub", page_icon="🌌", layout="wide")

st.markdown("""
    <style>
    .stChatMessage { border-radius: 20px !important; padding: 18px 22px !important; margin-bottom: 16px !important; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid rgba(255,255,255,0.1); }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .affection-badge { display: inline-block; background: linear-gradient(135deg, rgba(255,105,180,0.2), rgba(138,43,226,0.2)); border: 1px solid rgba(255,105,180,0.4); border-radius: 20px; padding: 4px 12px; font-size: 12px; color: #ff99cc; font-weight: bold; }
    .stChatMessage p em, .stChatMessage em { color: #94a3b8 !important; font-style: normal !important; }
    .stChatMessage p { line-height: 1.7 !important; margin-bottom: 12px !important; }
    </style>
""", unsafe_allow_html=True)

conn = init_db()
cursor = conn.cursor()

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = None

if not api_key:
    st.warning("⚠️ ยังไม่ได้ตั้งค่า GEMINI_API_KEY ใน Streamlit Secrets")
    st.stop()

client = genai.Client(api_key=api_key)
model_name = "gemini-3.5-flash-lite"

# 🔄 ระบบจัดการ Session และ Query Params เพื่อกันหลุดเวลา Refresh หน้าเว็บ
query_params = st.query_params

if "logged_in" not in st.session_state:
    if "user" in query_params:
        u_check = query_params["user"]
        cursor.execute("SELECT username, is_admin FROM users WHERE username = ?", (u_check,))
        row = cursor.fetchone()
        if row:
            st.session_state.logged_in = True
            st.session_state.username = row[0]
            st.session_state.is_admin = bool(1 if row[0].lower() == "admin" else row[1])
        else:
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.is_admin = False
    else:
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.is_admin = False

if "in_chat" not in st.session_state: st.session_state.in_chat = False

# 🔐 หน้าจอ Login
if not st.session_state.logged_in:
    st.title("🌌 AI Roleplay - Universe Hub")
    tab1, tab2 = st.tabs(["🔑 เข้าสู่ระบบ", "📝 สมัครสมาชิก"])
    with tab1:
        with st.form("login_form"):
            l_user = st.text_input("Username")
            l_pass = st.text_input("Password", type="password")
            if st.form_submit_button("เข้าสู่ระบบ", use_container_width=True):
                cursor.execute("SELECT password, is_admin FROM users WHERE username = ?", (l_user,))
                row = cursor.fetchone()
                if row and row[0] == hash_password(l_pass):
                    st.session_state.logged_in = True
                    st.session_state.username = l_user
                    st.session_state.is_admin = bool(1 if l_user.lower() == "admin" else row[1])
                    st.query_params["user"] = l_user
                    st.success("เข้าสู่ระบบสำเร็จ!")
                    st.rerun()
                else:
                    st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    with tab2:
        with st.form("register_form"):
            r_user = st.text_input("ตั้ง Username")
            r_pass = st.text_input("ตั้ง Password", type="password")
            if st.form_submit_button("สมัครสมาชิก", use_container_width=True):
                if r_user and r_pass:
                    cursor.execute("SELECT username FROM users WHERE username = ?", (r_user,))
                    if cursor.fetchone():
                        st.error("ชื่อผู้ใช้นี้ถูกใช้งานแล้ว")
                    else:
                        cursor.execute("SELECT COUNT(*) FROM users")
                        assigned_admin = 1 if (r_user.lower() == "admin" or cursor.fetchone()[0] == 0) else 0
                        cursor.execute("INSERT INTO users (username, password, is_admin, user_name) VALUES (?, ?, ?, ?)", (r_user, hash_password(r_pass), assigned_admin, r_user))
                        conn.commit()
                        st.success("สมัครสมาชิกสำเร็จ! กรุณาไปที่แท็บเข้าสู่ระบบ")
    st.stop()

current_user = st.session_state.username
if current_user.lower() == "admin": st.session_state.is_admin = True
is_current_admin = st.session_state.is_admin

cursor.execute("SELECT user_name, user_persona, pronoun_speak, pronoun_desc, call_speak, call_desc FROM users WHERE username = ?", (current_user,))
p_row = cursor.fetchone()
u_name, u_persona, u_pspeak, u_pdesc, u_cspeak, u_cdesc = p_row if p_row else (current_user, "", "", "", "", "")

cursor.execute("SELECT name FROM characters")
all_chars = [row[0] for row in cursor.fetchall()]

if "current_char" not in st.session_state or st.session_state.current_char not in all_chars:
    st.session_state.current_char = all_chars[0] if all_chars else None

with st.sidebar:
    st.markdown(f"👤 **ผู้ใช้งาน:** `{current_user}`")
    if is_current_admin: st.markdown("🛡️ **สถานะ:** `ผู้ดูแลระบบ (Admin)`")
    else: st.markdown("👤 **สถานะ:** `ผู้ใช้งานทั่วไป (User)`")
    st.divider()

    sidebar_action = render_admin_sidebar(cursor, conn, all_chars, st.session_state.current_char, is_current_admin, current_user)

    if is_current_admin:
        manageable_chars = all_chars
    else:
        cursor.execute("SELECT name FROM characters WHERE creator = ?", (current_user,))
        manageable_chars = [row[0] for row in cursor.fetchall()]

    if manageable_chars and sidebar_action not in ["✨ สร้างตัวละครหลักด้วย AI (อัตโนมัติ)", "🌐 นำเข้าตัวละครจากข้อมูลเว็บ (Smart Parser)"]:
        selected_char = st.selectbox("เลือกตัวละครหลัก:", manageable_chars, index=manageable_chars.index(st.session_state.current_char) if st.session_state.current_char in manageable_chars else 0)
        if selected_char != st.session_state.current_char:
            st.session_state.current_char = selected_char
            st.rerun()

    st.divider()
    if st.button("🚪 ออกจากระบบ", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.is_admin = False
        st.session_state.in_chat = False
        if "user" in st.query_params: del st.query_params["user"]
        st.rerun()

    if st.button("🏠 กลับสู่หน้าแรก", use_container_width=True):
        st.session_state.in_chat = False
        st.session_state.current_char = None
        st.rerun()

    active_char = st.session_state.current_char
    handle_admin_actions(sidebar_action, cursor, conn, all_chars, active_char, client, model_name, current_user, is_current_admin)

# 🏠 หน้าแรก
if not st.session_state.in_chat:
    st.title("🔥 จักรวาลยอดนิยม & ตัวละครทั้งหมด")
    st.divider()
    if not all_chars:
        st.info("📭 ยังไม่มีตัวละครในระบบ กรุณาสร้างตัวละครหลักก่อนครับ")
    else:
        cols = st.columns(3)
        for idx, c_name in enumerate(all_chars):
            cursor.execute("SELECT prompt, personality, lore, avatar FROM characters WHERE name = ?", (c_name,))
            c_data = cursor.fetchone()
            c_prompt, c_pers, c_lore, c_av = (c_data[0], c_data[1], c_data[2], c_data[3]) if c_data else ("", "", "", None)
            
            with cols[idx % 3]:
                with st.container(border=True):
                    if c_av: st.image(Image.open(io.BytesIO(c_av)), use_container_width=True)
                    else: st.image("https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=500", use_container_width=True)
                    st.markdown(f"### 🌟 {c_name}")
                    
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        with st.popover("📖 ดูข้อมูล", use_container_width=True):
                            st.markdown(f"### 🌟 {c_name}")
                            st.markdown(f"**📌 คาแรคเตอร์:**\n{c_prompt}")
                            st.markdown(f"**🧠 บุคลิก/นิสัย:**\n{c_pers}")
                            st.markdown(f"**📖 เรื่องราวพื้นหลัง:**\n{c_lore}")
                            
                            cursor.execute("SELECT sub_name, sub_prompt, sub_lore FROM supporting_characters WHERE char_name = ?", (c_name,))
                            subs = cursor.fetchall()
                            if subs:
                                st.markdown("---")
                                st.markdown("**👥 ตัวละครเสริมในเรื่อง:**")
                                for s_name, s_p, s_l in subs:
                                    st.markdown(f"- **{s_name}**: {s_p} *({s_l})*")

                            cursor.execute("SELECT task_desc, reward_points FROM quests WHERE char_name = ?", (c_name,))
                            quests = cursor.fetchall()
                            if quests:
                                st.markdown("---")
                                st.markdown("**🎯 ภารกิจเริ่มต้น:**")
                                for q_desc, q_pts in quests:
                                    st.markdown(f"- {q_desc} `(+{q_pts} แต้ม)`")

                    with btn_col2:
                        if st.button("✨ แชท", key=f"b_{c_name}", use_container_width=True):
                            st.session_state.current_char = c_name
                            st.session_state.in_chat = True
                            st.rerun()
    st.stop()

# 💬 ห้องแชท
if st.session_state.in_chat and st.session_state.current_char:
    cursor.execute("SELECT prompt, personality, lore, first_message, avatar FROM characters WHERE name = ?", (st.session_state.current_char,))
    char_data = cursor.fetchone()
    base_prompt = char_data[0] if char_data else ""
    char_personality = char_data[1] if char_data else ""
    char_lore = char_data[2] if char_data else ""
    char_first_msg_raw = char_data[3] if char_data else "[]"
    char_avatar_img = Image.open(io.BytesIO(char_data[4])) if (char_data and char_data[4]) else None

    cursor.execute("SELECT sub_name, sub_prompt, sub_personality FROM supporting_characters WHERE char_name = ?", (st.session_state.current_char,))
    supporting_text = ", ".join([f"{s[0]} ({s[1]}, นิสัย: {s[2]})" for s in cursor.fetchall()]) or "ไม่มี"

    cursor.execute("INSERT OR IGNORE INTO character_status (username, char_name, affection_score, relationship_level) VALUES (?, ?, 0, 'คนแปลกหน้า')", (current_user, st.session_state.current_char))
    conn.commit()
    
    cursor.execute("SELECT affection_score, relationship_level FROM character_status WHERE username = ? AND char_name = ?", (current_user, st.session_state.current_char))
    status_row = cursor.fetchone()
    current_affection, current_rel_level = (status_row[0], status_row[1]) if status_row else (0, "คนแปลกหน้า")

    cursor.execute("SELECT memory_summary FROM novel_memories WHERE username = ? AND char_name = ?", (current_user, st.session_state.current_char))
    mem_row = cursor.fetchone()
    long_term_memory = mem_row[0] if mem_row else "ยังไม่มีเหตุการณ์สำคัญสะสม เริ่มต้นเรื่องราวใหม่"

    roleplay_instruction = f"""
คุณคือนักเขียนนิยายโรแมนติก/ดราม่าและผู้สวมบทบาทมืออาชีพ ตัวละครหลักชื่อ '{st.session_state.current_char}'
- ข้อมูลคาแรคเตอร์หลัก: {base_prompt}
- นิสัย: {char_personality}
- เรื่องราวพื้นหลัง (Lore): {char_lore}
- ตัวละครเสริมที่มีในเรื่อง: {supporting_text}
- ความทรงจำระยะยาว (Smart Memory Vault): "{long_term_memory}"

[ผู้สนทนา]: ชื่อ {u_name} | ประวัติ: {u_persona} | สรรพนามพูด: {u_pspeak} | สรรพนามบรรยาย: {u_pdesc} | เรียกผู้ใช้: {u_cspeak}
- ความสัมพันธ์ปัจจุบัน: "{current_rel_level}" (แต้มความชอบสะสม: {current_affection} แต้ม)

[กฎพฤติกรรมตามระดับความสัมพันธ์]:
- แต้มต่ำ (0-100 หรือ 'คนแปลกหน้า'): ระแวง เย็นชา หรือวางตัวตามคาแรคเตอร์ดั้งเดิม
- แต้มปานกลาง (200-400): เริ่มเปิดใจ เป็นกันเอง ยิ้มให้ และห่วงใยมากขึ้น
- แต้มสูง (500 ขึ้นไป เช่น 'คนรู้ใจ', 'คู่ชีวิต', 'โซลเมท'): คลั่งรัก อ่อนโยนเป็นพิเศษ เปิดเผยความรู้สึก ลึกซึ้ง และผูกพันขั้นสุด

[กฎการเขียนบทบาท]:
1. **จัดย่อหน้าและเว้นบรรทัดให้อ่านง่าย**: เคาะขึ้นบรรทัดใหม่แบ่งฉาก ท่าทาง บทพูด หรือตัวละครเสริมอย่างชัดเจน
2. **รูปแบบสัดส่วน**: 
   - บรรยาย ท่าทาง สีหน้า แววตา ความคิด ให้อยู่ในเครื่องหมาย *...* (แสดงผลสีเทาอ่อน ตัวตรงปกติ ไม่อียง)
   - บทพูด ใช้ "{st.session_state.current_char}: \"...\""
3. **การมีส่วนร่วมของตัวละครเสริม**: ดึงตัวละครเสริมเข้ามาโต้ตอบในฉากตามความเหมาะสม
4. **บรรทัดสุดท้ายต้องเป็น JSON รูปแบบนี้เป๊ะๆ ห้ามพลาดเด็ดขาด**:
{{"score_change": 2, "quest_update": null, "memory_update": "[สรุปเหตุการณ์สำคัญสั้นๆ 1 ประโยค]"}}
"""

    def get_random_first_msg(raw_json):
        try:
            msgs = json.loads(raw_json)
            if msgs: return random.choice(msgs)
        except: pass
        return "*ปรายตามองคุณด้วยความเรียบเฉย* \"มีธุระอะไร?\""

    cursor.execute("SELECT COUNT(*) FROM messages WHERE username = ? AND char_name = ?", (current_user, st.session_state.current_char))
    if cursor.fetchone()[0] == 0:
        init_msg = get_random_first_msg(char_first_msg_raw)
        cursor.execute("INSERT INTO messages (username, char_name, role, content) VALUES (?, ?, 'assistant', ?)", (current_user, st.session_state.current_char, init_msg))
        conn.commit()

    cursor.execute("SELECT role, content, image_blob FROM (SELECT role, content, image_blob, id FROM messages WHERE username = ? AND char_name = ? ORDER BY id DESC LIMIT 15) ORDER BY id ASC", (current_user, st.session_state.current_char))
    current_messages = [{"role": r[0], "content": r[1], "image": Image.open(io.BytesIO(r[2])) if r[2] else None} for r in cursor.fetchall()]

    col_av, col_title, col_reset = st.columns([1, 6, 2])
    with col_av:
        if char_avatar_img: st.image(char_avatar_img, width=60)
        else: st.image("https://api.iconify.design/lucide:user-round.svg", width=50)
    with col_title:
        st.markdown(f"### แชทกับ: `{st.session_state.current_char}` (ผู้ใช้: `{u_name}`)")
    with col_reset:
        if st.button("🔄 รีเซ็ตแชท", use_container_width=True):
            cursor.execute("DELETE FROM messages WHERE username = ? AND char_name = ?", (current_user, st.session_state.current_char))
            cursor.execute("UPDATE character_status SET affection_score = 0, relationship_level = 'คนแปลกหน้า' WHERE username = ? AND char_name = ?", (current_user, st.session_state.current_char))
            cursor.execute("DELETE FROM novel_memories WHERE username = ? AND char_name = ?", (current_user, st.session_state.current_char))
            cursor.execute("DELETE FROM user_quests WHERE username = ? AND quest_id IN (SELECT id FROM quests WHERE char_name = ?)", (current_user, st.session_state.current_char))
            
            new_m = get_random_first_msg(char_first_msg_raw)
            cursor.execute("INSERT INTO messages (username, char_name, role, content) VALUES (?, ?, 'assistant', ?)", (current_user, st.session_state.current_char, new_m))
            conn.commit()
            st.rerun()

    st.divider()

    for message in current_messages:
        if message["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(message["content"])
        else:
            with st.chat_message("assistant", avatar=char_avatar_img or "✨"):
                col_badge, col_pop = st.columns([4, 1.2])
                with col_badge:
                    st.markdown(f'<div class="affection-badge">💖 {current_rel_level} | คะแนนสะสม: {current_affection} แต้ม</div>', unsafe_allow_html=True)
                with col_pop:
                    with st.popover("🎯 ภารกิจ", use_container_width=True):
                        st.markdown("#### 🎯 รายการภารกิจ")
                        cursor.execute("SELECT id, task_desc, reward_points FROM quests WHERE char_name = ?", (st.session_state.current_char,))
                        quests_in_db = cursor.fetchall()
                        if quests_in_db:
                            for q_id, desc, pts in quests_in_db:
                                cursor.execute("SELECT is_completed FROM user_quests WHERE username = ? AND quest_id = ?", (current_user, q_id))
                                uq = cursor.fetchone()
                                is_comp = uq[0] if uq else 0
                                if is_comp:
                                    st.markdown(f"- ✅ **[#{q_id}]** ~~{desc}~~ — *สำเร็จแล้ว* (+{pts} แต้ม)")
                                else:
                                    st.markdown(f"- ⏳ **[#{q_id}]** {desc} — *ยังไม่สำเร็จ* (รางวัล: {pts} แต้ม)")
                        else:
                            st.caption("ยังไม่มีภารกิจในระบบ")

                st.markdown(message["content"])
                if message["image"]: st.image(message["image"], width=280)

    if user_input := st.chat_input(f"ส่งข้อความหา {st.session_state.current_char}..."):
        cursor.execute("INSERT INTO messages (username, char_name, role, content) VALUES (?, ?, 'user', ?)", (current_user, st.session_state.current_char, user_input))
        conn.commit()

        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        is_cheat = False
        bot_response = ""
        score_change = 0
        completed_q_id = None
        memory_update = None

        if user_input.startswith("/+ชอบ "):
            is_cheat = True
            try:
                score_change = int(user_input.replace("/+ชอบ ", "").strip())
                bot_response = f"*(สังเกตการณ์ระบบ: เพิ่มแต้มความชอบสะสมให้ {score_change} คะแนนเรียบร้อย)*"
            except:
                bot_response = "*(รูปแบบคำสั่งไม่ถูกต้อง ใช้ตัวอย่าง: `/+ชอบ 100`)*"
        elif user_input.startswith("/+ผ่านภารกิจ "):
            is_cheat = True
            try:
                completed_q_id = int(user_input.replace("/+ผ่านภารกิจ ", "").strip())
                cursor.execute("SELECT task_desc, reward_points FROM quests WHERE id = ? AND char_name = ?", (completed_q_id, st.session_state.current_char))
                q_data = cursor.fetchone()
                if q_data:
                    bot_response = f"*(สังเกตการณ์ระบบ: ทำภารกิจที่ #{completed_q_id} '{q_data[0]}' สำเร็จ! รับไป {q_data[1]} แต้ม)*"
                else:
                    bot_response = f"*(สังเกตการณ์ระบบ: ไม่พบภารกิจหมายเลข #{completed_q_id})*"
                    completed_q_id = None
            except:
                bot_response = "*(รูปแบบคำสั่งไม่ถูกต้อง ใช้ตัวอย่าง: `/+ผ่านภารกิจ 1`)*"

        with st.chat_message("assistant", avatar=char_avatar_img or "✨"):
            message_placeholder = st.empty()

            if is_cheat:
                time.sleep(0.3)
                message_placeholder.markdown(bot_response)
                eval_data = {"score_change": score_change, "quest_update": completed_q_id, "memory_update": None}
            else:
                message_placeholder.markdown("กำลังประพันธ์เรื่องราวระดับพรีเมียม...")
                bot_response = None
                eval_data = {}
                max_retries = 3

                for attempt in range(max_retries):
                    try:
                        formatted_history = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]} for m in current_messages]
                        chat = client.chats.create(
                            model=model_name,
                            history=formatted_history if formatted_history else None,
                            config={"system_instruction": roleplay_instruction, "temperature": 1.1}
                        )
                        response = chat.send_message(user_input)
                        raw_text = response.text

                        if "{" in raw_text and "}" in raw_text:
                            parts = raw_text.rsplit("{", 1)
                            bot_response = parts[0].strip()
                            try:
                                eval_data = json.loads("{" + parts[1])
                            except:
                                eval_data = {"score_change": 2, "quest_update": None, "memory_update": None}
                        else:
                            bot_response = raw_text
                            eval_data = {"score_change": 2, "quest_update": None, "memory_update": None}
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            message_placeholder.markdown(f"⚠️ กำลังเชื่อมต่อใหม่ครั้งที่ {attempt + 2}...")
                            time.sleep(1.5)
                        else:
                            bot_response = f"ขออภัย เกิดข้อผิดพลาดในการเชื่อมต่อ: `{str(e)}`"
                            eval_data = {"score_change": 0, "quest_update": None, "memory_update": None}
                message_placeholder.markdown(bot_response)

            if bot_response:
                score_change = eval_data.get("score_change", score_change)
                completed_q_id = eval_data.get("quest_update", completed_q_id)
                memory_update = eval_data.get("memory_update", None)

                if memory_update:
                    updated_memory_vault = f"{long_term_memory} -> {memory_update}" if long_term_memory != "ยังไม่มีเหตุการณ์สำคัญสะสม เริ่มต้นเรื่องราวใหม่" else memory_update
                    cursor.execute("INSERT OR REPLACE INTO novel_memories (username, char_name, memory_summary) VALUES (?, ?, ?)", (current_user, st.session_state.current_char, updated_memory_vault))

                quest_bonus = 0
                if completed_q_id:
                    cursor.execute("SELECT is_completed FROM user_quests WHERE username = ? AND quest_id = ?", (current_user, completed_q_id))
                    uq_row = cursor.fetchone()
                    if not uq_row or uq_row[0] == 0:
                        cursor.execute("SELECT reward_points FROM quests WHERE id = ?", (completed_q_id,))
                        q_info = cursor.fetchone()
                        if q_info:
                            quest_bonus = q_info[0]
                            cursor.execute("INSERT OR REPLACE INTO user_quests (username, quest_id, is_completed) VALUES (?, ?, 1)", (current_user, completed_q_id))

                updated_score = max(0, current_affection + score_change + quest_bonus)
                new_lvl = get_relationship_level(updated_score)

                cursor.execute("UPDATE character_status SET affection_score = ?, relationship_level = ? WHERE username = ? AND char_name = ?", (updated_score, new_lvl, current_user, st.session_state.current_char))

                attached_photo_bytes = None
                cursor.execute("SELECT photo FROM character_photos WHERE char_name = ?", (st.session_state.current_char,))
                photos = cursor.fetchall()
                if photos and random.random() < 0.30:
                    attached_photo_bytes = random.choice(photos)[0]

                if attached_photo_bytes:
                    st.image(Image.open(io.BytesIO(attached_photo_bytes)), width=280)

                cursor.execute("INSERT INTO messages (username, char_name, role, content, image_blob) VALUES (?, ?, 'assistant', ?, ?)", (current_user, st.session_state.current_char, bot_response, attached_photo_bytes))
                conn.commit()
                st.rerun()
