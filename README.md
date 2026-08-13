# 2단계: API 연동형 국내 여행 추천 프로그램

## 프로젝트 개요

이 프로젝트는 사용자가 입력한 여행 날짜를 기반으로, Gemini API와 Kakao Local API를 연동하여 국내 여행지를 추천하고 맛집 정보를 함께 정리한 여행 리포트를 생성하는 Python 프로그램입니다.

핵심 흐름은 아래와 같습니다.

1. 사용자 입력으로 여행 날짜를 받습니다.
2. Gemini API가 해당 시기에 적합한 도시에 대한 추천 정보를 구조화된 JSON으로 생성합니다.
3. Kakao Local API로 해당 도시의 맛집 정보를 검색합니다.
4. 최종 리포트가 Markdown 형식으로 생성됩니다.
5. 결과 데이터와 리포트 파일이 `results/` 폴더에 저장됩니다.

## 구현 목표

- CLI 기반 실행 환경 구성
- API 키 보안 관리 (`.env` 사용)
- 외부 API 호출 예외 처리
- 구조화된 JSON 결과 생성
- 최종 Markdown 리포트 산출

## 개발 환경

- Python 3.10 이상
- 라이브러리 설치

```bash
pip install google-genai requests python-dotenv
```

## API 키 설정

프로젝트 루트에 `.env` 파일을 생성하고 아래와 같이 입력합니다.

```env
GEMINI_API_KEY=your_google_gemini_api_key_here
KAKAO_REST_API_KEY=your_kakao_rest_api_key_here
```

> 중요한 점: 실제 API 키는 코드나 문서에 직접 작성하지 않고 `.env` 파일로 관리해야 합니다.
> `.gitignore`에 `.env`가 포함되어 있어 공개 저장소에 노출되지 않도록 설정했습니다.

## 실행 방법

```bash
python travel_planner.py --date "2026-05-15"
```

## 결과물

실행 완료 후 `results/` 폴더 안에 아래 파일이 생성됩니다.

- `YYYY-MM-DD_raw.json`: 추천 결과, 장소 검색 결과, 오류 목록
- `YYYY-MM-DD_travel_plan.md`: 최종 여행 리포트 Markdown

## 예외 처리 정책

다음 상황을 모두 고려해 프로그램을 설계했습니다.

- API 키 미설정 시 프로그램 즉시 종료
- LLM JSON 파싱 실패 시 1회 재시도
- Kakao API 인증 실패 시 에러 기록 후 프로그램 계속 진행
- 검색 결과 0건 시 데이터 없음 상태로 리포트 작성
- 네트워크 오류 발생 시 예외 로그 남기고 다음 단계 유지

## 보안 주의사항

- `.env` 파일은 절대 외부로 공유하지 않습니다.
- 결과물과 README에 실제 키 값을 넣지 않습니다.
- GitHub와 같은 공개 환경에서는 민감한 키가 누출되지 않도록 주의합니다.

## 2단계 구현 결과 요약

다음 기능이 포함된 상태입니다.

- `travel_planner.py` 생성
- `02_2단계_개발계획.md` 작성
- `02_2단계_구현결과.md` 작성
- 실행 시 results 폴더에 JSON과 Markdown 저장

## 참고 실행 예시

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
