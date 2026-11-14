import time
import streamlit as st

def run_with_timer(title_text, total_seconds=30):
    bar = st.progress(0, text=f"{title_text} (กำลังเริ่มต้นประมวลผล...)")
    for i in range(total_seconds):
        time.sleep(1.0)
        percent = int(((i + 1) / total_seconds) * 100)
        remaining = total_seconds - (i + 1)
        bar.progress(percent, text=f"{title_text} — คาดว่าจะเสร็จในอีกประมาณ {remaining} วินาที (กำลังสร้างสรรค์เนื้อหาพรีเมียม)...")
    bar.empty()