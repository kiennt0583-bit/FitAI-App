import streamlit as st
import pandas as pd
import json
import sqlite3
from datetime import date
import matplotlib.pyplot as plt

st.set_page_config(page_title="FitAI Pro", layout="wide")
st.title("💪 FitAI Pro - Trợ lý tập luyện thông minh")

# ====================== KHỞI TẠO & MIGRATE DATABASE ======================
def init_db():
    conn = sqlite3.connect('fitai.db')
    cursor = conn.cursor()
    
    # Tạo bảng nếu chưa có
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workout_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            exercise_name TEXT,
            set_number INTEGER,
            reps INTEGER,
            weight REAL,
            volume REAL
        )
    ''')
    
    # Migrate: Thêm cột volume nếu chưa có (cho database cũ)
    cursor.execute("PRAGMA table_info(workout_logs)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'volume' not in columns:
        cursor.execute("ALTER TABLE workout_logs ADD COLUMN volume REAL")
        # Cập nhật volume cho dữ liệu cũ
        cursor.execute("UPDATE workout_logs SET volume = set_number * reps * weight WHERE volume IS NULL")
    
    conn.commit()
    conn.close()

init_db()

# ====================== TẢI DỮ LIỆU ======================
@st.cache_data
def load_data():
    try:
        with open('gym_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except FileNotFoundError:
        st.error("Không tìm thấy file gym_data.json!")
        return pd.DataFrame()

df = load_data()

# ====================== TABS ======================
tab_tracker, tab_history, tab_coach = st.tabs(["🚀 FitAI Tracker", "📊 History & Progress", "🧠 FitAI Coach"])

# ====================== TAB TRACKER ======================
with tab_tracker:
    st.header("Nhật ký tập luyện hôm nay")

    muscle_filter = st.sidebar.multiselect(
        "Lọc theo nhóm cơ:", 
        options=df['muscle_gp'].unique() if not df.empty else [],
        default=[]
    )

    filtered_df = df[df['muscle_gp'].isin(muscle_filter)] if muscle_filter else df

    if 'current_exercise' not in st.session_state:
        st.session_state.current_exercise = filtered_df['exercise_name'].iloc[0] if not filtered_df.empty else ""

    col1, col2 = st.columns([3, 2])
    with col1:
        selected_ex = st.selectbox(
            "Chọn bài tập:", 
            options=filtered_df['exercise_name'].tolist() if not filtered_df.empty else [],
            index=0 if not filtered_df.empty else None,
            key="exercise_select"
        )
        st.session_state.current_exercise = selected_ex

    with col2:
        with st.form("workout_form", clear_on_submit=True):
            sets = st.number_input("Số hiệp (Sets)", min_value=1, value=3)
            reps = st.number_input("Số lần lặp (Reps)", min_value=1, value=10)
            weight = st.number_input("Khối lượng (kg)", min_value=0.0, value=0.0, step=0.5)
            
            submitted = st.form_submit_button("💾 Lưu buổi tập", type="primary")
            
            if submitted and selected_ex:
                volume = sets * reps * weight
                conn = sqlite3.connect('fitai.db')
                conn.execute('''INSERT INTO workout_logs 
                              (date, exercise_name, set_number, reps, weight, volume)
                              VALUES (?, ?, ?, ?, ?, ?)''', 
                              (date.today().isoformat(), selected_ex, int(sets), int(reps), float(weight), volume))
                conn.commit()
                conn.close()
                st.success(f"✅ Đã lưu **{selected_ex}** | Volume: **{volume:.0f}** kg")
                st.balloons()

    # === CHART TIẾN ĐỘ ===
    st.write("---")
    st.subheader(f"📈 Tiến độ: {st.session_state.current_exercise or 'Chưa chọn'}")
    
    conn = sqlite3.connect('fitai.db')
    volume_df = pd.read_sql('''
        SELECT date, SUM(volume) as volume 
        FROM workout_logs 
        WHERE exercise_name = ? 
        GROUP BY date 
        ORDER BY date ASC
    ''', conn, params=(st.session_state.current_exercise,))
    conn.close()

    if not volume_df.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(volume_df['date'], volume_df['volume'], marker='o', linewidth=2.5, color='#00ff88')
        ax.set_xlabel("Ngày")
        ax.set_ylabel("Volume (kg)")
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)
    else:
        st.info("Chưa có dữ liệu. Hãy tập và lưu buổi tập đầu tiên!")

# ====================== TAB HISTORY ======================
with tab_history:
    st.header("📊 Lịch sử tập luyện & Tiến độ tổng thể")
    
    conn = sqlite3.connect('fitai.db')
    logs = pd.read_sql("SELECT * FROM workout_logs ORDER BY date DESC, id DESC", conn)
    conn.close()

    if not logs.empty:
        st.dataframe(logs, use_container_width=True, hide_index=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Tổng buổi tập", len(logs['date'].unique()))
        with col2:
            st.metric("Tổng Volume", f"{logs['volume'].sum():,.0f} kg")
        with col3:
            st.metric("Số bài tập", logs['exercise_name'].nunique())
        
        # Volume theo tuần
        logs['date'] = pd.to_datetime(logs['date'])
        weekly = logs.resample('W', on='date')['volume'].sum()
        
        st.subheader("Volume theo tuần")
        fig2, ax2 = plt.subplots(figsize=(10, 4))
        ax2.bar(weekly.index.astype(str), weekly.values, color='#4dabf7')
        plt.xticks(rotation=45)
        st.pyplot(fig2)
    else:
        st.info("Chưa có dữ liệu. Hãy bắt đầu ghi nhật ký ở tab Tracker.")

# ====================== TAB COACH ======================
with tab_coach:
    st.header("🧠 AI Coach - Kế hoạch cá nhân hóa")
    
    col1, col2 = st.columns(2)
    with col1:
        weight_kg = st.number_input("Cân nặng (kg)", value=70.0, step=0.1)
        height_cm = st.number_input("Chiều cao (cm)", value=170.0, step=1.0)
        age = st.number_input("Tuổi", value=25, step=1)
        gender = st.selectbox("Giới tính", ["Nam", "Nữ"])
    
    with col2:
        activity_level = st.selectbox("Mức độ hoạt động", [
            "Ít vận động (ngồi văn phòng)", 
            "Vận động nhẹ (1-3 buổi/tuần)", 
            "Vận động trung bình (3-5 buổi/tuần)",
            "Vận động nhiều (6-7 buổi/tuần)"
        ])
        goal = st.selectbox("Mục tiêu chính", ["Tăng cơ", "Giảm mỡ", "Giữ cân"])

    if st.button("📋 Tính toán & Gợi ý kế hoạch", type="primary"):
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if gender == "Nam" else -161)
        
        multipliers = {
            "Ít vận động (ngồi văn phòng)": 1.2,
            "Vận động nhẹ (1-3 buổi/tuần)": 1.375,
            "Vận động trung bình (3-5 buổi/tuần)": 1.55,
            "Vận động nhiều (6-7 buổi/tuần)": 1.725
        }
        tdee = bmr * multipliers[activity_level]
        
        if goal == "Tăng cơ":
            calories = tdee + 300
            protein = weight_kg * 2.2
        elif goal == "Giảm mỡ":
            calories = tdee - 500
            protein = weight_kg * 2.0
        else:
            calories = tdee
            protein = weight_kg * 1.8

        fat = calories * 0.25 / 9
        carb = (calories - (protein * 4) - (fat * 9)) / 4

        st.success(f"### Calo hàng ngày: **{int(calories)} kcal**")
        st.write(f"**Protein**: {int(protein)}g | **Carb**: {int(carb)}g | **Fat**: {int(fat)}g")

        st.write("---")
        st.subheader("Kế hoạch tập gợi ý")
        if goal == "Tăng cơ":
            st.write("**Push - Pull - Legs (6 buổi/tuần)**")
        elif goal == "Giảm mỡ":
            st.write("**Upper/Lower + Cardio**")
        else:
            st.write("**Full Body 3-4 buổi/tuần**")
        st.info("💡 Tăng dần trọng lượng khi bạn hoàn thành reps dễ dàng.")
