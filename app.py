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

# ====================== TAB COACH (AI THẬT - GROQ) ======================
with tab_coach:
    st.header("🧠 FitAI Coach - Trợ lý AI cá nhân")

    # Khởi tạo lịch sử chat
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Chào bạn! Tôi là FitAI Coach 🤖\n\nTôi có thể giúp bạn về lịch tập, dinh dưỡng, kỹ thuật bài tập, progressive overload... Bạn đang cần hỗ trợ gì hôm nay?"}
        ]

    # Hiển thị lịch sử chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Ô nhập câu hỏi
    if prompt := st.chat_input("Hỏi tôi bất kỳ điều gì về fitness..."):
        # Thêm tin nhắn người dùng
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Phản hồi từ AI
        with st.chat_message("assistant"):
            with st.spinner("FitAI Coach đang suy nghĩ..."):
                try:
                    from groq import Groq
                    
                    client = Groq(api_key="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")
                    
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[
                            {"role": "system", "content": """Bạn là FitAI Coach - một huấn luyện viên thể hình và dinh dưỡng chuyên nghiệp. 
                            Trả lời bằng tiếng Việt, nhiệt tình, dễ hiểu, dựa trên khoa học. 
                            Khuyến khích người dùng và luôn sẵn sàng hỏi thêm thông tin nếu cần."""},
                            *[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                        ],
                        temperature=0.7,
                        max_tokens=800
                    )
                    
                    answer = response.choices[0].message.content
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})

                except Exception as e:
                    st.error(f"Lỗi kết nối AI: {e}")
                    st.info("💡 Kiểm tra xem API Key còn hạn không hoặc thử lại sau.")
