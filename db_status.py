"""DB 적재 현황 조회"""
import argparse
import sys

from modules.postgresql import get_connection

sys.stdout.reconfigure(encoding="utf-8")


def show_status(limit: int = 20):
    conn = get_connection()
    cur = conn.cursor()

    # 요약
    cur.execute("SELECT count(*) FROM chat_messages")
    chat_total = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM streaming_events")
    streaming_total = cur.fetchone()[0]

    print(f"{'='*60}")
    print(f" chat_messages: {chat_total}건 | streaming_events: {streaming_total}건")
    print(f"{'='*60}")

    # 스트리머별 통계
    cur.execute("""
        SELECT streamer, msg_type, count(*)
        FROM chat_messages
        GROUP BY streamer, msg_type
        ORDER BY streamer, count(*) DESC
    """)
    rows = cur.fetchall()
    if rows:
        print("\n [스트리머별 유형]")
        for streamer, msg_type, cnt in rows:
            print(f"   {streamer:>15s} | {msg_type:<15s} | {cnt}건")

    # 최근 메시지
    cur.execute(f"""
        SELECT ts, msg_type, nickname, message, pay_amount
        FROM chat_messages
        ORDER BY ts DESC
        LIMIT {limit}
    """)
    rows = cur.fetchall()
    if rows:
        print(f"\n [최근 {limit}건]")
        print(f"   {'시간':>19s} | {'유형':<12s} | {'닉네임':<16s} | 메시지")
        print(f"   {'-'*19}-+-{'-'*12}-+-{'-'*16}-+-{'-'*20}")
        for ts, msg_type, nickname, message, pay_amount in reversed(rows):
            time_str = ts.strftime("%m-%d %H:%M:%S")
            nick = (nickname or "-")[:16]
            msg = (message or "")[:40]
            if msg_type == "DONATION":
                msg = f"[{pay_amount}원] {msg}"
            print(f"   {time_str:>19s} | {msg_type:<12s} | {nick:<16s} | {msg}")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, default=20, help="최근 메시지 수 (기본 20)")
    args = parser.parse_args()
    show_status(args.n)
