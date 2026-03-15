"""대시보드 공통 스타일"""

import os

import streamlit as st

CUSTOM_CSS = """
<style>
/* 전체 폰트 */
@import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* 페이지 상단 여백 축소 */
.block-container {
    padding-top: 2rem;
}

/* 카드 스타일 */
div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {
    align-items: center;
}

/* 뱃지 */
.badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
}
.badge-live {
    background: #dcfce7;
    color: #166534;
}
.badge-offline {
    background: #f3f4f6;
    color: #6b7280;
}
.badge-crawler-on {
    background: #dbeafe;
    color: #1e40af;
}
.badge-crawler-off {
    background: #f3f4f6;
    color: #9ca3af;
}

/* 스트리머 카드 */
.streamer-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 0.5rem;
    transition: box-shadow 0.2s;
}
.streamer-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.streamer-name {
    font-size: 1.1rem;
    font-weight: 600;
    color: #111827;
    margin: 0;
}
.streamer-id {
    font-size: 0.8rem;
    color: #9ca3af;
    font-family: monospace;
}

/* 메트릭 카드 */
.metric-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 12px;
    padding: 1.5rem;
    color: white;
    text-align: center;
}
.metric-card.green {
    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
}
.metric-card.orange {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}
.metric-card .metric-value {
    font-size: 2rem;
    font-weight: 700;
    margin: 0.3rem 0;
}
.metric-card .metric-label {
    font-size: 0.85rem;
    opacity: 0.9;
}

/* 섹션 제목 */
.section-title {
    font-size: 1.3rem;
    font-weight: 700;
    color: #111827;
    margin: 1.5rem 0 1rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #e5e7eb;
}

/* 입력 폼 스타일 */
div[data-testid="stTextInput"] input {
    border-radius: 8px;
}

/* 토글 라벨 숨김 + 크기 확대 */
div[data-testid="stToggle"] label p {
    font-size: 0 !important;
}
div[data-testid="stToggle"] label > div {
    transform: scale(1.4);
    transform-origin: left center;
}

/* 기본 사이드바 네비게이션 숨김 */
[data-testid="stSidebarNav"] {
    display: none;
}

/* 사이드바 섹션 제목 */
.sidebar-section {
    font-size: 0.75rem;
    font-weight: 600;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.8rem 0 0.4rem 0;
    margin: 0;
}
</style>
"""


def apply_style():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def metric_card(label: str, value: str, variant: str = "default"):
    cls = variant if variant != "default" else ""
    st.markdown(
        f"""<div class="metric-card {cls}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def badge(text: str, variant: str = "default"):
    return f'<span class="badge badge-{variant}">{text}</span>'


def section_title(text: str):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)


def render_sidebar():
    """커스텀 사이드바 렌더링"""
    metabase_url = os.environ.get("METABASE_URL", "http://localhost:3000")

    with st.sidebar:
        st.markdown(
            '<p style="font-size:1.2rem; font-weight:700; margin-bottom:0.2rem;">'
            "Chzzk Analytics</p>"
            '<p style="font-size:0.8rem; color:#9ca3af; margin-top:0;">데이터 파이프라인</p>',
            unsafe_allow_html=True,
        )

        st.divider()

        st.page_link("app.py", label="홈", icon="🏠")

        st.markdown('<p class="sidebar-section">데이터 수집</p>', unsafe_allow_html=True)
        st.page_link("pages/1_streamers.py", label="스트리머 관리", icon="📡")
        st.page_link("pages/2_stats.py", label="수집 통계", icon="📈")
        st.page_link("pages/3_database.py", label="데이터베이스", icon="🗄️")

        st.markdown('<p class="sidebar-section">데이터 분석</p>', unsafe_allow_html=True)
        st.page_link("pages/5_keywords.py", label="키워드 분석", icon="🔤")
        st.page_link(metabase_url, label="Metabase", icon="📊")

        st.markdown('<p class="sidebar-section">시스템</p>', unsafe_allow_html=True)
        st.page_link("pages/4_kafka.py", label="Kafka", icon="⚡")
