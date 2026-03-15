"""키워드 배치 분석기.

chat_messages 테이블에서 미분석 메시지가 임계값 이상 쌓이면
키워드 분석을 실행하여 keyword_counts에 저장한다.

추적 기준: created_at (DB 삽입 시각) — msg_id는 해시이므로 순서 비교 불가.
"""

import time
from collections import defaultdict

from kiwipiepy import Kiwi
from psycopg2.extras import execute_values

from modules.postgresql import get_connection

POLL_INTERVAL = 10  # DB 폴링 주기 (초)

TARGET_POS = {"NNG", "NNP", "VV", "VA"}
TARGET_MSG_TYPES = ("CHAT", "DONATION")
MIN_KEYWORD_LEN = 2

UPSERT_KEYWORD_SQL = """
    INSERT INTO keyword_counts (window_start, streamer, keyword, pos, count)
    VALUES %s
    ON CONFLICT (window_start, streamer, keyword, pos)
    DO UPDATE SET count = keyword_counts.count + EXCLUDED.count
"""

kiwi = Kiwi()

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


def _count_unanalyzed(conn, last_at: str) -> int:
    """미분석 메시지 수를 반환한다."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM chat_messages "
            "WHERE created_at > %s::timestamp AND msg_type IN %s",
            (last_at, TARGET_MSG_TYPES),
        )
        return cur.fetchone()[0]


def _fetch_batch(conn, last_at: str) -> list[dict]:
    """미분석 메시지를 전부 가져온다 (created_at 순)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT created_at, ts, streamer, message FROM chat_messages "
            "WHERE created_at > %s::timestamp AND msg_type IN %s "
            "ORDER BY created_at",
            (last_at, TARGET_MSG_TYPES),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def extract_keywords(text: str) -> list[tuple[str, str]]:
    """텍스트에서 명사/동사/형용사를 추출한다."""
    tokens = kiwi.tokenize(text)
    return [
        (t.form, t.tag)
        for t in tokens
        if t.tag in TARGET_POS and len(t.form) >= MIN_KEYWORD_LEN
    ]


def extract_bigrams(text: str) -> list[tuple[str, str]]:
    """텍스트에서 명사 바이그램을 추출한다.

    연속된 명사 2개를 결합하여 복합 키워드로 만든다.
    예: "롤 챔피언" → ("롤 챔피언", "BIGRAM")
    """
    tokens = kiwi.tokenize(text)
    nouns = [
        t for t in tokens
        if t.tag in ("NNG", "NNP") and len(t.form) >= MIN_KEYWORD_LEN
    ]
    bigrams = []
    for i in range(len(nouns) - 1):
        # 원문에서 연속된 위치인지 확인 (사이 간격 3자 이하)
        if nouns[i + 1].start - nouns[i].end <= 3:
            combined = f"{nouns[i].form} {nouns[i + 1].form}"
            bigrams.append((combined, "BIGRAM"))
    return bigrams


def _analyze_batch(conn, messages: list[dict]):
    """메시지 배치를 분석하여 keyword_counts에 upsert한다."""
    counts: dict[tuple, int] = defaultdict(int)

    for msg in messages:
        text = msg["message"]
        if not text:
            continue

        streamer = msg["streamer"]
        # 1분 단위 윈도우
        window_start = msg["ts"].replace(second=0, microsecond=0)

        # 단일 키워드
        for keyword, pos in extract_keywords(text):
            counts[(window_start, streamer, keyword, pos)] += 1

        # 바이그램
        for bigram, pos in extract_bigrams(text):
            counts[(window_start, streamer, bigram, pos)] += 1

    if not counts:
        return

    values = [
        (window_start, streamer, keyword, pos, cnt)
        for (window_start, streamer, keyword, pos), cnt in counts.items()
    ]
    with conn.cursor() as cur:
        execute_values(cur, UPSERT_KEYWORD_SQL, values)
    conn.commit()

    print(f"  [KeywordAnalyzer] {len(messages)}건 분석 → {len(values)}개 키워드 집계 upsert")


def run():
    conn = get_connection()
    conn.autocommit = False

    print("[KeywordAnalyzer] 시작됨. 미분석 채팅 폴링 중...")

    while True:
        try:
            last_at = _get_setting(conn, "last_analyzed_at") or "1970-01-01T00:00:00"
            threshold = int(_get_setting(conn, "chat_threshold") or "500")

            pending = _count_unanalyzed(conn, last_at)

            if pending >= threshold:
                print(f"[KeywordAnalyzer] 미분석 {pending}건 >= 임계값 {threshold} → 분석 시작")

                messages = _fetch_batch(conn, last_at)
                if messages:
                    _analyze_batch(conn, messages)
                    new_last_at = messages[-1]["created_at"].isoformat()
                    _set_setting(conn, "last_analyzed_at", new_last_at)
                    print("[KeywordAnalyzer] 분석 완료. last_analyzed_at 갱신")

        except Exception as e:
            print(f"[KeywordAnalyzer] 오류: {e}")
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
            conn = get_connection()
            conn.autocommit = False

        time.sleep(POLL_INTERVAL)
