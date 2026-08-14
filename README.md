# ✈️ 국내 여행지 및 맛집 추천 프로그램 (Travel Planner CLI)

사용자가 입력한 여행 날짜(`--date "YYYY-MM-DD"`)를 기반으로 **Google Gemini API**와 **Kakao Local API**를 연동하여 국내 최적의 여행지를 추천하고, 현지 맛집 정보와 1일 일정 계획이 담긴 최종 여행 리포트를 자동 생성하는 Python CLI 애플리케이션입니다.

본 프로젝트는 **사전 평가 및 사전 검증 활동(Pre-Validation)**을 통해 식별된 LLM 파싱 및 API 연동 이슈를 완벽하게 개선하고 안정성을 확보한 완성형 버전입니다.

---

## 1. 프로그램 개요 (Overview)

현대 서비스 개발의 핵심인 **다중 외부 API 오케스트레이션(Orchestration)** 및 **LLM 출력 구조화(JSON Extraction)** 기술을 활용하여 제작되었습니다.

### 🔄 전체 처리 아키텍처 및 데이터 흐름
```
[사용자 날짜 입력]
       │ (argparse 입력 검증: YYYY-MM-DD)
       ▼
[1단계: Gemini LLM 1차 추천] ──> response_mime_type="application/json"
       │
       ▼
[Robust JSON 파서 & 도시명 정규화] ──> 마크다운 제거, { } 추출, 행정구역 정제
       │
       ▼ (정규화된 도시명 전달)
[2단계: Kakao Local API] ──> 맛집 5곳 검색 (이름, 주소, 카테고리, 좌표, URL)
       │
       ▼ (추천 데이터 + 맛집 데이터 종합)
[3단계: Gemini LLM 최종 리포트 생성] ──> Markdown 포맷 (1일 코스, 맛집, 축제, 오류 요약)
       │
       ▼
[results/ 디렉터리 저장] ──> YYYY-MM-DD_raw.json & YYYY-MM-DD_travel_plan.md
```

1. **날짜 입력 및 검증**: 사용자가 입력한 날짜의 유효성(`YYYY-MM-DD`)을 CLI 인자로 검증합니다.
2. **1차 AI 여행지 추천 (LLM)**: Gemini API에 JSON 출력을 강제하여 해당 시기 적합한 국내 도시, 날씨 요약, 축제/행사, 추천 이유를 구조화된 JSON으로 추출합니다.
3. **도시명 정규화 & 안전 파싱**: 정규식 기반 마크다운 정제 파서 및 행정구역 수식어 정규화를 거쳐 지도 검색 신뢰도를 확보합니다.
4. **맛집 정보 검색 (지도 API)**: 정규화된 추천 도시를 기반으로 Kakao Local 키워드 검색 API를 호출하여 대표 맛집 5곳의 상세 정보를 수집합니다.
5. **최종 여행 리포트 생성 (LLM)**: 추천 정보와 맛집 데이터를 종합하여 오전/오후/저녁 1일 코스를 포함한 완성형 Markdown 여행 리포트를 생성합니다.
6. **결과물 저장**: 원본 데이터 JSON과 최종 리포트 Markdown을 `results/` 디렉터리에 자동 저장합니다.

---

## 2. 사전 평가 및 검증 결과 반영 (Pre-Validation & Bug Fixes)

사전 평가 지침서(`gemini_code_assist_bugfix_guide.md`)에 따른 사전 검증 활동(Pre-Validation Checklist)을 100% 통과하였으며, 주요 개선 내역은 다음과 같습니다.

### 🧪 사전 평가 체크리스트 검증 결과표

| 검증 항목 | 검증 기준 | 개선 전 문제 | 사전 평가 및 개선 후 결과 | 판정 |
| :--- | :--- | :--- | :--- | :---: |
| **1. 터미널 경고 메시지** | 실행 시 `[경고] LLM JSON 파싱 실패` 로그 미발생 | 마크다운 혼입으로 파싱 실패 및 1회 재시도 경고 발생 | `safe_parse_json` 정규식 파서 적용으로 **경고 0건, 1회차 성공** | ✅ **통과** |
| **2. 결과 JSON 출력 검증** | `results/` JSON 내 `"reason"` 필드가 실제 LLM 추천 사유로 출력 | 파싱 에러로 하드코딩된 `"기본 추천 도시로 대체되었습니다."` 기록 | **실제 날짜별 맞춤 추천 사유 정상 기록** (통영/강릉/경주 등) | ✅ **통과** |
| **3. 날씨 정보 연동 검증** | `"weather"` 필드에 실제 기상 정보 반영 | `"날씨 정보 파싱 실패"`로 폴백 | **평균 기온, 계절성 및 상세 날씨 데이터 정상 반영** | ✅ **통과** |
| **4. 지도/장소 API 연동** | 추천 도시 기준 맛집 5곳 정상 검색 | 비정제 도시명 및 경로 문제로 인한 실패 가능성 | `normalize_city_name` 적용으로 **맛집 5곳 100% 정상 수집** | ✅ **통과** |
| **5. 최종 마크다운 리포트** | 1일 일정 및 필수 섹션 포함 마크다운 생성 | 모델 404/503 에러 시 리포트 생성 실패 | **다중 모델 자동 폴백으로 완성형 리포트 생성 완비** | ✅ **통과** |

### 🛠️ 핵심 코드 개선 사항
1. **JSON 응답 구조 강제**: `types.GenerateContentConfig(response_mime_type="application/json", temperature=0.7)` 적용
2. **다중 모델 무중단 자동 폴백(Failover)**: `gemini-3.7-flash` ➔ `gemini-3-flash-preview` ➔ `gemini-flash-latest` 순차 호출 지원
3. **Robust JSON 파서 (`safe_parse_json`)**: 마크다운 태그(````json ... ````) 정제 및 `{ ... }` 중괄호 영역 정밀 추출
4. **도시명 정규화 (`normalize_city_name`)**: 공백/특수문자 및 불필요한 행정구역 접미사("특별자치도", "특별시", "광역시", "도") 제거
5. **Windows 콘솔 UTF-8 한글 인코딩 지원**: 표준 출력 스트림 재구성을 통해 한글 깨짐 방지

---

## 3. 개발 환경 및 사전 준비 (Prerequisites)

* **언어 및 버전**: Python 3.10 이상
* **필수 패키지**:
  * `google-genai` (Google Gemini 공식 SDK)
  * `requests` (Kakao REST API HTTP 통신)
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

## 4. API 키 설정 방법 (API Key Configuration)

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

## 5. 프로그램 실행 방법 (Usage)

CLI(터미널)에서 `--date` 옵션과 함께 여행 희망 날짜를 `YYYY-MM-DD` 형식으로 전달하여 실행합니다.

### 🚀 기본 실행 명령어
```bash
python travel_planner.py --date "2026-08-14"
```

### 🖥️ 실행 화면 (CLI 출력 예시)
```text
[1/3] 1차 추천 생성 중(LLM)...
  - recommended_city: "통영"
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

## 6. 결과물 확인 방법 (Output Verification)

프로그램 실행이 완료되면 프로젝트 내 `results/` 폴더에 날짜를 파일명으로 하는 **2가지 결과물**이 자동 생성됩니다.

```
results/
├── YYYY-MM-DD_raw.json          # 1차 LLM 추천 + 맛집 검색 결과 + 오류 내역 원본 JSON
└── YYYY-MM-DD_travel_plan.md    # 완성된 1일 일정 및 맛집이 포함된 최종 Markdown 여행 리포트
```

### 📄 1) 원본 데이터 JSON (`results/2026-08-14_raw.json` 예시)
```json
{
  "date": "2026-08-14",
  "recommendation": {
    "recommended_city": "통영",
    "weather": "평균 기온 26~31도의 무더운 한여름 날씨이며, 낮에는 일조량이 풍부하고 밤에는 시원한 바닷바람이 붑니다.",
    "events": [
      "통영한산대첩축제",
      "디피랑 야간 미디어아트 페스티벌",
      "통영 해양레포츠 체험"
    ],
    "reason": "8월 중순은 통영의 대표 축제인 '통영한산대첩축제'가 열려 거리 퍼레이드와 수상 불꽃놀이 등 풍성한 볼거리를 즐길 수 있는 최고의 시기입니다..."
  },
  "places": [
    {
      "name": "울산다찌",
      "address": "경남 통영시 미수해안로 157",
      "category": "음식점 > 한식 > 해물,생선 > 회",
      "url": "http://place.map.kakao.com/25746655",
      "x": "128.4144839165626",
      "y": "34.8329679385357"
    }
  ],
  "errors": []
}
```

### 📑 2) 최종 여행 리포트 Markdown (`results/2026-08-14_travel_plan.md`)
* **포함 항목**:
  1. `## 📅 여행 개요` (날짜, 추천 지역, 날씨 요약)
  2. `## ✨ 추천 이유` (계절적 특성 및 매력 포인트)
  3. `## 🎡 주요 행사 및 축제` (지역 대표 축제 및 체험)
  4. `## 🗺️ 추천 1일 여행 코스` (오전 / 오후 / 저녁 타임라인 표)
  5. `## 🍽️ 맛집 추천` (검증된 로컬 맛집 5곳 상세 정보 및 링크)
  6. `## ⚠️ 발생한 오류` (정상 동작 시 '오류 없음' 표기)

---

## 7. 보안 및 안전 관리 (Security Notice)

> 🔒 **API 키 보안 원칙**:
> 1. **소스 코드 내 하드코딩 금지**: API 키는 절대 코드나 문서(Markdown, 로그 등)에 직접 작성하지 않습니다.
> 2. **`.gitignore` 적용**: `.env` 파일은 `.gitignore`에 등록되어 GitHub 등 공개 저장소에 커밋/푸시되지 않습니다.
> 3. **경로 독립성**: 프로젝트 루트 경로를 기준으로 `.env`를 탐색하므로 스크립트 실행 위치에 구애받지 않고 안전하게 환경변수를 로드합니다.

---

## 8. 예외 처리 및 안정성 정책 (Error Handling)

| 예외 상황 | 대응 정책 |
| :--- | :--- |
| **API 키 미설정** | 에러 메시지 출력 후 즉시 종료(`sys.exit(1)`), `.env` 설정 안내 |
| **LLM JSON 응답 형식 불일치** | 마크다운 제거 및 중괄호 정규식 추출 후 안전 파싱(`safe_parse_json`), 실패 시 1회 재요청 |
| **Gemini 모델 트래픽 / 장애** | `gemini-3.7-flash` -> `gemini-3-flash-preview` -> `gemini-flash-latest` 순 다중 모델 자동 장애 복구(Failover) |
| **지도 API 검색 실패 / 0건** | 프로그램 중단 없이 맛집 섹션에 "데이터 없음 (장소 검색 결과 0건)"으로 표기 후 리포트 정상 생성 |
| **지도 API 인증 실패(401/403)** | `errors` 배열에 에러 기록, 리포트 생성을 지속하여 안정적인 실행 흐름 보장 |

---

## 9. 과제 목표 및 학습 인사이트 (Key Insights)

* **REST API 요청/응답 구조**: HTTP GET(장소 검색)과 POST(LLM 생성) 메서드의 특성과 헤더 인증(Authorization) 방식을 체득.
* **데이터 파이프라인 연동**: LLM이 생성한 비정형 텍스트를 구조화된 JSON으로 변환하여 지도 API의 검색 키워드로 전달하는 파이프라인 구축.
* **오류 복구성(Resilience)**: API 호출 단계별 예외(인증/쿼터/네트워크/파싱)를 격리 처리하여 프로그램이 중단되지 않고 최종 리포트를 완성하도록 설계.
* **보안 관리**: `.env` 환경 변수 분리를 통해 협업 및 배포 환경에서의 API 키 유출을 원천 방지.
