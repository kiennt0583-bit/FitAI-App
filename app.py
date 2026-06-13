import streamlit as st
import pandas as pd
import json
import sqlite3
from datetime import date
import matplotlib.pyplot as plt

st.set_page_config(page_title="FitAI Pro", layout="wide")
st.title("💪 FitAI - Trợ lý tập luyện thông minh")

# Tải dữ liệu
@st.cache_data
def load_data():
    with open('gym_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return pd.DataFrame(data)

df = load_data()

# Tạo 2 tab lớn nhất
tab_tracker, tab_coach = st.tabs(["🚀 FitAI Tracker", "🧠 FitAI Coach"])

with tab_tracker:
    st.header("Nhật ký tập luyện")
    
    # Sidebar trong Tab Tracker
    muscle_filter = st.sidebar.multiselect("Chọn nhóm cơ (Tracker):", options=df['muscle_gp'].unique())
    filtered_df = df[df['muscle_gp'].isin(muscle_filter)] if muscle_filter else df

    # Form nhập liệu
    with st.form("workout_form", clear_on_submit=True):
        selected_ex = st.selectbox("Chọn bài tập:", filtered_df['exercise_name'].tolist())
        sets = st.number_input("Số hiệp (Sets)", min_value=1, value=3)
        reps = st.number_input("Số lần lặp (Reps)", min_value=1, value=10)
        weight = st.number_input("Khối lượng (kg)", min_value=0.0, value=0.0, step=0.5, format="%.2f")
        
        submitted = st.form_submit_button("Lưu buổi tập")
        if submitted:
            conn = sqlite3.connect('fitai.db')
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO workout_logs (date, exercise_name, set_number, reps, weight)
                            VALUES (?, ?, ?, ?, ?)''', (date.today(), selected_ex, int(sets), int(reps), float(weight)))
            conn.commit()
            conn.close()
            st.success(f"Đã lưu: {selected_ex}")

    # Biểu đồ tự động
    st.write("---")
    st.subheader(f"📈 Tiến độ của: {selected_ex}")
    conn = sqlite3.connect('fitai.db')
    volume_ex_df = pd.read_sql('SELECT date, (set_number * reps * weight) as volume FROM workout_logs WHERE exercise_name = ? ORDER BY date ASC', 
                              conn, params=(selected_ex,))
    conn.close()

    if not volume_ex_df.empty:
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.plot(volume_ex_df['date'], volume_ex_df['volume'], marker='o', color='g')
        st.pyplot(fig)
    else:
        st.info("Chưa có dữ liệu lịch sử.")

with tab_coach:
    st.header("🤖 AI Coach: Dinh dưỡng & Mục tiêu")
    col1, col2 = st.columns(2)
    with col1:
        weight_kg = st.number_input("Cân nặng (kg)", value=70.0)
        height_cm = st.number_input("Chiều cao (cm)", value=170.0)
        age = st.number_input("Tuổi", value=25)
    with col2:
        gender_ai = st.selectbox("Giới tính", ["Nam", "Nữ"])
        goal = st.selectbox("Mục tiêu", ["Tăng cơ", "Giảm mỡ", "Giữ cân"])

    if st.button("Tính toán dinh dưỡng"):
        s = 5 if gender_ai == "Nam" else -161
        tdee = (10 * weight_kg + 6.25 * height_cm - 5 * age + s) * 1.375
        if goal == "Tăng cơ": tdee += 300
        elif goal == "Giảm mỡ": tdee -= 300
        
        st.success(f"### Calo hàng ngày: {int(tdee)} kcal")
        st.write(f"- Protein: {int(weight_kg * 2)}g | Fat: {int(tdee * 0.25 / 9)}g | Carb: {int((tdee - (weight_kg * 2 * 4) - (tdee * 0.25)) / 4)}g")