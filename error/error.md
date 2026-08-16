# 오류 기록 (Error History Log)

이 파일은 프로그램 실행 중 발생한 오류들을 누적 기록하는 파일입니다.

## [2026-08-16 14:38:59] 시스템/초기화 오류
- **단계 (Step)**: `argument_parsing`
  - **오류 유형 (Type)**: `VALIDATION_ERROR`
  - **오류 메시지 (Message)**: 올바르지 않은 날짜 형식입니다: 'invalid'. 'YYYY-MM-DD' 형식으로 입력해주세요.


## [2026-08-16 14:39:33] 시스템/초기화 오류
- **단계 (Step)**: `argument_parsing`
  - **오류 유형 (Type)**: `VALIDATION_ERROR`
  - **오류 메시지 (Message)**: 달력에 존재하지 않는 유효하지 않은 날짜입니다: '2026-02-30'


## [2026-08-16 14:40:46] 여행 날짜: 2026-08-25
- **단계 (Step)**: `place_search`
  - **오류 유형 (Type)**: `AUTH_ERROR`
  - **오류 메시지 (Message)**: Kakao HTTP 401


## [2026-08-16 14:51:34] 여행 날짜: 2026-08-20
- **단계 (Step)**: `report_generation`
  - **오류 유형 (Type)**: `LLM_ERROR`
  - **오류 메시지 (Message)**: 401 UNAUTHENTICATED. {'error': {'code': 401, 'message': 'Request had invalid authentication credentials. Expected OAuth 2 access token, login cookie or other valid authentication credential. See https://developers.google.com/identity/sign-in/web/devconsole-project.', 'status': 'UNAUTHENTICATED', 'details': [{'@type': 'type.googleapis.com/google.rpc.ErrorInfo', 'reason': 'ACCESS_TOKEN_TYPE_UNSUPPORTED', 'metadata': {'method': 'google.ai.generativelanguage.v1beta.GenerativeService.GenerateContent', 'service': 'generativelanguage.googleapis.com'}}]}}

