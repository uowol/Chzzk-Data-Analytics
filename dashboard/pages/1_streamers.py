"""스트리머 관리 - 등록, 방송 상태, 크롤러 ON/OFF"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from modules.chzzk.api import fetch_channelName, fetch_streamingCheck
from modules.config import NID_AUT, NID_SES
from modules.postgresql import get_connection
from modules.postgresql.schema import init_schema

from dashboard.crawler_manager import is_crawler_running, start_crawler, stop_crawler
from dashboard.style import apply_style, badge, section_title

st.set_page_config(page_title="스트리머 관리", page_icon="📡", layout="wide")
apply_style()

st.markdown("""
<h1 style="font-weight: 800; margin-bottom: 0.2rem;">📡 스트리머 관리</h1>
<p style="color: #6b7280; margin-bottom: 1.5rem;">스트리머 등록, 방송 상태 확인, 크롤러 제어</p>
""", unsafe_allow_html=True)

# --- DB 초기화 ---
conn = get_connection()
init_schema(conn)

# --- 스트리머 등록 ---
section_title("스트리머 등록")

col_input, col_btn = st.columns([6, 1])
with col_input:
    input_url = st.text_input(
        "URL",
        placeholder="치지직 채널 URL 또는 ID를 입력하세요",
        label_visibility="collapsed",
    )
with col_btn:
    add_clicked = st.button("등록", use_container_width=True, type="primary")

if add_clicked and input_url:
    streamer_id = input_url.strip().rstrip("/").split("/")[-1]
    try:
        streamer_name = fetch_channelName(streamer_id)
    except Exception:
        st.error(f"채널 정보를 가져올 수 없습니다: `{streamer_id}`")
        streamer_name = None

    if streamer_name:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO streamers (streamer_id, streamer_name) VALUES (%s, %s) ON CONFLICT (streamer_id) DO NOTHING",
                (streamer_id, streamer_name),
            )
            conn.commit()
        st.success(f"**{streamer_name}** 등록 완료!")
        st.rerun()

# --- 등록된 스트리머 목록 ---
section_title("등록된 스트리머")

with conn.cursor() as cur:
    cur.execute("SELECT streamer_id, streamer_name, created_at FROM streamers ORDER BY created_at")
    streamers = cur.fetchall()

if not streamers:
    st.markdown("""
    <div style="text-align:center; padding: 3rem; color: #9ca3af;">
        <p style="font-size: 2rem; margin-bottom: 0.5rem;">📭</p>
        <p>등록된 스트리머가 없습니다.<br>위에서 채널 URL을 입력하여 등록하세요.</p>
    </div>
    """, unsafe_allow_html=True)
else:
    cookies = {"NID_SES": NID_SES, "NID_AUT": NID_AUT}

    for streamer_id, streamer_name, created_at in streamers:
        # 상태 조회
        try:
            is_live = fetch_streamingCheck(streamer_id, cookies)
        except Exception:
            is_live = False
        crawler_on = is_crawler_running(streamer_id)

        live_badge = badge("LIVE", "live") if is_live else badge("OFFLINE", "offline")
        crawler_badge = badge("수집 중", "crawler-on") if crawler_on else badge("대기", "crawler-off")

        with st.container(border=True):
            cols = st.columns([4, 2, 2, 1.5, 0.8])

            with cols[0]:
                st.markdown(
                    f'<p class="streamer-name">{streamer_name}</p>'
                    f'<span class="streamer-id">{streamer_id[:20]}...</span>',
                    unsafe_allow_html=True,
                )

            with cols[1]:
                st.markdown(f"<div style='padding-top:0.5rem'>{live_badge}</div>", unsafe_allow_html=True)

            with cols[2]:
                st.markdown(f"<div style='padding-top:0.5rem'>{crawler_badge}</div>", unsafe_allow_html=True)

            with cols[3]:
                toggled = st.toggle(
                    "크롤러",
                    value=crawler_on,
                    key=f"toggle_{streamer_id}",
                    disabled=not is_live and not crawler_on,
                    label_visibility="collapsed",
                )
                if toggled and not crawler_on:
                    start_crawler(streamer_id, streamer_name)
                    st.rerun()
                elif not toggled and crawler_on:
                    stop_crawler(streamer_id)
                    st.rerun()

            with cols[4]:
                if st.button("삭제", key=f"del_{streamer_id}"):
                    stop_crawler(streamer_id)
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM streamers WHERE streamer_id = %s", (streamer_id,))
                        conn.commit()
                    st.rerun()

conn.close()
