# 국내 여행지 추천 프로그램 - 전체 미션 구현 결과

## 1. 프로젝트 개요

이 프로젝트는 사용자가 입력한 여행 날짜를 기반으로, Google Gemini API와 Kakao Local API를 연동하여 국내 여행지를 추천하고, 해당 지역의 맛집 정보를 반영한 최종 여행 리포트를 생성하는 Python 프로그램입니다.

핵심 흐름은 다음과 같습니다.

1. 사용자로부터 여행 날짜를 입력받습니다.
2. Gemini API가 해당 시기 적합한 도시를 추천합니다.
3. Kakao Local API로 추천 도시의 맛집 정보를 검색합니다.
4. 최종 여행 리포트를 Markdown 형식으로 생성합니다.
5. 원본 데이터와 최종 리포트를 `results/` 폴더에 저장합니다.

## 2. 구현 목표

- CLI 기반 실행 환경 구성
- 외부 API 연동 구조 구현
- API 키 보안 관리 (`.env` 방식)
- 구조화된 JSON 생성 및 파싱 처리
- 예외 상황 대응 로직 구현
- 결과물 JSON, Markdown 저장 기능 구현

## 3. 구현 내용

### 3-1. API 키 발급 및 보안 관리

- Google Gemini API 키 준비
- Kakao Developers 앱 생성 및 REST API 키 확보
- `.env` 파일에 키 저장
- `.gitignore`로 민감 정보 보호

### 3-2. Python 개발 환경 구성

- Python 3.10 이상 환경 기준
- 필요한 라이브러리 설치

```bash
pip install google-genai requests python-dotenv
```

### 3-3. 프로그램 기능 구현

- CLI 입력 처리 (`--date`)
- 날짜 형식 검증
- Gemini를 통한 여행 도시 추천
- JSON 응답 파싱 및 재시도 처리
- Kakao Local API를 통한 맛집 검색
- 검색 결과 0건 처리
- 인증 실패 및 네트워크 오류 대응
- 최종 여행 리포트 생성
- 결과 파일 저장

### 3-4. 실행 결과

아래 명령으로 실제 실행을 검증했습니다.

```bash
python travel_planner.py --date "2026-08-13"
```

실행 흐름은 다음과 같습니다.

- `[1/3] 1차 추천 생성 중(LLM)...`
- `[2/3] 맛집 검색 중(지도/장소 API)...`
- `[3/3] 최종 리포트 생성 중(LLM)...`
- 결과 파일 생성 완료 메시지 출력

또한 잘못된 날짜를 입력한 경우에도 아래처럼 예외 처리가 동작했습니다.

```bash
python travel_planner.py --date "20260515"
```

출력 예시:

```text
[ERROR] 올바르지 않은 날짜 형식입니다. 'YYYY-MM-DD' 형식으로 입력해주세요.
```

## 4. 제출해야 하는 항목

다음 항목을 제출용으로 준비했습니다.

### 4-1. 프로그램 파일

- `travel_planner.py`

### 4-2. 실행 설명 문서

- `README.md`

### 4-3. 보안 파일

- `.env`
- `.env.example`
- `.gitignore`

### 4-4. 라이브러리 목록

- `requirements.txt`

### 4-5. 결과물 파일

실행 완료 후 `results/` 폴더에 저장되는 파일입니다.

- `YYYY-MM-DD_raw.json`
- `YYYY-MM-DD_travel_plan.md`

## 5. 결과물 경로

```text
results/
├── 2026-08-13_raw.json
└── 2026-08-13_travel_plan.md
```

## 6. 보안 주의사항

- API 키는 코드와 문서에 직접 넣지 않습니다.
- `.env` 파일은 로컬 환경에만 보관합니다.
- 공개 저장소나 공유 문서에 키를 올리지 않습니다.
- `.gitignore`에 `.env`가 포함되어 민감 정보 유출을 방지합니다.

## 7. 구현 결과 요약

이 프로젝트는 다음 조건을 만족하는 최종 결과물로 완성되었습니다.

- CLI 기반 Python 프로그램 구현
- 외부 API 연동 구조 구현
- JSON 구조화 응답 처리
- 장소 검색 API 연동
- 오류 처리 및 예외 대응
- 결과 저장 및 리포트 생성
- README 기반 실행/설정 설명 제공

## 8. 실행 방법

```bash
python travel_planner.py --date "2026-05-15"
```

## 9. 참고 예시

```text
[1/3] 1차 추천 생성 중(LLM)...
  [경고] LLM JSON 파싱 실패. 1회 재시도합니다...
  - recommended_city: "제주"
[2/3] 맛집 검색 중(지도/장소 API)...
  - 오류: 지도 API 인증 실패(401). 키/권한 설정을 확인하세요.
[3/3] 최종 리포트 생성 중(LLM)...
  - 리포트 생성 완료

완료! results\2026-08-13_travel_plan.md 및 results\2026-08-13_raw.json 를 확인하세요.
```
