# Chzzk-Data-Analytics

Chzzk(치지직) 스트리밍 플랫폼의 채팅·후원 데이터를 실시간 수집하고 분석하는 데이터 파이프라인입니다.

- 방송 채팅, 도네이션, 구독 데이터를 실시간 수집
- 과거 데이터 분석(Analysis)을 넘어 예측 등의 Analytics를 목표
- LLM + RAG를 활용한 자연어 질의 기반 분석까지 확장 예정

## 프로젝트 구조

```
.
├── run_pipeline.py              # 메인 진입점 (streaming_check → producer + consumer 동시 실행)
├── db_status.py                 # DB 적재 현황 조회
├── pipelines/                   # 파이프라인 설정 파일 (YAML)
│   └── crawl_chat.yaml          # 채팅 수집 파이프라인 템플릿
├── components/                  # 파이프라인 구성 단위
│   ├── streaming_check.py       # 방송 상태 폴링 (시작 대기)
│   ├── producer.py              # WebSocket 채팅 크롤링 → Kafka 발행
│   └── consumer.py              # Kafka 메시지 소비 → PostgreSQL 적재
├── modules/                     # 핵심 모듈
│   ├── config.py                # .env 기반 환경 설정 로드
│   ├── chzzk/
│   │   ├── api.py               # Chzzk API 클라이언트 (방송 상태, 채널 정보, 토큰)
│   │   ├── chat.py              # WebSocket 채팅 핸들러 (연결, 수신, Kafka 발행)
│   │   ├── enums.py             # 채팅 명령/타입 enum
│   │   └── constants.py         # HTTP 헤더
│   ├── kafka/
│   │   ├── producer.py          # Kafka Producer 생성
│   │   └── consumer.py          # Kafka Consumer 생성
│   └── postgresql/
│       ├── __init__.py          # PostgreSQL 연결 헬퍼
│       └── schema.py            # 테이블 스키마 정의 (chat_messages, streaming_events)
├── docker/
│   └── docker-compose.yaml      # PostgreSQL + Zookeeper + Kafka + 앱
├── Dockerfile                   # 앱 이미지 (python:3.12-slim + uv)
├── .env                         # 환경 설정 (Kafka, PG 접속 정보, 쿠키)
├── .devcontainer/
│   └── devcontainer.json        # VS Code Dev Container 설정
└── pyproject.toml               # 프로젝트 설정 및 의존성 (uv)
```

## 데이터 흐름

```
StreamingCheck          Producer                    Consumer
(API 폴링,         →  (WebSocket 채팅 크롤링)  →  (Kafka 소비 → PostgreSQL 적재)
 방송 시작 대기)              │
                     ┌───────┴───────┐
                topic:chat      topic:streaming
                     │               │
                일반 채팅          카테고리 변경
                도네이션          방송 종료
                구독/삭제
```

`run_pipeline.py` 실행 시 Consumer가 백그라운드 스레드로 자동 실행되어 Kafka 메시지를 PostgreSQL에 실시간 적재합니다.

## 실행 방법

### 1. 의존성 설치

```bash
uv sync
```

### 2. 환경 설정

`.env.example`을 복사하여 `.env`를 생성하고, 네이버 로그인 쿠키를 입력합니다.

```bash
cp .env.example .env
```

```env
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chzzk
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
NID_SES=네이버_NID_SES_쿠키
NID_AUT=네이버_NID_AUT_쿠키
```

- `NID_SES`, `NID_AUT`: 네이버 로그인 후 브라우저 개발자 도구(F12) → Application → Cookies에서 복사

### 3. 인프라 실행

```bash
docker compose -f docker/docker-compose.yaml up -d
```

### 4. Kafka 토픽 생성

```bash
docker compose -f docker/docker-compose.yaml exec broker \
  kafka-topics --create --topic chat --bootstrap-server broker:29092 \
  --partitions 1 --replication-factor 1

docker compose -f docker/docker-compose.yaml exec broker \
  kafka-topics --create --topic streaming --bootstrap-server broker:29092 \
  --partitions 1 --replication-factor 1
```

### 5. 파이프라인 설정

`pipelines/crawl_chat.yaml`을 복사하여 스트리머 정보를 입력합니다. (`__`로 시작하는 파일은 `.gitignore`로 관리됩니다.)

```bash
cp pipelines/crawl_chat.yaml pipelines/__my_streamer.yaml
```

```yaml
streamer_id: "스트리머_채널_ID"
streamer_name: "스트리머_이름"
```

- `streamer_id`: 치지직 채널 URL에서 확인 (`chzzk.naver.com/live/{streamer_id}`)

### 6. 파이프라인 실행

```bash
uv run python run_pipeline.py --pipeline __my_streamer.yaml
```

방송 시작까지 폴링 → 채팅 수집(Producer) + DB 적재(Consumer) 동시 실행 → 방송 종료 시 자동 종료됩니다.

### 7. DB 현황 조회

```bash
uv run python db_status.py        # 최근 20건
uv run python db_status.py -n 50  # 최근 50건
```

## 개발 환경

```bash
uv sync                  # 의존성 설치 (dev 포함)
uv run ruff check .      # 린트 체크
```

VS Code Dev Container를 사용할 경우, "Reopen in Container"로 Docker 기반 개발 환경에 접속할 수 있습니다.

## Reference

- https://github.com/Buddha7771/ChzzkChat
- https://github.com/kimcore/chzzk
