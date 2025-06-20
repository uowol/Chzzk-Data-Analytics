# Chzzk-Data-Analytics
- 방송 채팅 및 후원 데이터를 수집하여 유의미한 분석을 진행합니다.
- 과거 데이터를 분석하는 Analysis를 넘어 예측 등의 Analytics를 목표로 합니다.
- 가능하면 LLM + RAG 모델을 붙여 자연어로 질문하면 분석 결과를 보여주는 데까지 개발해보고자 합니다.

### Reference
- https://github.com/Buddha7771/ChzzkChat?tab=readme-ov-file
- https://github.com/kimcore/chzzk/tree/main

## Inference

### 1. Run Postgres Server
```sh
docker run -d --name postgres-server -p 5432:5432 -e POSTGRES_USER=user -e POSTGRES_PASSWORD=pw -e POSTGRES_DB=chzzk postgres:14.0

apt install psql
POSTGRES_PASSWORD=pw psql -h localhost -p 5432 -U user -d chzzk
```

dev-container 환경을 사용할 경우 타 docker container로 띄워진 postgres server에 접근하려면, 같은 네트워크로 연결하고 `localhost` 대신 server 컨테이너의 `container-name`을 입력하면됩니다.

```sh
docker network create chzzk
docker network connect chzzk priceless_ellis(dev-container)
docker network connect chzzk postgres-server
POSTGRES_PASSWORD=pw psql -h postgres-server -p 5432 -U user -d chzzk
```


```sh
poetry run python run_pipeline.py --pipeline crawl_chat.yaml
```
- 파이프라인들은 `pipelines` 폴더 내에 정의되어 있습니다.