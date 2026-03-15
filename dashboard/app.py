"""Chzzk Data Analytics Dashboard"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.style import apply_style, metric_card, section_title
from modules.postgresql import get_connection
from modules.postgresql.schema import init_schema

st.set_page_config(
    page_title="Chzzk Analytics",
    page_icon="📊",
    layout="wide",
)
apply_style()

# --- 헤더 ---
st.markdown("""
<div style="text-align:center; padding: 2rem 0 1rem 0;">
    <h1 style="font-size: 2.5rem; font-weight: 800; margin: 0;
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        Chzzk Data Analytics
    </h1>
    <p style="color: #6b7280; font-size: 1.1rem; margin-top: 0.5rem;">
        치지직 스트리밍 데이터 수집 및 분석 대시보드
    </p>
</div>
""", unsafe_allow_html=True)

st.divider()

# --- DB 요약 (5초마다 갱신) ---
@st.fragment(run_every=5)
def render_summary():
    conn = get_connection()
    init_schema(conn)

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM chat_messages")
        chat_total = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM streaming_events")
        streaming_total = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM streamers")
        streamer_total = cur.fetchone()[0]

    conn.close()

    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("등록 스트리머", f"{streamer_total}명")
    with col2:
        metric_card("수집 채팅", f"{chat_total:,}건", "green")
    with col3:
        metric_card("스트리밍 이벤트", f"{streaming_total:,}건", "orange")


render_summary()

st.markdown("<br>", unsafe_allow_html=True)

# --- 네비게이션 ---
section_title("바로가기")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.page_link("pages/1_streamers.py", label="📡  스트리머 관리", use_container_width=True)
with col2:
    st.page_link("pages/2_stats.py", label="📈  수집 통계", use_container_width=True)
with col3:
    st.page_link("pages/3_database.py", label="🗄️  데이터베이스", use_container_width=True)
with col4:
    st.page_link("pages/4_kafka.py", label="⚡  Kafka", use_container_width=True)
