# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chzzk(치지직) 스트리밍 플랫폼의 채팅/도네이션 데이터를 실시간 수집·분석하는 Python 데이터 파이프라인.
WebSocket으로 라이브 채팅을 크롤링 → Kafka로 스트리밍 → PostgreSQL 저장 구조.

## Commands

```bash
# 의존성 설치
uv sync

# 데이터 수집 실행 (크롤러 + Consumer)
uv run python orchestrator.py

# 대시보드 실행 (별도 프로세스)
uv run streamlit run dashboard/app.py

# Docker 전체 실행 (인프라 + 앱 + 대시보드)
docker compose -f docker/docker-compose.yaml up -d

# Docker 재빌드 (코드 변경 시 analytics와 dashboard 모두 재빌드 필요)
docker compose -f docker/docker-compose.yaml up -d --build chzzk-analytics
docker compose -f docker/docker-compose.yaml up -d --build dashboard

# Kafka 토픽 생성 (최초 1회)
docker compose -f docker/docker-compose.yaml exec broker kafka-topics --create \
  --topic <topic-name> --bootstrap-server broker:29092 \
  --partitions 1 --replication-factor 1

# Lint
uv run ruff check .

# 테스트
uv run pytest
```

## Architecture

```
Orchestrator (DB is_active 폴링 → 크롤러 스레드 자동 시작/중지)
  ├── StreamingCheck (방송 대기)
  ├── Producer (WebSocket 크롤링 → Kafka)
  └── Consumer ×2 (chat/streaming 토픽 → PostgreSQL 배치 INSERT)

Dashboard (Streamlit, 별도 컨테이너/프로세스)
  └── PostgreSQL 직접 조회 + Kafka 상태 모니터링
```

### 핵심 모듈

- **`orchestrator.py`** — 메인 진입점. DB `streamers.is_active` 폴링 → 크롤러 스레드 관리. `run_pipeline.py`는 레거시(미사용)
- **`modules/chzzk/`** — Chzzk API 클라이언트(`api.py`), WebSocket 채팅 핸들러(`chat.py`), 이모지 관리(`emoji.py`), 채팅 명령 enum(`enums.py`)
- **`modules/kafka/`** — Kafka producer/consumer 래퍼. bootstrap 서버는 `.env`에서 관리
- **`modules/postgresql/`** — DB 연결 헬퍼 + 스키마 정의(`schema.py`)
- **`components/`** — 파이프라인 구성 단위. producer, consumer, streaming_check (각각 `run()` 함수)
- **`dashboard/`** — Streamlit 대시보드. 스트리머 관리, 통계, DB 조회, Kafka 모니터링

### 설정 구조

- `.env` — 환경별(Kafka/PG 접속) + 사용자별(NID_SES/NID_AUT 쿠키) 설정
- `streamers` 테이블 — 스트리머 등록/수집 제어 (`is_active` 플래그)

### Kafka 토픽

- `chat` — 일반 채팅, 도네이션, 구독, 삭제된 메시지
- `streaming` — 카테고리 변경, 방송 종료 이벤트

## Tech Stack

- Python 3.12+, uv
- Pydantic v2, websocket-client, kafka-python
- PostgreSQL 14.0, Kafka (Docker Compose)
- Streamlit (대시보드)
- psycopg2 (`execute_values` 배치 INSERT)
- requests (API 호출)
- ruff, pytest (dev dependency)

## Important Notes

- 이 프로젝트는 배포용 라이브러리가 아닌 **애플리케이션**이므로, `pyproject.toml`에 `[build-system]`을 정의하지 않고 `[tool.uv] package = false`를 사용한다. hatchling/setuptools 등의 build-backend를 지정하면 패키지 디렉토리를 찾지 못해 빌드가 실패한다.

## Known Issues & Lessons Learned

### Docker 배포 시 주의

- **chzzk-analytics와 dashboard는 별도 컨테이너**다. 코드 변경 시 양쪽 모두 재빌드해야 한다. `--build chzzk-analytics`만 하면 dashboard에는 반영되지 않음.
- 이모지 파일은 `emoji-data` named volume에 저장됨. 컨테이너 재시작 시 유실 방지.

### PostgreSQL 주의사항

- **`ALTER TABLE`은 `AccessExclusive` 락**을 건다. `init_schema()`에 ALTER TABLE을 넣으면 여러 프로세스(dashboard, orchestrator)가 동시 호출 시 데드락 발생. 스키마 변경은 CREATE TABLE에 반영하고, 런타임 ALTER TABLE은 피할 것.
- **psycopg2 암묵적 트랜잭션**: SELECT만 해도 트랜잭션이 열림. 폴링 루프처럼 오래 유지하는 커넥션은 `autocommit=True` 설정 필수.

### WebSocket (chat.py) 주의사항

- **`sock.recv()`가 `None`을 반환**할 수 있다. `json.loads()` 전에 반드시 None/빈문자열 체크 필요.
- **재연결 직후 API 호출 금지**: PONG 타이밍에 API를 호출하면 서버가 연결을 끊는다. `_last_streaming_check`을 `time.monotonic()`으로 초기화하여 재연결 후 30초간 API 호출을 지연해야 한다. `0.0`으로 초기화하면 즉시 호출 → 재연결 루프 발생.
- **이모지 경로는 파일명만 저장**: Docker와 로컬의 절대경로가 다르므로, `emoji_id.ext` 형태로 저장하고 런타임에 `EMOJI_DIR / filename`으로 조합.

### 데이터 무결성

- **msg_id는 `SHA256(cid:uid:msg:msgTime:idx)`로 결정적 생성**. UUID를 쓰면 재연결 시 같은 메시지에 다른 ID가 붙어 중복 저장됨.
- **ts에는 `msgTime`(치지직 서버 타임스탬프)을 사용**. `time.time()`(Kafka 발행 시점)이 아니라 채팅이 실제로 올라온 시점.
- Consumer의 `ON CONFLICT (msg_id) DO NOTHING`으로 DB 레벨 중복 방지.

### Consumer 성능

- **건별 `cur.execute()`는 느리다**. `psycopg2.extras.execute_values()`로 배치 INSERT해야 Lag이 쌓이지 않음.

## Conventions

- 커밋 메시지 접두사: `add:`, `refact:`, `fix:`, `chore:`, `docs:` 등 (소문자, 한국어 혼용)
- 로그 타임존: KST (Asia/Seoul)
- Chzzk API 인증: NID_SES, NID_AUT 쿠키 사용 (.env에서 관리)
