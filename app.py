# ในส่วน Sidebar ของ app.py ให้ตรวจสอบการเรียกใช้ฟังก์ชันแบบนี้:
if st.session_state.logged_in:
  sidebar_action = render_admin_sidebar(
      cursor,
      conn,
      all_chars,
      st.session_state.current_char,
      is_current_admin,
      current_user,
  )

  # และตรงส่วนจัดการการกระทำ:
  handle_admin_actions(
      sidebar_action,
      cursor,
      conn,
      all_chars,
      active_char,
      client,
      model_name,
      current_user,
      is_current_admin,
  )
