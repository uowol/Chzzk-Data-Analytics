"""데이터베이스 조회, 수정, 삭제"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from modules.postgresql import get_connection
from modules.postgresql.schema import init_schema

from dashboard.style import apply_style, section_title


def query_df(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return pd.DataFrame()
        cols = [desc[0] for desc in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


st.set_page_config(page_title="데이터베이스", page_icon="🗄️", layout="wide")
apply_style()

st.markdown("""
<h1 style="font-weight: 800; margin-bottom: 0.2rem;">🗄️ 데이터베이스</h1>
<p style="color: #6b7280; margin-bottom: 1.5rem;">데이터 조회, 삭제, SQL 실행</p>
""", unsafe_allow_html=True)

conn = get_connection()
init_schema(conn)

# --- 테이블 선택 + 필터 ---
section_title("조회")

col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

with col1:
    table = st.selectbox("테이블", ["chat_messages", "streaming_events", "streamers"])

filter_clauses = []
filter_params = []
streamer_options = []

if table in ("chat_messages", "streaming_events"):
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT DISTINCT name FROM (
                SELECT streamer_name AS name FROM streamers
                UNION
                SELECT streamer FROM {table}
            ) t ORDER BY name
        """)
        streamer_options = [row[0] for row in cur.fetchall()]

    with col2:
        filter_streamer = st.selectbox("스트리머", ["전체"] + streamer_options, key="db_streamer")
        if filter_streamer != "전체":
            filter_clauses.append("streamer = %s")
            filter_params.append(filter_streamer)

    if table == "chat_messages":
        with col3:
            filter_type = st.selectbox(
                "유형",
                ["전체", "CHAT", "DONATION", "SUBSCRIPTION", "DELETED_CHAT"],
                key="db_type",
            )
            if filter_type != "전체":
                filter_clauses.append("msg_type = %s")
                filter_params.append(filter_type)

with col4:
    limit = st.number_input("조회 수", min_value=10, max_value=1000, value=100, step=10)

where_sql = "WHERE " + " AND ".join(filter_clauses) if filter_clauses else ""
order_by = "ORDER BY created_at DESC" if table == "streamers" else "ORDER BY ts DESC"

# --- 데이터 테이블 ---
df = query_df(conn, f"SELECT * FROM {table} {where_sql} {order_by} LIMIT %s", filter_params + [limit])

st.markdown(
    f'<p style="color:#6b7280; margin: 0.5rem 0;">총 <b>{len(df)}</b>건 조회됨</p>',
    unsafe_allow_html=True,
)

if df.empty:
    st.info("데이터가 없습니다.")
else:
    st.dataframe(df, width="stretch", hide_index=True, height=400)

# --- 삭제 ---
section_title("데이터 삭제")

tab_single, tab_batch = st.tabs(["개별 삭제", "일괄 삭제"])

with tab_single:
    col_id, col_del = st.columns([5, 1])
    with col_id:
        pk_label = "streamer_id" if table == "streamers" else "msg_id"
        msg_id_to_delete = st.text_input(
            f"삭제할 {pk_label}",
            placeholder=f"{pk_label}를 입력하세요",
            label_visibility="collapsed",
        )
    with col_del:
        if st.button("삭제", key="btn_del_single", use_container_width=True):
            if msg_id_to_delete:
                pk_col = "streamer_id" if table == "streamers" else "msg_id"
                with conn.cursor() as cur:
                    cur.execute(f"DELETE FROM {table} WHERE {pk_col} = %s", (msg_id_to_delete,))
                    deleted = cur.rowcount
                    conn.commit()
                if deleted:
                    st.success(f"{deleted}건 삭제됨")
                    st.rerun()
                else:
                    st.warning("해당 ID를 찾을 수 없습니다.")

with tab_batch:
    if table in ("chat_messages", "streaming_events"):
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            del_streamer = st.selectbox("스트리머", ["선택"] + streamer_options, key="del_batch_streamer")
        with col_d2:
            if table == "chat_messages":
                del_type = st.selectbox(
                    "유형",
                    ["전체", "CHAT", "DONATION", "SUBSCRIPTION", "DELETED_CHAT"],
                    key="del_batch_type",
                )
            else:
                del_type = "전체"

        if del_streamer != "선택":
            count_clauses = ["streamer = %s"]
            count_params = [del_streamer]
            if del_type != "전체":
                count_clauses.append("msg_type = %s")
                count_params.append(del_type)
            count_where = "WHERE " + " AND ".join(count_clauses)

            with conn.cursor() as cur:
                cur.execute(f"SELECT count(*) FROM {table} {count_where}", count_params)
                target_count = cur.fetchone()[0]

            st.markdown(
                f'<p style="color:#ef4444; font-weight:600;">삭제 대상: {target_count:,}건</p>',
                unsafe_allow_html=True,
            )
            if st.button(f"{target_count:,}건 삭제", key="btn_del_batch"):
                with conn.cursor() as cur:
                    cur.execute(f"DELETE FROM {table} {count_where}", count_params)
                    conn.commit()
                st.success(f"{target_count:,}건 삭제 완료")
                st.rerun()
    elif table == "streamers":
        st.info("스트리머는 **스트리머 관리** 페이지에서 삭제하세요.")

# --- SQL 직접 실행 ---
section_title("SQL 실행")

sql_input = st.text_area(
    "SQL",
    height=120,
    placeholder="SELECT * FROM chat_messages ORDER BY ts DESC LIMIT 10",
    label_visibility="collapsed",
)

col_sql1, col_sql2 = st.columns([1, 7])
with col_sql1:
    run_sql = st.button("실행", type="primary", use_container_width=True)

if run_sql and sql_input:
    try:
        sql_stripped = sql_input.strip().upper()
        if sql_stripped.startswith("SELECT") or sql_stripped.startswith("WITH"):
            result_df = query_df(conn, sql_input)
            st.dataframe(result_df, width="stretch", hide_index=True)
            st.caption(f"{len(result_df)}건 조회됨")
        else:
            with conn.cursor() as cur:
                cur.execute(sql_input)
                affected = cur.rowcount
                conn.commit()
            st.success(f"{affected}건 영향받음")
            st.rerun()
    except Exception as e:
        conn.rollback()
        st.error(f"SQL 오류: {e}")

conn.close()
