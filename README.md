# ✈️ 국내 여행지 및 맛집 추천 프로그램 (Travel Planner CLI)

사용자가 입력한 여행 날짜(`--date "YYYY-MM-DD"`)를 기반으로 **Google Gemini API**와 **Kakao Local API**를 연동하여 국내 최적의 여행지를 추천하고, 현지 맛집 정보와 1일 일정 계획이 담긴 최종 여행 리포트를 자동 생성하는 Python CLI 애플리케이션입니다.

---

## 1. 프로그램 개요 (Overview)

현대 서비스 개발에서 중요한 **다중 외부 API 오케스트레이션(Orchestration)** 및 **LLM 출력 구조화(JSON Extraction)** 기술을 활용하여 제작되었습니다.

### 🔄 전체 처리 흐름
```
[사용자 날짜 입력] ──> [Gemini API (JSON 응답)] ──> [Robust JSON 파싱 & 도시명 정규화]
                              │
                              ▼
                      [Kakao Local API] (맛집 5곳 검색)
                              │
                              ▼
                      [Gemini API 리포트 생성] (Markdown)
                              │
                              ▼
                      [results/ 폴더에 JSON & MD 파일 저장]
```

1. **날짜 입력 및 검증**: 사용자가 입력한 날짜의 유효성(`YYYY-MM-DD`)을 CLI 인자로 검증합니다.
2. **1차 AI 여행지 추천 (LLM)**: Gemini API(`response_mime_type="application/json"`)를 호출하여 해당 시기에 적합한 국내 도시, 날씨 요약, 축제/행사, 추천 이유를 구조화된 JSON으로 추출합니다.
3. **도시명 정규화 & 안전 파싱**: 정규식 기반 마크다운 정제 파서 및 행정구역 정규화를 거쳐 검색 신뢰도를 확보합니다.
4. **맛집 정보 검색 (지도 API)**: 정규화된 추천 도시를 기반으로 Kakao Local 키워드 검색 API를 호출하여 대표 맛집 5곳의 상세 정보(이름, 주소, 카테고리, URL, 좌표)를 수집합니다.
5. **최종 여행 리포트 생성 (LLM)**: 추천 정보와 맛집 데이터를 종합하여 오전/오후/저녁 1일 코스를 포함한 완성형 Markdown 여행 리포트를 생성합니다.
6. **결과물 저장**: 원본 데이터 JSON과 최종 리포트 Markdown을 `results/` 디렉터리에 자동 저장합니다.

---

## 2. 개발 환경 및 사전 준비 (Prerequisites)

* **언어 및 버전**: Python 3.10 이상
* **필수 라이브러리**:
  * `google-genai` (Google Gemini 공식 SDK)
  * `requests` (Kakao REST API HTTP 요청)
  * `python-dotenv` (환경 변수 및 `.env` 파일 관리)

### 📦 패키지 설치
```bash
pip install -r requirements.txt
```
또는
```bash
pip install google-genai requests python-dotenv
```

---

## 3. API 키 설정 방법 (API Key Configuration)

프로그램 실행을 위해 **Google Gemini API Key**와 **Kakao REST API Key**가 필요합니다.

### 🔑 1) API 키 발급
1. **Google Gemini API Key**: [Google AI Studio](https://aistudio.google.com/)에서 API 키 발급
2. **Kakao REST API Key**: [Kakao Developers 콘솔](https://developers.kakao.com/)에서 애플리케이션 생성 후 `REST API 키` 복사

### ⚙️ 2) `.env` 파일 생성 및 설정
프로젝트 루트 디렉터리에 `.env` 파일을 생성하고 아래 형식으로 키 값을 입력합니다:

```env
GEMINI_API_KEY=your_gemini_api_key_here
KAKAO_REST_API_KEY=your_kakao_rest_api_key_here
```

> 💡 **참고**: 저장소에 포함된 `.env.example` 파일을 복사하여 `.env`로 이름을 변경한 뒤 실제 키 값을 입력할 수 있습니다.
> ```bash
> cp .env.example .env
> ```

---

## 4. 프로그램 실행 방법 (Usage)

CLI(터미널)에서 `--date` 옵션과 함께 여행 희망 날짜를 `YYYY-MM-DD` 형식으로 전달하여 실행합니다.

### 🚀 기본 실행 명령어
```bash
python travel_planner.py --date "2026-08-14"
```

### 🖥️ 실행 화면 (CLI 출력 예시)
```text
[1/3] 1차 추천 생성 중(LLM)...
  - recommended_city: "강릉"
[2/3] 맛집 검색 중(지도/장소 API)...
  - 맛집 5곳 검색 완료
[3/3] 최종 리포트 생성 중(LLM)...
  - 리포트 생성 완료

완료! results/2026-08-14_travel_plan.md 및 results/2026-08-14_raw.json 를 확인하세요.
```

### ⚠️ 잘못된 날짜 입력 시 (예외 처리 예시)
```bash
python travel_planner.py --date "20260814"
```
**출력:**
```text
[ERROR] 올바르지 않은 날짜 형식입니다. 'YYYY-MM-DD' 형식으로 입력해주세요.
usage: travel_planner.py [-h] --date DATE

국내 여행지 및 맛집 추천 프로그램

options:
  -h, --help   show this help message and exit
  --date DATE  여행 날짜 (YYYY-MM-DD)
```

---

## 5. 결과물 확인 방법 (Output Verification)

프로그램 실행이 완료되면 프로젝트 내 `results/` 폴더에 날짜를 파일명으로 하는 **2가지 결과물**이 자동 생성됩니다.

```
results/
├── YYYY-MM-DD_raw.json          # 1차 LLM 추천 + 맛집 검색 결과 + 오류 내역 원본 JSON
└── YYYY-MM-DD_travel_plan.md    # 완성된 1일 일정 및 맛집이 포함된 최종 Markdown 여행 리포트
```

### 📄 1) 원본 데이터 JSON (`results/2026-08-14_raw.json`)
```json
{
  "date": "2026-08-14",
  "recommendation": {
    "recommended_city": "강릉",
    "weather": "평균 기온 26~30℃ 내외의 무더운 한여름 날씨이며, 시원한 바닷바람과 함께 간헐적인 소나기가 내릴 수 있습니다.",
    "events": [
      "경포 썸머 페스티벌",
      "강릉 비치비어 페스티벌"
    ],
    "reason": "8월 중순은 동해안의 맑고 푸른 바다에서 해수욕과 다채로운 수상 레포츠를 즐기기에 가장 완벽한 시기입니다..."
  },
  "places": [
    {
      "name": "옹심이장칼국수 감자바우",
      "address": "강원특별자치도 강릉시 금성로35번길 4",
      "category": "음식점 > 한식 > 국수 > 칼국수",
      "url": "http://place.map.kakao.com/11395119",
      "x": "128.89707430758034",
      "y": "37.75310689521508"
    }
  ],
  "errors": []
}
```

### 📑 2) 최종 여행 리포트 Markdown (`results/2026-08-14_travel_plan.md`)
* **포함 항목**:
  1. 여행 개요 (날짜, 추천 지역, 날씨 요약)
  2. 추천 이유 (계절적 특성 및 매력 포인트)
  3. 주요 행사 및 축제 정보
  4. 추천 1일 여행 코스 (오전 / 오후 / 저녁 타임라인 표)
  5. 엄선 맛집 5곳 상세 정보 (주소, 카테고리, 특징)
  6. 발생 오류 요약 (정상 동작 시 '오류 없음' 표기)

---

## 6. 보안 및 안전 관리 (Security Notice)

> 🔒 **API 키 보안 원칙**:
> 1. **소스 코드 내 하드코딩 금지**: API 키는 절대 코드나 문서(Markdown, 로그 등)에 직접 작성하지 않습니다.
> 2. **`.gitignore` 적용**: `.env` 파일은 `.gitignore`에 등록되어 GitHub 등 공개 저장소에 커밋/푸시되지 않습니다.
> 3. **경로 독립성**: 프로젝트 루트 경로를 기준으로 `.env`를 탐색하므로 스크립트 실행 위치에 구애받지 않고 안전하게 환경변수를 로드합니다.

---

## 7. 예외 처리 및 안정성 정책 (Error Handling)

| 예외 상황 | 대응 정책 |
| :--- | :--- |
| **API 키 미설정** | 에러 메시지 출력 후 즉시 종료(`sys.exit(1)`), `.env` 설정 안내 |
| **LLM JSON 응답 형식 불일치** | 마크다운 제거 및 중괄호 정규식 추출 후 안전 파싱(`safe_parse_json`), 실패 시 1회 재요청 |
| **Gemini 모델 트래픽 / 장애** | `gemini-3.7-flash` -> `gemini-3-flash-preview` -> `gemini-flash-latest` 순 다중 모델 자동 장애 복구(Failover) |
| **지도 API 검색 실패 / 0건** | 프로그램 중단 없이 맛집 섹션에 "데이터 없음 (장소 검색 결과 0건)"으로 표기 후 리포트 정상 생성 |
| **지도 API 인증 실패(401/403)** | `errors` 배열에 에러 기록, 리포트 생성을 지속하여 안정적인 실행 흐름 보장 |
