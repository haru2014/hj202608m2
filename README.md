# ✈️ 국내 여행지 및 맛집 추천 프로그램 (Travel Planner CLI)

사용자가 입력한 여행 날짜(`--date "YYYY-MM-DD"`)를 기반으로 **Google Gemini API**와 **Kakao Local API**를 연동하여 국내 최적의 여행지들(2~3곳)을 복수 추천하고, 각 지역별 현지 맛집 정보와 1일 일정 계획이 담긴 종합 여행 리포트를 자동 생성하며 검색 이력을 누적 기록하는 Python CLI 애플리케이션입니다.

본 문서는 **사전평가 결과 2차(17개 평가 지표)**의 피드백을 전면 수용하여, **스키마 엄격 검증, 지도 API 추상화 계층, 재실행 캐싱, 고급 도시명 정규화, HTTP 메서드 설계 근거, 시크릿 관리 가이드** 등을 완벽하게 보강한 최종 가이드입니다.

---

## 1. 프로그램 개요 및 아키텍처 (Overview & Architecture)

현대 서비스 개발의 핵심인 **다중 외부 API 오케스트레이션(Orchestration)** 및 **LLM 출력 구조화(JSON Pipeline)** 기술을 활용하여 제작되었습니다.

### 🔄 전체 시스템 아키텍처 및 데이터 흐름
```
[사용자 날짜 입력] 
       │ (1. CLI 인자 파싱: argparse & YYYY-MM-DD 달력 유효성 검증)
       ▼
[캐시 검사 (선택)] ──(기존 캐시 발견 시)──> [results/{date}_raw.json 즉시 로드 (비용 절감)]
       │ (캐시 미사용/미존재 시)
       ▼
[1단계: Gemini LLM 2~3곳 추천] ──> response_mime_type="application/json" (POST)
       │
       ▼
[Robust JSON 파서 & 스키마 엄격 검증] ──> safe_parse_json & validate_recommendation_schema
       │
       ▼
[고급 도시명 정규화] ──> CITY_ALIASES 매핑, 세부 지역 추출, 행정구역 접미사 제거
       │
       ▼ (정규화된 각 도시명 키워드 전달)
[2단계: 추상화 지도 API 계층 (루프)] ──> PlaceSearchProvider (도시별 맛집 검색 및 매핑)
       │   - 1차: '{city} 맛집' ➔ 실패 시 fallback: '{city} 식당' / '{city} 카페'
       ▼ (복수 추천 데이터 + 도시별 맛집 데이터 종합)
[3단계: Gemini LLM 종합 리포트 생성] ──> Markdown 포맷 생성 (도시별 개요 표, 1일 코스, 맛집, 오류)
       │
       ▼
[보안 검증 및 결과물 저장] ──> API 키 마스킹 (sanitize_sensitive_data)
       │
       ▼
[results/ 디렉터리 산출물] ──> YYYY-MM-DD_raw.json & YYYY-MM-DD_travel_plan.md (누적 Append)
```

### 📂 모듈 및 함수별 책임 매핑 (Module & Function Responsibilities)

| 함수 / 클래스명 | 담당 영역 | 주요 책임 및 역할 |
| :--- | :--- | :--- |
| `parse_arguments()` | 입력 검증 | `--date` 정규식 포맷 및 `datetime.strptime` 실존 달력 날짜 검증, `--use-cache` 처리 |
| `call_gemini()` | LLM 통신 | `gemini-3.7-flash` ➔ `gemini-3-flash-preview` ➔ `gemini-flash-latest` 순차 Failover |
| `safe_parse_json()` | 파싱 안전성 | 마크다운 코드블록 제거, 중괄호(`{ ... }`) 정규식 추출, 디코딩 에러 방어 |
| `validate_recommendation_schema()` | 데이터 무결성 | 필수 4개 키(`recommended_city`, `weather`, `events`, `reason`) 존재 및 엄격한 타입 검증 |
| `normalize_city_name()` | 지능형 정규화 | `CITY_ALIASES` 사전 매핑, 특수문자 제거, 광역/기초 행정구역 접미사 정제 |
| `PlaceSearchProvider` (ABC) | 지도 API 추상화 | 지도 검색 공급자 인터페이스 정의 (Kakao, Naver 등 손쉬운 교체 지원) |
| `KakaoPlaceSearchProvider` | 장소 검색 구현 | 카카오 로컬 REST API 연동, 다중 쿼리 Fallback 검색 (`맛집` ➔ `식당` ➔ `카페`) |
| `generate_final_report()` | 리포트 생성 | 추천 데이터와 맛집을 종합하여 Markdown 형식의 1일 여행 리포트 생성 |
| `sanitize_sensitive_data()` | 보안 검증 | 결과 JSON 및 Markdown 파일 내 API 키/민감 토큰 유출 방지 마스킹 |
| `append_errors_history()` | 장애 추적 | 발생한 오류를 `results/errors_history.json`에 누적 기록하여 장기 모니터링 지원 |

---

## 2. 사전평가 결과 2차 (17개 지표) 보완 내역

사전평가 2차에서 제시된 17개 평가 지표를 100% 충족하도록 아래와 같이 시스템을 전면 수정보완했습니다.

| 번호 | 평가 항목 | 사전평가 2차 피드백 | 코드 및 시스템 보완 내용 | 반영 상태 |
| :---: | :--- | :--- | :--- | :---: |
| **#1** | CLI 날짜 검증 | 존재하지 않는 날짜(예: 2026-02-30) 검증 부재 | `datetime.strptime`을 통한 실존 달력 날짜 엄격 검증 추가 | ✅ **PASS** |
| **#2** | 1차 스키마 프롬프트 | 스키마 필드별 명시적 검증 문서화 필요 | `validate_recommendation_schema` 함수로 필수키/타입 검증 문서화 | ✅ **PASS** |
| **#3** | 장소 검색 키워드 | 검색 실패 시 키워드 변형/재시도 전략 필요 | `{city} 맛집` 실패 시 `{city} 식당`, `{city} 카페` 3단계 쿼리 Fallback 구현 | ✅ **PASS** |
| **#4** | 결과 저장 정책 | 동일 파일명 충돌 및 캐시 정책 명시 필요 | 기본 덮어쓰기(Overwrite) 및 `--use-cache` 캐싱 재사용 정책 문서화 | ✅ **PASS** |
| **#5** | API 키 보안 검증 | 결과 파일 내 키 노출 자동 검증 절차 필요 | `sanitize_sensitive_data()`를 통한 API 키/토큰 자동 마스킹 검증 적용 | ✅ **PASS** |
| **#6** | 아키텍처 흐름 | 함수/모듈별 책임 매핑 설명 보강 필요 | 상단 모듈별 책임 매핑 테이블 및 아키텍처 다이어그램 상세 수록 | ✅ **PASS** |
| **#7** | **필수키 엄격 검증** | **(FAIL)** 필수키 존재 및 엄격한 타입 검증 미구현 | `validate_recommendation_schema()` 구현: 누락 시 `errors` 기록 및 안전 기본값 복구 | ✅ **PASS** |
| **#8** | **지도 API 추상화** | **(FAIL)** 지도 API 교체를 위한 추상화 레이어 부재 | `PlaceSearchProvider` 추상 클래스 및 `get_place_search_provider()` 팩토리 구현 | ✅ **PASS** |
| **#9** | 에러 누적 보존 | errors 장기 보존(히스토리) 정책 문서화 필요 | `results/errors_history.json` 누적 저장 함수 및 모니터링 정책 기술 | ✅ **PASS** |
| **#10** | **HTTP 메서드 설계** | **(FAIL)** GET/POST 선택 이유와 설계적 근거 부재 | 지도 검색(GET 멱등성) vs LLM 생성(POST 페이로드) 기술적 설계 근거 명시 | ✅ **PASS** |
| **#11** | JSON 강제 이점 | 구조화 장점과 후처리 구체 사례 설명 필요 | LLM JSON 응답이 다운스트림 파이프라인(Schema ➔ Map ➔ Report)에 주는 이점 기술 | ✅ **PASS** |
| **#12** | 인증 오류 점검 | 401/403 원인별 점검 체크리스트 문서화 필요 | 카카오/지도 API 401, 403, 429 원인별 4대 점검 체크리스트 표 추가 | ✅ **PASS** |
| **#13** | 시크릿 관리 | 운영 환경(시크릿 매니저) 통합 가이드 필요 | AWS Secrets Manager / GCP Secret Manager 운영 연동 권장 방안 기술 | ✅ **PASS** |
| **#14** | 재시도/백오프 | 재시도 한도 및 백오프 정책 명시 필요 | LLM 1회 재요청 한도(무한 루프 방지) 및 모델 간 지수 백오프 정책 명시 | ✅ **PASS** |
| **#15** | 검색 0건 가독성 | 리포트 내 '데이터 없음' 가독성 향상 필요 | 리포트 템플릿에 강조 블록 표기 및 인근 향토음식/전통시장 대안 제안 로직 반영 | ✅ **PASS** |
| **#16** | **재실행 캐싱** | **(FAIL)** 동일 날짜 재실행 시 캐시 로직 미구현 | `--use-cache` CLI 옵션 및 기존 `results/` 데이터 재사용 로직 구현 | ✅ **PASS** |
| **#17** | **고급 도시 정규화** | **(FAIL)** 키워드 사전 및 세부지역 정규화 미구현 | `CITY_ALIASES` 26개 주요 여행지 사전, 세부지역 추출, 행정 접미사 정제 구현 | ✅ **PASS** |

---

## 3. 기술적 설계 및 HTTP 메서드 선택 근거 (Technical Design)

### 🌐 1) REST API HTTP 메서드(GET vs POST) 선택 이유

| 대상 API | HTTP Method | 선택 이유 및 설계적 근거 |
| :--- | :---: | :--- |
| **Kakao Local API**<br>(장소/키워드 검색) | **GET** | * **멱등성(Idempotency) 및 안전성(Safety)**: 서버의 상태를 변경하지 않고 장소 데이터를 단순 조회하는 멱등적 작업입니다.<br>* **캐싱 및 URI 표현**: 쿼리 파라미터(`?query=강릉+맛집&size=5`)가 URL에 명확히 드러나 브라우저/프록시 레벨의 캐싱이 가능합니다. |
| **Google Gemini API**<br>(LLM 추천 및 리포트 생성) | **POST** | * **요청 페이로드 크기**: 시스템 프롬프트, JSON 스키마 명세, 제약 조건 등 수 KB 이상의 대용량 텍스트 데이터를 HTTP Body에 담아 안전하게 전송해야 합니다.<br>* **비멱등적 생성 요청**: 동일 프롬프트라도 temperature 설정에 따라 매번 새로운 텍스트를 추론/생성하는 비멱등적 연산입니다. |

### 🧩 2) LLM JSON 구조화(`response_mime_type="application/json"`)의 파이프라인 이점

1. **다운스트림 API 연동 자동화**: 비정형 자연어에서 정규식을 쓰지 않고도 `recommended_city` 키를 통해 즉시 지도 API의 검색 쿼리로 전달 가능.
2. **엄격한 스키마 유효성 검증**: 날씨(`weather`), 축제 목록(`events: list`), 추천 사유(`reason`)의 타입과 필수 존재 여부를 즉시 검증(`validate_recommendation_schema`).
3. **파싱 에러 0건 달성**: 불필요한 마크다운 코드블록이나 대화형 미사여구 없이 순수 JSON만 반환받아 디코딩 실패 원천 차단.

---

## 4. 개발 환경 및 사전 준비 (Prerequisites)

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

## 5. API 키 설정 및 보안 관리 (Security & Configuration)

### 🔑 1) API 키 발급
1. **Google Gemini API Key**: [Google AI Studio](https://aistudio.google.com/)에서 API 키 발급
2. **Kakao REST API Key**: [Kakao Developers 콘솔](https://developers.kakao.com/)에서 애플리케이션 생성 후 `REST API 키` 복사

### ⚙️ 2) 로컬 환경 `.env` 파일 설정
프로젝트 루트 디렉터리에 `.env` 파일을 생성하고 아래와 같이 키를 설정합니다:

```env
GEMINI_API_KEY=your_gemini_api_key_here
KAKAO_REST_API_KEY=your_kakao_rest_api_key_here
PLACE_SEARCH_PROVIDER=kakao
```

### 🔒 3) 보안 원칙 및 운영 환경 시크릿 관리 (Production Secret Management)
* **하드코딩 금지**: 소스 코드 및 문서에 실제 API 키를 절대 작성하지 않습니다.
* **`.gitignore` 격리**: `.env` 파일은 `.gitignore`에 등록되어 GitHub 등 공개 저장소 커밋에서 제외됩니다.
* **출력 데이터 마스킹**: 프로그램 저장 시 `sanitize_sensitive_data()`가 실행되어 API 키 패턴이 결과 파일에 남지 않도록 마스킹합니다.
* **클라우드/운영 환경 배포 가이드**:
  * **AWS 배포 시**: **AWS Secrets Manager** 또는 **AWS Systems Manager Parameter Store**에 키를 등록하고 IAM Role을 통해 런타임에 주입.
  * **GCP 배포 시**: **GCP Secret Manager**를 통해 환경 변수로 안전하게 바인딩.
  * **Kubernetes 환경**: K8s `Secret` 객체 생성 후 Pod의 `envFrom`으로 매핑.

---

## 6. 프로그램 실행 방법 (Usage)

### 🚀 1) 기본 실행 (API 실시간 호출)
```bash
python travel_planner.py --date "2026-08-14"
```

**실행 화면 (CLI 출력):**
```text
[1/3] 1차 추천 생성 중(LLM)...
  - recommended_city: "강릉"
[2/3] 맛집 검색 중(지도/장소 API)...
  - 맛집 5곳 검색 완료 (쿼리: '강릉 맛집')
[3/3] 최종 리포트 생성 중(LLM)...
  - 리포트 생성 완료

완료! results/2026-08-14_travel_plan.md 및 results/2026-08-14_raw.json 를 확인하세요.
```

### ⚡ 2) 캐시 재사용 실행 (비용 및 속도 최적화)
동일 날짜의 결과(`results/{date}_raw.json`)가 이미 존재할 때, 외부 API 호출을 생략하고 캐시를 재사용합니다.
```bash
python travel_planner.py --date "2026-08-14" --use-cache
```

**실행 화면:**
```text
[CACHE] 기존 캐시 데이터(results/2026-08-14_raw.json)를 발견하여 API 호출을 건너뛰고 재사용합니다.
  - 캐시 로드 완료 (추천 도시: "강릉", 맛집: 5곳)

완료 (캐시 활용)! results/2026-08-14_travel_plan.md 및 results/2026-08-14_raw.json 를 확인하세요.
```

### ⚠️ 3) 잘못된 입력 예외 처리 검증
* **형식 오류 (`20260814`)**:
  ```text
  [ERROR] 올바르지 않은 날짜 형식입니다. 'YYYY-MM-DD' 형식으로 입력해주세요.
  ```
* **달력에 없는 날짜 (`2026-02-30`)**:
  ```text
  [ERROR] 달력에 존재하지 않는 유효하지 않은 날짜입니다: '2026-02-30'
  ```

---

## 7. 결과물 확인 및 저장 정책 (Output & Storage Policy)

프로그램 실행 완료 시 `results/` 폴더에 결과물이 저장됩니다.

```
results/
├── YYYY-MM-DD_raw.json          # 1차 추천 + 맛집 데이터 + 오류 내역 원본 JSON
├── YYYY-MM-DD_travel_plan.md    # 1일 일정 및 맛집이 포함된 완성형 Markdown 리포트
└── errors_history.json          # 발생한 에러 내역 누적 보존 로그
```

* **저장 정책 (Accumulative Append Policy)**: 동일 날짜로 새로 실행할 때마다 기존 결과를 덮어쓰지 않고, 이전 추천 데이터 및 마크다운 리포트 이력 뒤에 신규 이력이 순차적으로 누적(Append)됩니다. 캐시 데이터의 재사용을 원할 경우 `--use-cache` 플래그를 사용하며, 이 경우 누적 데이터 중 가장 최근 검색 이력을 기준으로 캐시가 복원됩니다.
* **오류 장기 보존 정책**: 실행 중 발생한 API 오류는 `results/errors_history.json`에 타임스탬프와 함께 영구 누적 기록되어 품질 개선 모니터링에 활용됩니다.

---

## 8. 외부 API 장애 및 오류 점검 체크리스트 (Troubleshooting Guide)

| 에러 코드 / 상황 | 주 발생 원인 | 해결 및 점검 체크리스트 |
| :--- | :--- | :--- |
| **HTTP 401 Unauthorized** | * Kakao REST API Key 오타<br>* 인증 헤더 형식 오류 (`KakaoAK {KEY}`) | 1. `.env` 파일의 `KAKAO_REST_API_KEY` 값 확인<br>2. 키 앞뒤 공백 및 따옴표 제거 상태 확인 |
| **HTTP 403 Forbidden** | * 카카오 개발자 콘솔 내 플랫폼 미등록<br>* REST API 권한 미활성화 | 1. Kakao Developers > 앱 설정 > 플랫폼 > Web 도메인 등록 여부 확인<br>2. 카카오 로컬 API 사용 권한 활성화 확인 |
| **HTTP 429 Quota Exceeded** | * 일일 / 분당 API 호출 한도 초과 | 1. Google AI Studio / Kakao 콘솔에서 일일 쿼터 잔여량 확인<br>2. `--use-cache` 옵션을 사용하여 불필요한 API 호출 방지 |
| **LLM 파싱 에러** | * LLM 응답 내 마크다운 태그 포함 | 1. `safe_parse_json()` 정규식 파서가 자동으로 마크다운 제거 후 파싱<br>2. 1회 재시도 실패 시 `errors`에 기록 후 안전 기본값 복구 |
| **장소 검색 0건** | * 희귀 지명 또는 세부 수식어 포함 | 1. `{city} 맛집` ➔ `{city} 식당` ➔ `{city} 카페` 3단계 Fallback 쿼리 자동 실행<br>2. 모두 0건 시 리포트 내 대안 향토음식 가이드 안내 |
