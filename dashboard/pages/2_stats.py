"""수집 데이터 통계"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from modules.postgresql import get_connection
from dashboard.style import apply_style, metric_card, render_sidebar, section_title


def query_df(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return pd.DataFrame()
        cols = [desc[0] for desc in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


st.set_page_config(page_title="수집 통계", page_icon="📈", layout="wide")
apply_style()
render_sidebar()

st.markdown("""
<h1 style="font-weight: 800; margin-bottom: 0.2rem;">📈 수집 통계</h1>
<p style="color: #6b7280; margin-bottom: 1.5rem;">수집된 데이터 현황 및 분석</p>
""", unsafe_allow_html=True)


# --- 전체 요약 (5초마다 갱신) ---
@st.fragment(run_every=5)
def render_summary():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM chat_messages")
        chat_total = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM streaming_events")
        streaming_total = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM chat_messages WHERE msg_type = 'DONATION'")
        donation_total = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(sum(pay_amount), 0) FROM chat_messages WHERE msg_type = 'DONATION'")
        donation_amount = cur.fetchone()[0]
        cur.execute("""
            SELECT COALESCE(sum(pg_total_relation_size(c.oid)), 0)
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname IN ('chat_messages', 'streaming_events', 'streamers')
        """)
        db_bytes = cur.fetchone()[0]
    conn.close()

    if db_bytes >= 1024 ** 3:
        db_size_text = f"{db_bytes / (1024**3):.2f} GB"
    else:
        db_size_text = f"{db_bytes / (1024**2):.1f} MB"

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        metric_card("총 채팅", f"{chat_total:,}")
    with col2:
        metric_card("스트리밍 이벤트", f"{streaming_total:,}", "green")
    with col3:
        metric_card("도네이션", f"{donation_total:,}건", "orange")
    with col4:
        metric_card("도네이션 총액", f"{donation_amount:,}원", "orange")
    with col5:
        metric_card("DB 용량", db_size_text, "green")


render_summary()

st.markdown("<br>", unsafe_allow_html=True)

# --- 필터 ---
section_title("필터")

conn = get_connection()

col_filter1, col_filter2 = st.columns(2)

with conn.cursor() as cur:
    cur.execute("""
        SELECT DISTINCT name FROM (
            SELECT streamer_name AS name FROM streamers
            UNION
            SELECT streamer FROM chat_messages
        ) t ORDER BY name
    """)
    streamer_list = [row[0] for row in cur.fetchall()]

with col_filter1:
    selected_streamer = st.selectbox("스트리머", options=["전체"] + streamer_list, index=0)

with col_filter2:
    selected_type = st.selectbox(
        "메시지 유형",
        options=["전체", "CHAT", "DONATION", "SUBSCRIPTION", "DELETED_CHAT"],
        index=0,
    )

where_clauses = []
params = []
if selected_streamer != "전체":
    where_clauses.append("streamer = %s")
    params.append(selected_streamer)
if selected_type != "전체":
    where_clauses.append("msg_type = %s")
    params.append(selected_type)
where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

# --- 스트리머별 유형 통계 + 시간대별 수집량 + 도네이션 랭킹 (5초 갱신) ---
@st.fragment(run_every=5)
def render_stats():
    _conn = get_connection()

    # 스트리머별 메시지 유형
    section_title("스트리머별 메시지 유형")

    query = f"""
        SELECT streamer, msg_type, count(*) as cnt
        FROM chat_messages {where_sql}
        GROUP BY streamer, msg_type
        ORDER BY streamer, cnt DESC
    """
    df_types = query_df(_conn, query, params or None)

    if not df_types.empty:
        pivot = df_types.pivot_table(
            index="streamer", columns="msg_type", values="cnt", fill_value=0, aggfunc="sum"
        )
        tab1, tab2 = st.tabs(["테이블", "차트"])
        with tab1:
            st.dataframe(pivot, width="stretch")
        with tab2:
            st.bar_chart(pivot)
    else:
        st.info("데이터가 없습니다.")

    # 시간대별 수집량 (스트리머별 라인 차트, 분 단위)
    section_title("시간대별 수집량")

    query_hourly = f"""
        SELECT date_trunc('minute', ts) as minute, streamer, count(*) as cnt
        FROM chat_messages {where_sql}
        GROUP BY minute, streamer ORDER BY minute
    """
    df_hourly = query_df(_conn, query_hourly, params or None)

    if not df_hourly.empty:
        pivot_hourly = df_hourly.pivot_table(
            index="minute", columns="streamer", values="cnt", fill_value=0, aggfunc="sum"
        )
        st.line_chart(pivot_hourly)
    else:
        st.info("데이터가 없습니다.")

    # 도네이션 랭킹
    section_title("도네이션 랭킹")

    donation_where = where_clauses.copy()
    donation_params = params.copy()
    if selected_type == "전체":
        donation_where.append("msg_type = %s")
        donation_params.append("DONATION")
    donation_where_sql = "WHERE " + " AND ".join(donation_where) if donation_where else ""

    query_top = f"""
        SELECT nickname, count(*) as cnt, COALESCE(sum(pay_amount), 0) as total
        FROM chat_messages {donation_where_sql}
        GROUP BY nickname ORDER BY total DESC LIMIT 10
    """
    df_top = query_df(_conn, query_top, donation_params or None)

    if not df_top.empty and df_top["cnt"].sum() > 0:
        for i, row in df_top.iterrows():
            rank = i + 1
            cols = st.columns([0.5, 3, 2, 2])
            cols[0].markdown(f"**#{rank}**")
            cols[1].markdown(f"**{row['nickname'] or '-'}**")
            cols[2].markdown(f"`{int(row['cnt']):,}건`")
            cols[3].markdown(f"**{int(row['total']):,}원**")
    else:
        st.info("도네이션 데이터가 없습니다.")

    _conn.close()


render_stats()

conn.close()
