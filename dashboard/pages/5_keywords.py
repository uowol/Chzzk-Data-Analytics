"""키워드 분석"""

import base64
import html
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from modules.postgresql import get_connection
from dashboard.style import apply_style, metric_card, section_title

EMOJI_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "emojis"
EMOJI_TAG_RE = re.compile(r"\[emoji:([a-zA-Z0-9_]+):([^\]]+)\]")

_b64_cache: dict[str, str] = {}


def _emoji_to_b64(filename: str) -> str | None:
    if filename in _b64_cache:
        return _b64_cache[filename]
    path = EMOJI_DIR / filename
    if not path.exists():
        return None
    data = base64.b64encode(path.read_bytes()).decode()
    ext = filename.rsplit(".", 1)[-1]
    mime = "image/png" if ext == "png" else f"image/{ext}"
    result = f"data:{mime};base64,{data}"
    _b64_cache[filename] = result
    return result


def render_message(text: str) -> str:
    if not text:
        return ""
    escaped = html.escape(text)

    def _replace(m):
        filename = m.group(2)
        b64 = _emoji_to_b64(filename)
        if b64:
            return (f'<img src="{b64}" alt="{m.group(1)}" '
                    'style="height:1.5em; vertical-align:middle; margin:0 2px;">')
        return f"[{m.group(1)}]"

    return EMOJI_TAG_RE.sub(_replace, escaped)


def query_df(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return pd.DataFrame()
        cols = [desc[0] for desc in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def _get_setting(conn, key: str) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT value FROM keyword_settings WHERE key = %s", (key,))
        row = cur.fetchone()
        return row[0] if row else ""


def _set_setting(conn, key: str, value: str):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO keyword_settings (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (key, value),
        )
    conn.commit()


st.set_page_config(page_title="키워드 분석", page_icon="🔤", layout="wide")
apply_style()

st.markdown("""
<h1 style="font-weight: 800; margin-bottom: 0.2rem;">🔤 키워드 분석</h1>
<p style="color: #6b7280; margin-bottom: 1.5rem;">채팅 키워드 빈도 분석 (배치 집계)</p>
""", unsafe_allow_html=True)


# --- 분석 설정 ---
section_title("분석 설정")

settings_conn = get_connection()

current_threshold = int(_get_setting(settings_conn, "chat_threshold") or "500")

new_threshold = st.number_input(
    "분석 트리거 임계값 (채팅 수)",
    min_value=50,
    max_value=100000,
    value=current_threshold,
    step=50,
    help="미분석 채팅이 이 수 이상 쌓이면 자동으로 키워드 분석을 실행합니다.",
)
if new_threshold != current_threshold:
    _set_setting(settings_conn, "chat_threshold", str(new_threshold))
    st.success(f"임계값이 {new_threshold}으로 변경되었습니다.")

settings_conn.close()


@st.fragment(run_every=5)
def render_pending():
    _conn = get_connection()
    last_at = _get_setting(_conn, "last_analyzed_at") or "1970-01-01T00:00:00"
    threshold_val = int(_get_setting(_conn, "chat_threshold") or "500")

    with _conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM chat_messages "
            "WHERE created_at > %s::timestamp AND msg_type IN ('CHAT', 'DONATION')",
            (last_at,),
        )
        pending_count = cur.fetchone()[0]
    _conn.close()

    progress = min(pending_count / threshold_val, 1.0) if threshold_val > 0 else 0
    st.markdown(f"**미분석 채팅**: {pending_count:,}건 / 임계값 {threshold_val:,}건")
    st.progress(progress)
    if pending_count >= threshold_val:
        st.success("임계값 도달 — 다음 폴링 시 분석이 실행됩니다.")
    else:
        remaining = threshold_val - pending_count
        st.info(f"분석까지 {remaining:,}건 남음")


render_pending()


# --- 필터 ---
section_title("필터")

conn = get_connection()

with conn.cursor() as cur:
    cur.execute("SELECT DISTINCT streamer FROM keyword_counts ORDER BY streamer")
    streamer_list = [row[0] for row in cur.fetchall()]

col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    selected_streamer = st.selectbox("스트리머", options=["전체"] + streamer_list, index=0)

with col_f2:
    pos_options = {"전체": None, "명사 (NNG)": "NNG", "고유명사 (NNP)": "NNP",
                   "동사 (VV)": "VV", "형용사 (VA)": "VA", "바이그램": "BIGRAM"}
    selected_pos_label = st.selectbox("품사", options=list(pos_options.keys()), index=0)
    selected_pos = pos_options[selected_pos_label]

with col_f3:
    time_range = st.selectbox("시간 범위", options=["최근 1시간", "최근 6시간", "최근 24시간", "전체"], index=0)
    time_interval_map = {"최근 1시간": "1 hour", "최근 6시간": "6 hours", "최근 24시간": "24 hours", "전체": None}
    time_interval = time_interval_map[time_range]

# keyword_counts 필터
where_clauses = []
params = []

if selected_streamer != "전체":
    where_clauses.append("streamer = %s")
    params.append(selected_streamer)
if selected_pos:
    where_clauses.append("pos = %s")
    params.append(selected_pos)
if time_interval:
    where_clauses.append("window_start >= NOW() - INTERVAL %s")
    params.append(time_interval)

where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

# chat_messages 필터
chat_where_clauses = ["msg_type IN ('CHAT', 'DONATION')"]
chat_params = []

if selected_streamer != "전체":
    chat_where_clauses.append("streamer = %s")
    chat_params.append(selected_streamer)
if time_interval:
    chat_where_clauses.append("ts >= NOW() - INTERVAL %s")
    chat_params.append(time_interval)

chat_where_sql = "WHERE " + " AND ".join(chat_where_clauses)


# --- 실시간 갱신 영역 ---
@st.fragment(run_every=5)
def render_keywords():
    _conn = get_connection()

    # 요약 메트릭
    summary = query_df(_conn, f"""
        SELECT
            COUNT(DISTINCT keyword) as unique_keywords,
            COALESCE(SUM(count), 0) as total_count,
            COUNT(DISTINCT window_start) as window_count
        FROM keyword_counts {where_sql}
    """, params or None)

    if not summary.empty:
        row = summary.iloc[0]
        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card("고유 키워드", f"{int(row['unique_keywords']):,}개")
        with c2:
            metric_card("총 출현 횟수", f"{int(row['total_count']):,}회", "green")
        with c3:
            metric_card("집계 윈도우", f"{int(row['window_count']):,}개", "orange")

    st.markdown("<br>", unsafe_allow_html=True)

    # TOP 20 키워드
    section_title("인기 키워드 TOP 20")

    df_top = query_df(_conn, f"""
        SELECT keyword, pos, SUM(count) as total
        FROM keyword_counts {where_sql}
        GROUP BY keyword, pos
        ORDER BY total DESC
        LIMIT 20
    """, params or None)

    if not df_top.empty:
        tab1, tab2 = st.tabs(["차트", "테이블"])
        with tab1:
            chart_df = df_top.set_index("keyword")
            st.bar_chart(chart_df["total"])
        with tab2:
            pos_labels = {"NNG": "일반명사", "NNP": "고유명사", "VV": "동사",
                          "VA": "형용사", "BIGRAM": "바이그램"}
            display_df = df_top.copy()
            display_df["pos"] = display_df["pos"].map(lambda x: pos_labels.get(x, x))
            display_df.columns = ["키워드", "품사", "출현 횟수"]
            st.dataframe(display_df, width="stretch", hide_index=True)
    else:
        st.info("키워드 데이터가 없습니다.")

    # 키워드가 포함된 원본 채팅 (문장 단위)
    section_title("최근 채팅 (키워드 포함)")

    keyword_search = st.text_input(
        "키워드 검색",
        placeholder="특정 키워드로 채팅 필터링 (비우면 최신 채팅 표시)",
    )

    search_clauses = list(chat_where_clauses)
    search_params = list(chat_params)
    if keyword_search:
        search_clauses.append("message ILIKE %s")
        search_params.append(f"%{keyword_search}%")
    search_where = "WHERE " + " AND ".join(search_clauses)

    df_messages = query_df(_conn, f"""
        SELECT ts, streamer, nickname, message, msg_type
        FROM chat_messages {search_where}
        ORDER BY ts DESC
        LIMIT 50
    """, search_params or None)

    if not df_messages.empty:
        chat_html_parts = []
        for _, row in df_messages.iterrows():
            ts_str = row["ts"].strftime("%H:%M:%S")
            nickname = html.escape(str(row["nickname"] or ""))
            msg_html = render_message(row["message"] or "")
            type_badge = ""
            if row["msg_type"] == "DONATION":
                type_badge = '<span style="background:#f5576c; color:white; padding:1px 6px; border-radius:8px; font-size:0.75rem; margin-right:4px;">후원</span>'

            chat_html_parts.append(
                f'<div style="padding:6px 0; border-bottom:1px solid #f3f4f6;">'
                f'<span style="color:#9ca3af; font-size:0.8rem; margin-right:8px;">{ts_str}</span>'
                f'{type_badge}'
                f'<span style="font-weight:600; margin-right:6px;">{nickname}</span>'
                f'<span>{msg_html}</span>'
                f'</div>'
            )

        st.markdown(
            '<div style="max-height:400px; overflow-y:auto; border:1px solid #e5e7eb; border-radius:8px; padding:8px 12px;">'
            + "".join(chat_html_parts)
            + '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("해당 조건의 채팅 데이터가 없습니다.")

    # 키워드 트렌드 (시간별 추이)
    section_title("키워드 트렌드")

    df_trend = query_df(_conn, f"""
        SELECT window_start, keyword, SUM(count) as total
        FROM keyword_counts {where_sql}
        GROUP BY window_start, keyword
        ORDER BY window_start
    """, params or None)

    if not df_trend.empty:
        top5 = df_trend.groupby("keyword")["total"].sum().nlargest(5).index.tolist()
        df_trend_top = df_trend[df_trend["keyword"].isin(top5)]
        pivot_trend = df_trend_top.pivot_table(
            index="window_start", columns="keyword", values="total", fill_value=0, aggfunc="sum"
        )
        st.line_chart(pivot_trend)
    else:
        st.info("트렌드 데이터가 없습니다.")

    # 품사별 비율
    section_title("품사별 분포")

    df_pos = query_df(_conn, f"""
        SELECT pos, SUM(count) as total
        FROM keyword_counts {where_sql}
        GROUP BY pos
        ORDER BY total DESC
    """, params or None)

    if not df_pos.empty:
        pos_labels = {"NNG": "일반명사", "NNP": "고유명사", "VV": "동사",
                      "VA": "형용사", "BIGRAM": "바이그램"}
        df_pos["품사명"] = df_pos["pos"].map(lambda x: pos_labels.get(x, x))
        chart_df = df_pos.set_index("품사명")
        st.bar_chart(chart_df["total"])
    else:
        st.info("품사 데이터가 없습니다.")

    # 스트리머별 키워드 비교
    if selected_streamer == "전체" and len(streamer_list) > 1:
        section_title("스트리머별 인기 키워드")

        time_where = []
        time_params = []
        if time_interval:
            time_where.append("window_start >= NOW() - INTERVAL %s")
            time_params.append(time_interval)
        if selected_pos:
            time_where.append("pos = %s")
            time_params.append(selected_pos)
        tw_sql = "WHERE " + " AND ".join(time_where) if time_where else ""

        df_by_streamer = query_df(_conn, f"""
            SELECT streamer, keyword, SUM(count) as total
            FROM keyword_counts {tw_sql}
            GROUP BY streamer, keyword
            ORDER BY streamer, total DESC
        """, time_params or None)

        if not df_by_streamer.empty:
            top_per_streamer = df_by_streamer.groupby("streamer").head(10)
            pivot_streamer = top_per_streamer.pivot_table(
                index="keyword", columns="streamer", values="total", fill_value=0, aggfunc="sum"
            )
            st.dataframe(pivot_streamer, width="stretch")

    _conn.close()


render_keywords()

conn.close()
