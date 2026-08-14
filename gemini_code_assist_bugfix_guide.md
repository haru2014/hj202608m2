# 🛠️ [Gemini Code Assist] travel_planner.py 버그 수정 및 개선 지침서

본 문서는 `travel_planner.py` 실행 시 발생하고 있는 **LLM JSON 파싱 실패 및 기본 추천 도시("제주") 대체 현상**을 해결하기 위한 VSCode Gemini Code Assist 전용 수정 지침서입니다.

---

## 1. 문제 현상 및 근본 원인 분석

### 📌 현상
* `python travel_planner.py --date "2026-08-14"` 실행 시 `[경고] LLM JSON 파싱 실패. 1회 재시도합니다...` 로그 발생.
* 생성된 JSON 파일(`results/2026-08-14_raw.json`) 내 결과가 아래와 같이 기본값으로 대체됨:
  ```json
  "recommendation": {
      "recommended_city": "제주",
      "weather": "날씨 정보 파싱 실패",
      "reason": "기본 추천 도시로 대체되었습니다."
  }
  ```

### 🔍 근본 원인 (Root Cause)
1. **LLM 응답 규격 불일치**: Gemini API가 결과를 반환할 때 마크다운 서식(```json ... ```)이나 불필요한 설명 문구를 포함하여 `json.loads()` 실행 시 `json.JSONDecodeError` 발생.
2. **Fallback(예외 처리) 동작**: 파싱 에러 발생에 따라 `except` 블록이 호출되어 하드코딩된 기본값("제주")으로 강제 전환됨.
3. **날씨 API 도시명 파싱 불일치**: 추천된 도시명 규격이 날씨 API 요구 형식과 달라 날씨 정보 가져오기 실패.

---

## ⚙️ 2. Gemini Code Assist 수정을 위한 프롬프트 / 코드 변경 지침

아래 지침에 따라 `travel_planner.py` 코드를 수정 및 리팩토링하세요.

### 1) Gemini API 설정 - JSON 응답 구조 강제 (`response_mime_type`)
Gemini API 호출 시 `GenerationConfig`에 `response_mime_type="application/json"`을 적용하여 마크다운이 없는 순수 JSON만 반환하도록 수정합니다.

```python
import google.generativeai as genai

# Gemini 모델 설정 시 JSON 응답 형태 강제 적용
generation_config = genai.GenerationConfig(
    response_mime_type="application/json",
    temperature=0.7
)

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",  # 프로젝트에 사용 중인 모델명
    generation_config=generation_config
)
```

### 2) Robust JSON 파서 함수 구현 (마크다운 정제 및 정규식 적용)
LLM 응답 텍스트에 포함될 수 있는 마크다운 태그(` ```json ` 등)를 완전히 정제한 후 파싱하는 헬퍼 함수를 추가/수정합니다.

```python
import json
import re

def safe_parse_json(raw_text: str) -> dict:
    if not raw_text:
        raise ValueError("LLM 응답이 비어있습니다.")

    # 마크다운 감싸기 제거
    cleaned = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*```', r'', raw_text).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 파싱 에러 발생: {e}")
        print(f"[DEBUG] Raw LLM Output:\n{raw_text}")
        raise e
```

### 3) 날씨 API 전처리 로직 강화
추천된 도시명(`recommended_city`)의 공백 및 행정구역 수식어(예: "제주" -> "제주특별자치도" 또는 "Jeju")를 날씨 API 규격에 맞춰 정제하는 전처리 함수를 추가합니다.

---

## 🧪 3. 사전 검증 활동 (Pre-Validation Checklist)

수정 완료 후 아래 검증을 수행하여 정상 동작을 확인하세요.

- [ ] **터미널 경고 메시지 확인**: `python travel_planner.py --date "2026-08-14"` 실행 시 `[경고] LLM JSON 파싱 실패` 로그가 발생하지 않아야 합니다.
- [ ] **결과 JSON 출력 검증**: `results/2026-08-14_raw.json` 파일 내 `"reason"` 값이 "기본 추천 도시로 대체되었습니다."가 아닌 **LLM이 생성한 실제 추천 사유**로 출력되는지 확인합니다.
- [ ] **날씨 정보 연동 검증**: `"weather"` 필드에 "날씨 정보 파싱 실패" 대신 정상적인 날씨 데이터가 반영되는지 확인합니다.
