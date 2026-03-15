# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chzzk(치지직) 스트리밍 플랫폼의 채팅/도네이션 데이터를 실시간 수집·분석하는 Python 데이터 파이프라인.
WebSocket으로 라이브 채팅을 크롤링 → Kafka로 스트리밍 → PostgreSQL 저장 구조.

## Commands

```bash
# 의존성 설치
poetry install --no-root

# 파이프라인 실행 (pipelines/ 디렉토리의 YAML 파일 지정)
poetry run python run_pipeline.py --pipeline <pipeline_name>.yaml

# Docker 인프라 (PostgreSQL, Zookeeper, Kafka)
docker compose -f docker/docker-compose.yaml up -d

# Kafka 토픽 생성
docker compose -p chzzk exec broker kafka-topics --create \
  --topic <topic-name> --bootstrap-server broker:29092 \
  --partitions 1 --replication-factor 1
```

테스트 프레임워크는 아직 구성되지 않음.

## Architecture

```
StreamingCheckComponent ──→ ProducerComponent ──→ ConsumerComponents
(스트림 상태 폴링)       (WebSocket 채팅 크롤링    (Kafka 메시지 소비
                         + Kafka 토픽 발행)        + DB 저장)
```

### 핵심 모듈

- **`modules/chzzk/`** — Chzzk API 클라이언트(`api.py`), WebSocket 채팅 핸들러(`chat.py`), 채팅 명령 enum(`enums.py`)
- **`modules/kafka/`** — Kafka producer/consumer 래퍼. 브로커: `broker:29092`, JSON 직렬화
- **`modules/postgresql/`** — DB 연결 헬퍼 (기초 단계)
- **`classes/`** — Pydantic v2 데이터 모델. `RequestProducerMessage`, `RequestStreamingCheckMessage` 등
- **`components/`** — 파이프라인 구성 단위. producer, consumer_chat, consumer_streaming, streaming_check
- **`pipelines/`** — YAML 기반 파이프라인 설정 파일
- **`run_pipeline.py`** — 메인 진입점. YAML 로드 → Pydantic 검증 → 컴포넌트 순차 실행

### Kafka 토픽

- `chat` — 일반 채팅, 도네이션, 구독, 삭제된 메시지
- `streaming` — 카테고리 변경, 방송 종료 이벤트

### 메시지 포맷

Producer가 Kafka에 발행하는 JSON: `msg_id`, `ts`, `streamer_name`, `msg_type`, `payload`

## Tech Stack

- Python 3.12+, Poetry
- Pydantic v2, websocket-client, kafka-python
- PostgreSQL 14.0, Kafka (Docker Compose)
- selenium, requests (웹 스크래핑)
- pandas, numpy, duckdb, pyarrow (데이터 처리)

## Conventions

- 커밋 메시지 접두사: `add:`, `refact:`, `fix:` 등 (소문자, 한국어 혼용)
- 로그 타임존: KST (Asia/Seoul)
- Chzzk API 인증: NID_SES, NID_AUT 쿠키 사용 (`.env` 또는 YAML에서 관리)
