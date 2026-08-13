# 국내 여행지 추천 프로그램

사용자가 지정한 날짜에 맞는 최적의 국내 여행지를 AI가 추천하고, 카카오 장소 검색 API를 연동하여 해당 지역의 맛집 정보 및 1일 여행 일정을 담은 리포트를 자동 생성합니다.

## 프로젝트 개요

이 프로그램은 다음 흐름으로 동작합니다.

1. 사용자가 `--date` 옵션으로 여행 날짜를 입력합니다.
2. Gemini API가 해당 시기 적합한 국내 도시를 추천합니다.
3. Kakao Local API로 추천 도시의 맛집 정보를 검색합니다.
4. 최종 여행 리포트가 Markdown 형식으로 생성됩니다.
5. 원본 JSON 데이터와 최종 리포트가 `results/` 폴더에 저장됩니다.

## 실행 환경

- Python 3.10 이상
- 필요한 라이브러리

```bash
pip install google-genai requests python-dotenv
```

## API 키 설정 방법

프로젝트 루트에 `.env` 파일을 생성하고 아래 내용을 입력합니다.

```env
GEMINI_API_KEY=your_google_gemini_api_key_here
KAKAO_REST_API_KEY=your_kakao_rest_api_key_here
```

> API 키는 코드에 직접 포함하지 않고 `.env` 파일로 관리해야 합니다.
> GitHub나 공유 폴더에 공개되지 않도록 주의하세요.

## 실행 방법

```bash
python travel_planner.py --date "2026-05-15"
```

## 결과물 확인

실행이 완료되면 `results/` 폴더 안에 다음 파일들이 생성됩니다.

- `YYYY-MM-DD_raw.json`: 추천 결과, 맛집 검색 결과, 오류 요약
- `YYYY-MM-DD_travel_plan.md`: 최종 여행 리포트

## 보안 주의사항

- `.env` 파일은 절대 공개 저장소에 올리지 마세요.
- `.gitignore`에 `.env`를 포함해 두었습니다.
- 키가 유출되면 외부 서비스 과금이나 불법 사용 문제가 발생할 수 있습니다.

## 문제점 처리 원칙

- API 키 미설정 시 즉시 종료합니다.
- 지도 API 인증 오류가 발생해도 다음 단계로 진행합니다.
- LLM JSON 파싱 실패 시 1회 재시도 후 실패 시 기본값을 사용합니다.
- 검색 결과가 0건이어도 프로그램은 중단되지 않고 리포트 작성으로 이어집니다.
