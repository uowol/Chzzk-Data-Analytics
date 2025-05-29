# Chzzk-Data-Analytics
- 방송 채팅 및 후원 데이터를 수집하여 유의미한 분석을 진행합니다.
- 과거 데이터를 분석하는 Analysis를 넘어 예측 등의 Analytics를 목표로 합니다.
- 가능하면 LLM + RAG 모델을 붙여 자연어로 질문하면 분석 결과를 보여주는 데까지 개발해보고자 합니다.

### Reference
- https://github.com/Buddha7771/ChzzkChat?tab=readme-ov-file
- https://github.com/kimcore/chzzk/tree/main

### Inference

```sh
poetry run python run_pipeline.py --pipeline crawl_chat.yaml
```
- 파이프라인들은 `pipelines` 폴더 내에 정의되어 있습니다.