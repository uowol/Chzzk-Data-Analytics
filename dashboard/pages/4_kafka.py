"""Kafka 모니터링 - 브로커, 토픽, 컨슈머 그룹 상태"""

import json
import sys
from pathlib import Path

import psutil
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from kafka import KafkaConsumer as _KafkaConsumer, TopicPartition
from kafka.admin import KafkaAdminClient

from modules.config import KAFKA_BOOTSTRAP_SERVERS
from modules.postgresql import get_connection
from dashboard.style import apply_style, badge, metric_card, render_sidebar, section_title

st.set_page_config(page_title="Kafka 모니터링", page_icon="⚡", layout="wide")
apply_style()
render_sidebar()

st.markdown("""
<h1 style="font-weight: 800; margin-bottom: 0.2rem;">⚡ Kafka 모니터링</h1>
<p style="color: #6b7280; margin-bottom: 1.5rem;">브로커, 토픽, 컨슈머 그룹 상태</p>
""", unsafe_allow_html=True)

# --- 브로커 연결 ---
try:
    admin = KafkaAdminClient(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        client_id="dashboard-monitor",
    )
    broker_connected = True
except Exception as e:
    broker_connected = False
    broker_error = str(e)

# --- 브로커 상태 ---
section_title("브로커")

with st.expander("브로커란?"):
    st.markdown("""
**Kafka 브로커**는 메시지를 저장하고 전달하는 Kafka 서버입니다.

- **Producer**(크롤러)가 수집한 채팅 데이터를 브로커의 **토픽**에 발행합니다.
- **Consumer**가 토픽에서 메시지를 꺼내 PostgreSQL에 저장합니다.
- 브로커는 메시지를 디스크에 보관하므로, Consumer가 잠시 꺼져도 데이터가 유실되지 않습니다.
- 현재 구조: `WebSocket 크롤러 → Kafka Broker → PostgreSQL`

```
Producer ──→ Broker(chat 토픽) ──→ Consumer ──→ DB
         ──→ Broker(streaming 토픽) ──→ Consumer ──→ DB
```
""")

if broker_connected:
    cluster = admin._client.cluster
    brokers = cluster.brokers()

    col1, col2 = st.columns(2)
    with col1:
        metric_card("브로커 수", str(len(brokers)), "green")
    with col2:
        metric_card("Bootstrap", KAFKA_BOOTSTRAP_SERVERS)

    if brokers:
        for broker in brokers:
            st.markdown(
                f"- **Broker {broker.nodeId}** — `{broker.host}:{broker.port}`"
            )
else:
    st.error(f"Kafka 브로커 연결 실패: {broker_error}")
    st.stop()

# --- 토픽 ---
section_title("토픽")

try:
    topics_metadata = admin.describe_topics(["chat", "streaming"])
except Exception:
    topics_metadata = []

# 각 토픽의 파티션별 offset 조회
offset_consumer = _KafkaConsumer(
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    client_id="dashboard-offset-check",
)

for topic_meta in topics_metadata:
    topic_name = topic_meta["topic"]
    partitions = topic_meta.get("partitions", [])

    with st.container(border=True):
        cols = st.columns([2, 2, 2, 2])

        with cols[0]:
            st.markdown(f"**{topic_name}**")

        with cols[1]:
            st.markdown(f"파티션: **{len(partitions)}**")

        # 총 메시지 수 계산
        total_messages = 0
        partition_details = []
        for p in partitions:
            tp = TopicPartition(topic_name, p["partition"])
            offset_consumer.assign([tp])
            offset_consumer.seek_to_beginning(tp)
            start = offset_consumer.position(tp)
            offset_consumer.seek_to_end(tp)
            end = offset_consumer.position(tp)
            count = end - start
            total_messages += count
            partition_details.append({
                "partition": p["partition"],
                "leader": p["leader"],
                "start": start,
                "end": end,
                "messages": count,
            })

        with cols[2]:
            st.markdown(f"총 메시지: **{total_messages:,}**")

        with cols[3]:
            replicas = partitions[0].get("replicas", []) if partitions else []
            st.markdown(f"복제본: **{len(replicas)}**")

        # 파티션 상세
        with st.expander("파티션 상세"):
            for pd in partition_details:
                st.markdown(
                    f"  Partition **{pd['partition']}** — "
                    f"Leader: {pd['leader']}, "
                    f"Offset: {pd['start']} ~ {pd['end']}, "
                    f"Messages: **{pd['messages']:,}**"
                )

offset_consumer.close()

# --- 컨슈머 그룹 (5초마다 갱신) ---
section_title("컨슈머 그룹")


@st.fragment(run_every=5)
def render_consumer_groups():
    try:
        _admin = KafkaAdminClient(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            client_id="dashboard-cg-monitor",
        )
        groups = _admin.list_consumer_groups()
    except Exception:
        groups = []
        _admin = None

    if not groups:
        st.info("활성 컨슈머 그룹이 없습니다.")
    else:
        for group_name, group_type in groups:
            with st.container(border=True):
                st.markdown(f"**{group_name}** ({group_type})")

                try:
                    offsets = _admin.list_consumer_group_offsets(group_name)

                    if offsets:
                        lag_consumer = _KafkaConsumer(
                            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                            client_id="dashboard-lag-check",
                        )

                        cols_header = st.columns([2, 2, 2, 2])
                        cols_header[0].markdown("**토픽**")
                        cols_header[1].markdown("**현재 오프셋**")
                        cols_header[2].markdown("**최신 오프셋**")
                        cols_header[3].markdown("**Lag**")

                        total_lag = 0
                        for tp, offset_meta in offsets.items():
                            lag_consumer.assign([tp])
                            lag_consumer.seek_to_end(tp)
                            end_offset = lag_consumer.position(tp)
                            current = offset_meta.offset
                            lag = max(0, end_offset - current)
                            total_lag += lag

                            lag_badge = badge(f"{lag:,}", "live" if lag == 0 else "offline")

                            cols_row = st.columns([2, 2, 2, 2])
                            cols_row[0].markdown(f"`{tp.topic}[{tp.partition}]`")
                            cols_row[1].markdown(f"{current:,}")
                            cols_row[2].markdown(f"{end_offset:,}")
                            cols_row[3].markdown(lag_badge, unsafe_allow_html=True)

                        lag_consumer.close()

                        if total_lag == 0:
                            st.markdown(badge("모든 메시지 소비 완료", "live"), unsafe_allow_html=True)
                        else:
                            st.markdown(
                                badge(f"총 Lag: {total_lag:,}", "offline"),
                                unsafe_allow_html=True,
                            )
                except Exception as e:
                    st.warning(f"오프셋 조회 실패: {e}")

    if _admin:
        try:
            _admin.close()
        except Exception:
            pass


render_consumer_groups()

# --- 프로듀서 (크롤러) 상태 ---
section_title("프로듀서 (크롤러)")

conn = get_connection()

with conn.cursor() as cur:
    cur.execute("SELECT streamer_id, streamer_name, is_active FROM streamers ORDER BY created_at")
    streamers = cur.fetchall()

if not streamers:
    st.info("등록된 스트리머가 없습니다.")
else:
    cols_header = st.columns([3, 2, 3])
    cols_header[0].markdown("**스트리머**")
    cols_header[1].markdown("**상태**")
    cols_header[2].markdown("**토픽**")

    for streamer_id, streamer_name, is_active in streamers:
        status_badge = badge("producing", "live") if is_active else badge("stopped", "offline")

        cols_row = st.columns([3, 2, 3])
        cols_row[0].markdown(f"**{streamer_name}**")
        cols_row[1].markdown(status_badge, unsafe_allow_html=True)
        cols_row[2].markdown("`chat`, `streaming`" if is_active else "-")

conn.close()

@st.fragment(run_every=5)
def render_resources():
    section_title("시스템 리소스")

    mem = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=0.5)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        mem_variant = "green" if mem.percent < 70 else ("orange" if mem.percent < 90 else "default")
        metric_card("메모리 사용률", f"{mem.percent}%", mem_variant)
    with col2:
        metric_card("메모리 사용", f"{mem.used / (1024**3):.1f} / {mem.total / (1024**3):.1f} GB")
    with col3:
        cpu_variant = "green" if cpu_percent < 70 else ("orange" if cpu_percent < 90 else "default")
        metric_card("CPU 사용률", f"{cpu_percent}%", cpu_variant)
    with col4:
        metric_card("가용 메모리", f"{mem.available / (1024**3):.1f} GB", "green")

    st.markdown("<br>", unsafe_allow_html=True)

    # 프로세스별 리소스
    section_title("프로세스별 리소스")

    pid_file = Path(__file__).resolve().parent.parent / ".crawler_pids.json"
    crawler_pids = {}
    if pid_file.exists():
        try:
            crawler_pids = json.loads(pid_file.read_text())
        except (json.JSONDecodeError, ValueError):
            pass

    process_rows = []

    for s_id, pid in crawler_pids.items():
        try:
            proc = psutil.Process(pid)
            children = proc.children(recursive=True)
            all_procs = [proc] + children

            total_rss = sum(p.memory_info().rss for p in all_procs)
            total_cpu = sum(p.cpu_percent(interval=0) for p in all_procs)
            name = next(
                (s_name for sid, s_name in streamers if sid == s_id),
                s_id[:8],
            )
            process_rows.append({
                "name": name,
                "pid": pid,
                "procs": len(all_procs),
                "rss": total_rss,
                "cpu": total_cpu,
                "status": proc.status(),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    for proc in psutil.process_iter(["pid", "name", "cmdline", "memory_info", "cpu_percent"]):
        try:
            pname = proc.info["name"].lower()
            cmdline = " ".join(proc.info["cmdline"] or []).lower()

            label = None
            if "java" in pname and "kafka" in cmdline:
                label = "Kafka Broker"
            elif "postgres" in pname:
                label = "PostgreSQL"
            elif "streamlit" in cmdline:
                label = "Streamlit Dashboard"

            if label:
                rss = proc.info["memory_info"].rss if proc.info["memory_info"] else 0
                process_rows.append({
                    "name": label,
                    "pid": proc.info["pid"],
                    "procs": 1,
                    "rss": rss,
                    "cpu": proc.info["cpu_percent"] or 0,
                    "status": proc.status(),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if process_rows:
        process_rows.sort(key=lambda x: x["rss"], reverse=True)

        cols_header = st.columns([3, 1, 1, 2, 1, 1, 1])
        cols_header[0].markdown("**프로세스**")
        cols_header[1].markdown("**PID**")
        cols_header[2].markdown("**하위**")
        cols_header[3].markdown("**메모리**")
        cols_header[4].markdown("**CPU**")
        cols_header[5].markdown("**상태**")
        cols_header[6].markdown("")

        for row in process_rows:
            rss_mb = row["rss"] / (1024 ** 2)
            mem_text = f"{rss_mb:.0f} MB" if rss_mb < 1024 else f"{rss_mb / 1024:.1f} GB"

            if rss_mb > 500:
                mem_badge_html = badge(mem_text, "offline")
            elif rss_mb > 200:
                mem_badge_html = badge(mem_text, "crawler-on")
            else:
                mem_badge_html = badge(mem_text, "live")

            cols_row = st.columns([3, 1, 1, 2, 1, 1, 1])
            cols_row[0].markdown(f"**{row['name']}**")
            cols_row[1].markdown(f"`{row['pid']}`")
            cols_row[2].markdown(f"{row['procs']}")
            cols_row[3].markdown(mem_badge_html, unsafe_allow_html=True)
            cols_row[4].markdown(f"{row['cpu']:.1f}%")
            cols_row[5].markdown(f"`{row['status']}`")
            with cols_row[6]:
                if st.button("Kill", key=f"kill_{row['pid']}"):
                    try:
                        p = psutil.Process(row["pid"])
                        p.kill()
                        st.toast(f"PID {row['pid']} 종료됨")
                        st.rerun()
                    except psutil.NoSuchProcess:
                        st.toast("이미 종료된 프로세스")
                        st.rerun()
                    except psutil.AccessDenied:
                        st.error("권한 부족")
    else:
        st.info("모니터링 대상 프로세스가 없습니다.")


render_resources()

try:
    admin.close()
except Exception:
    pass
