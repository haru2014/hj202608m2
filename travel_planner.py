import argparse  # 명령행 인자(CLI arguments)를 파싱하기 위한 모듈
import json  # JSON 형식의 데이터를 처리하기 위한 모듈
import os  # 운영체제와 상호작용하여 파일 경로 등을 처리하기 위한 모듈
import re  # 정규표현식을 사용한 패턴 매칭을 위한 모듈
import sys  # 시스템 관련 파라미터와 함수에 접근하기 위한 모듈
from abc import ABC, abstractmethod  # 추상 클래스를 정의하기 위한 모듈
from datetime import datetime  # 날짜와 시간을 다루기 위한 모듈
import random  # 다양한 도시를 무작위로 샘플링하기 위한 모듈

import requests  # HTTP 요청을 보내 외부 API(카카오 지도 등)와 통신하기 위한 라이브러리
from dotenv import load_dotenv  # .env 파일에서 환경변수를 로드하기 위한 라이브러리
from google import genai  # Google Gemini API를 사용하기 위한 라이브러리
from google.genai import types  # Gemini API의 데이터 타입을 사용하기 위한 라이브러리

# Windows 환경 등에서 발생할 수 있는 한글 출력 인코딩 오류를 방지하기 위해 표준 출력을 UTF-8로 재설정합니다.
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 프로그램 내에서 사용할 파일 및 디렉토리의 절대 경로들을 설정합니다.
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))  # 현재 소스 파일이 위치한 디렉토리 경로
RESULTS_DIR = os.path.join(PROJECT_DIR, "results")  # 결과 보고서가 저장될 디렉토리 경로
ERROR_DIR = os.path.join(PROJECT_DIR, "error")  # 에러 로그가 저장될 디렉토리 경로
ENV_PATH = os.path.join(PROJECT_DIR, ".env")  # API 키 등이 담긴 설정 파일 경로
ERRORS_HISTORY_PATH = os.path.join(RESULTS_DIR, "errors_history.json")  # 에러 이력을 누적 저장할 JSON 파일 경로
ERROR_MD_PATH = os.path.join(ERROR_DIR, "error.md")  # 사람이 읽기 편한 형식으로 에러를 기록할 마크다운 파일 경로


def load_runtime_env():
    """
    .env 파일을 직접 읽어 환경 변수로 등록하고, load_dotenv로 보완합니다.
    (UTF-8 BOM 등 특수 문자가 포함되어 있어도 정상적으로 파싱할 수 있도록 보장합니다.)
    """
    env_path = ENV_PATH
    if os.path.exists(env_path):
        # utf-8-sig 인코딩을 사용하여 UTF-8 파일의 BOM(Byte Order Mark)을 제거하며 파일을 읽습니다.
        with open(env_path, "r", encoding="utf-8-sig") as env_file:
            for line in env_file:
                line = line.strip()
                # 빈 줄이거나, #으로 시작하는 주석이거나, '='가 없는 줄은 건너뜁니다.
                if not line or line.startswith("#") or "=" not in line:
                    continue
                # 첫 번째 '='를 기준으로 key와 value를 분리합니다.
                key, value = line.split("=", 1)
                # 앞뒤 공백 및 따옴표('나 ")를 제거한 뒤 환경변수(os.environ)에 등록합니다.
                os.environ[key.strip()] = value.strip().strip('"').strip("'")

    # dotenv 라이브러리를 이용하여 추가적으로 환경 변수를 로드합니다 (기존 수동 등록 값을 덮어쓰지 않음).
    load_dotenv(dotenv_path=env_path, override=False)


# 프로그램 실행 시 즉시 환경 변수를 로드합니다.
load_runtime_env()

# 외부 API 호출에 필요한 인증 키들을 환경 변수에서 가져옵니다.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")

# API 인증 키가 설정되어 있지 않으면 프로그램을 더 진행할 수 없으므로, 에러 메시지를 출력하고 종료합니다.
if not GEMINI_API_KEY or not KAKAO_REST_API_KEY:
    err_msg = "API 키가 설정되지 않았습니다. .env 파일에 GEMINI_API_KEY와 KAKAO_REST_API_KEY가 바르게 입력되었는지 확인하세요."
    print(f"[ERROR] {err_msg}")
    # 에러 기록용 마크다운 파일에 기록을 남깁니다.
    append_error_md([{"step": "initialization", "type": "ENV_ERROR", "message": err_msg}])
    sys.exit(1)

# Google Gemini API 클라이언트를 생성합니다.
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Gemini API 호출 시 사용할 모델들의 후보 리스트입니다.
# .env에 지정된 모델이 있으면 우선 사용하고, 없을 경우 차례대로 백업 모델로 전환(Fallback)합니다.
CANDIDATE_GEMINI_MODELS = [
    os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    "gemini-3.5-flash",
    "gemini-flash-latest",
]


def call_gemini(prompt: str, is_json: bool = False, temperature: float = 0.7) -> str:
    """
    구글 Gemini LLM API를 호출하는 함수입니다.
    네트워크 문제나 모델 변경에 유연하게 대응하기 위해 자동 재시도 및 모델 폴백(Fallback)을 적용했습니다.
    """
    # API 요청을 위한 설정 객체를 생성합니다. JSON 출력이 필요한 경우 MIME 타입을 명시해 줍니다.
    config = types.GenerateContentConfig(
        response_mime_type="application/json" if is_json else "text/plain",
        temperature=temperature
    )

    last_error = None
    # 후보 모델들을 순서대로 시도하며 성공할 때까지 반복합니다.
    for model_name in CANDIDATE_GEMINI_MODELS:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            # 성공적으로 응답을 받았고 텍스트가 있다면 이를 반환합니다.
            if response and response.text:
                return response.text
        except Exception as exc:
            # 실패 시 에러를 기록해두고 다음 후보 모델로 넘어갑니다.
            last_error = exc
            continue

    # 모든 후보 모델이 실패한 경우 에러를 발생시킵니다.
    raise last_error or RuntimeError("Gemini API 호출에 실패했습니다.")


def parse_arguments():
    """
    명령행 인자(CLI arguments)를 파싱하고 입력받은 날짜의 형식을 유효성 검사하는 함수입니다.
    """
    parser = argparse.ArgumentParser(description="국내 여행지 및 맛집 추천 프로그램")
    # 필수 인자로 --date를 받습니다.
    parser.add_argument("--date", required=True, help="여행 날짜 (YYYY-MM-DD)")
    # 선택 인자로 캐시 사용 여부를 결정하는 플래그를 받습니다.
    parser.add_argument("--use-cache", action="store_true", help="기존 동일 날짜 결과가 있을 경우 API 호출 생략 및 캐시 사용")
    args = parser.parse_args()

    # 정규표현식을 사용하여 YYYY-MM-DD 포맷(숫자4자리-숫자2자리-숫자2자리)인지 1차 검사합니다.
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        err_msg = f"올바르지 않은 날짜 형식입니다: '{args.date}'. 'YYYY-MM-DD' 형식으로 입력해주세요."
        print(f"[ERROR] {err_msg}")
        parser.print_help()
        append_error_md([{"step": "argument_parsing", "type": "VALIDATION_ERROR", "message": err_msg}])
        sys.exit(1)

    # 13월 32일과 같이 달력상에 실제로 존재하지 않는 날짜인지 2차 검사합니다 (윤년 등 검증).
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        err_msg = f"달력에 존재하지 않는 유효하지 않은 날짜입니다: '{args.date}'"
        print(f"[ERROR] {err_msg}")
        parser.print_help()
        append_error_md([{"step": "argument_parsing", "type": "VALIDATION_ERROR", "message": err_msg}])
        sys.exit(1)

    return args.date, args.use_cache


def safe_parse_json(raw_text: str) -> dict:
    """
    LLM의 원본 출력 텍스트에서 안전하게 JSON 데이터를 파싱하는 함수입니다.
    마크다운 코드 블록(```json) 기호가 포함되어 있거나 앞뒤에 공백이 있어도 정상 작동합니다.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("LLM 응답이 비어있습니다.")

    # 정규표현식을 이용하여 ```json ... ``` 혹은 ``` ... ``` 안에 들어있는 알맹이 텍스트만 추출합니다.
    cleaned = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*```', r'\1', raw_text).strip()

    # 만약 코드 블록이 없었거나, 텍스트가 걸러지지 않았다면 중괄호 {} 로 둘러싸인 구역을 찾아내어 추출합니다.
    if not cleaned or cleaned == raw_text.strip():
        json_match = re.search(r'\{[\s\S]*\}', cleaned or raw_text)
        if json_match:
            cleaned = json_match.group(0)

    try:
        result = json.loads(cleaned)
        # 파싱된 결과가 파이썬 딕셔너리 객체인지 확인합니다.
        if not isinstance(result, dict):
            raise ValueError("LLM 응답이 JSON 객체가 아닙니다.")
        return result
    except json.JSONDecodeError as e:
        # JSON 문법 에러 발생 시 디버깅을 위해 에러 내용과 원본 텍스트를 출력합니다.
        print(f"[ERROR] JSON 파싱 에러 발생: {e}")
        print(f"[DEBUG] Raw LLM Output:\n{raw_text}")
        print(f"[DEBUG] Cleaned Text:\n{cleaned}")
        raise e


def validate_recommendation_schema(data: dict, errors_list: list) -> dict:
    """
    LLM이 응답한 JSON 구조(Schema)가 약속된 규칙을 지켰는지 검증하는 함수입니다.
    필수 데이터가 누락되었거나 타입이 올바르지 않으면 미리 준비된 기본값(Default)으로 보완합니다.
    """
    # 필수 키가 누락되었을 때 채워줄 백업용 기본값 딕셔너리
    default_recommendation = {
        "recommended_city": "제주",
        "weather": "해당 시기 온화한 기후",
        "events": ["지역 대표 문화 행사"],
        "reason": "추천 스키마 검증 실패로 기본 추천이 제공됩니다."
    }

    # 전체 데이터가 딕셔너리가 아닌 경우 처리
    if not isinstance(data, dict):
        error_msg = "LLM 응답이 딕셔너리(JSON Object) 형태가 아닙니다."
        errors_list.append({"step": "schema_validation", "type": "TYPE_ERROR", "message": error_msg})
        return {"recommendations": [default_recommendation]}

    # 'recommendations' 키가 없거나 리스트 형식이 아닌 경우 처리
    recommendations = data.get("recommendations")
    if not isinstance(recommendations, list) or not recommendations:
        error_msg = "필수 키 'recommendations'가 누락되었거나 리스트 형식이 아닙니다."
        errors_list.append({"step": "schema_validation", "type": "MISSING_OR_INVALID_LIST", "message": error_msg})
        return {"recommendations": [default_recommendation]}

    validated_list = []
    # 각 필수 키와 예상 타입 및 기본값을 매핑한 정보
    required_keys = {
        "recommended_city": (str, "제주"),
        "weather": (str, "해당 시기 온화한 기후"),
        "events": (list, ["지역 대표 문화 행사"]),
        "reason": (str, "해당 시기에 방문하기 적합한 추천 여행지입니다.")
    }

    # 추천 도시 리스트를 순회하며 개별 요소를 정밀 검증합니다.
    for idx, item in enumerate(recommendations):
        if not isinstance(item, dict):
            errors_list.append({
                "step": "schema_validation",
                "type": "INVALID_ITEM_TYPE",
                "message": f"recommendations의 {idx}번째 요소가 객체(dict) 형식이 아닙니다."
            })
            validated_list.append(default_recommendation.copy())
            continue

        validated_item = {}
        for key, (expected_type, default_val) in required_keys.items():
            val = item.get(key)
            if val is None:
                # 1. 필수 키가 아예 없을 때
                errors_list.append({
                    "step": "schema_validation",
                    "type": "MISSING_KEY",
                    "message": f"추천 항목 {idx}에서 필수 키 '{key}'가 누락되어 기본값으로 대체되었습니다."
                })
                validated_item[key] = default_val
            elif not isinstance(val, expected_type):
                # 2. 키는 존재하나 데이터 타입이 안 맞을 때 (예: 문자열이어야 하는데 숫자/리스트인 경우 등)
                errors_list.append({
                    "step": "schema_validation",
                    "type": "INVALID_TYPE",
                    "message": f"추천 항목 {idx}의 키 '{key}' 타입({type(val).__name__})이 예상 타입({expected_type.__name__})과 다릅니다."
                })
                validated_item[key] = default_val
            elif isinstance(val, str) and not val.strip():
                # 3. 문자열인데 공백으로 비어있을 때
                errors_list.append({
                    "step": "schema_validation",
                    "type": "EMPTY_STRING",
                    "message": f"추천 항목 {idx}의 키 '{key}'가 빈 문자열이어서 기본값으로 대체되었습니다."
                })
                validated_item[key] = default_val
            elif isinstance(val, list):
                # 4. 리스트인 경우 각 요소에서 불필요한 공백을 지우고 문자열화하여 보정합니다.
                cleaned_list = [str(e).strip() for e in val if str(e).strip()]
                validated_item[key] = cleaned_list if cleaned_list else default_val
            else:
                # 5. 정상적인 데이터인 경우 공백 처리 후 저장
                validated_item[key] = val.strip() if isinstance(val, str) else val

        validated_list.append(validated_item)

    return {"recommendations": validated_list}


# 지도 검색이나 매칭의 정확도를 높이기 위해, LLM이 추천한 다양한 명칭을 대표 도시명으로 단일화하는 사전입니다.
CITY_ALIASES = {
    "제주도": "제주",
    "제주시": "제주",
    "제주특별자치도": "제주",
    "서귀포시": "서귀포",
    "강릉시": "강릉",
    "통영시": "통영",
    "경주시": "경주",
    "부산시": "부산",
    "부산광역시": "부산",
    "해운대": "부산",
    "해운대구": "부산",
    "전주시": "전주",
    "여수시": "여수",
    "속초시": "속초",
    "가평군": "가평",
    "양평군": "양평",
    "태안군": "태안",
    "춘천시": "춘천",
    "포항시": "포항",
    "단양군": "단양",
    "남해군": "남해",
    "안동시": "안동",
    "순천시": "순천",
    "거제시": "거제",
    "평창군": "평창",
    "인제군": "인제",
}


def normalize_city_name(city: str) -> str:
    """
    입력받은 도시 이름에서 불필요한 수식어나 행정구역 접미사(시, 군, 구, 도 등)를 지우고
    사전(CITY_ALIASES)을 활용해 통일된 대표 명칭으로 변환해 주는 함수입니다.
    """
    if not city:
        return "제주"

    cleaned = city.strip()
    # 괄호, 따옴표, 꺾쇠 등 특수문자들을 모두 제거합니다.
    cleaned = re.sub(r'[\(\)\[\]\{\}\'\"`<>]', '', cleaned).strip()

    # 사전에 등록된 동의어와 완전 일치하는 경우 즉시 정규화된 값을 리턴합니다.
    if cleaned in CITY_ALIASES:
        return CITY_ALIASES[cleaned]

    # 부분 매칭 처리 (예: "강원도 강릉"처럼 적었더라도 "강릉"이 포함되어 있으면 "강릉"으로 판단)
    for alias, standard in CITY_ALIASES.items():
        if alias in cleaned and len(alias) >= 2:
            return standard

    # 특별시, 광역시, 도 등 상위 행정구역 이름을 제거합니다.
    cleaned = re.sub(r'^(서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|세종특별자치시|경기도|강원특별자치도|강원도|충청북도|충청남도|전라북도|전북특별자치도|전라남도|경상북도|경상남도|제주특별자치도)\s*', '', cleaned)
    # 뒤에 붙는 '시', '군', '구', '도', '특별자치도' 등의 접미사를 떼어냅니다.
    cleaned = re.sub(r'특별자치도|특별시|광역시|자치시|시$|군$|구$|도$', '', cleaned).strip()

    # 정규화된 최종 이름을 리턴하되, 빈 값이 되었으면 기본값 "제주"로 리턴합니다.
    return cleaned if cleaned else "제주"


def get_llm_recommendation(date_str, errors_list, is_retry=False):
    """
    (1단계) 구글 Gemini LLM에 요청하여 주어진 날짜에 가기 좋은 국내 여행 도시 추천 정보를 생성합니다.
    """
    # 추천 가능한 다양한 국내 관광 도시 후보군
    CANDIDATE_CITIES = [
        "제주", "강릉", "부산", "경주", "전주", "여수", "속초", "가평", "양평", 
        "태안", "춘천", "포항", "단양", "남해", "안동", "순천", "거제", "평창", 
        "인제", "통영", "수원", "강화", "삼척", "영월", "보성", "담양", "목포"
    ]
    # 무작위로 8개의 도시를 샘플링하여 프롬프트에 힌트로 전달함으로써 특정 도시 쏠림 현상을 방지합니다.
    suggested = random.sample(CANDIDATE_CITIES, 8)
    suggested_str = ", ".join(suggested)

    # LLM이 출력 형태를 정확하게 유지하도록 상세하게 프롬프트를 작성합니다.
    prompt = f"""
    당신은 여행 전문가입니다. 여행 날짜 '{date_str}'에 가기 좋은 한국의 서로 다른 도시 2~3곳을 추천해주세요.
    매번 특정 유명 도시(제주, 부산, 강릉 등)만 편중되어 추천되지 않도록, 아래 제공된 후보군 목록을 포함하여 전국 각지의 숨겨진 명소와 다양한 여행 도시를 무작위로 고려해서 고르게 추천해야 합니다.
    
    [추천 고려 대상 도시 예시]
    {suggested_str} (이 목록 외에 다른 국내의 매력적인 도시를 자유롭게 추천해도 무방합니다)

    응답은 반드시 아래 JSON 스키마를 엄격히 준수하여 오직 JSON 형식의 텍스트만 출력하세요. 다른 설명은 포함하지 마세요.

    JSON 스키마:
    {{
      "recommendations": [
        {{
          "recommended_city": "도시명 (예: 경주, 여수)",
          "weather": "해당 시기 일반적 날씨 요약",
          "events": ["행사 또는 축제 후보 1~3개"],
          "reason": "추천 근거 2~4문장"
        }}
      ]
    }}
    """

    # 이전 시도에서 JSON 형식 오류가 나서 다시 시도(Retry)하는 경우 추가 경고 프롬프트를 이어 붙입니다.
    if is_retry:
        prompt += "\n주의: 이전 응답의 JSON 파싱에 실패했습니다. 규칙에 맞춰 정확한 JSON만 반환하세요."

    try:
        # call_gemini 함수를 사용해 JSON 출력을 강제하고 결과를 얻습니다.
        raw_text = call_gemini(prompt, is_json=True, temperature=0.7)

        # 받아온 원본 텍스트에서 JSON 데이터 구조만 찾아 파싱합니다.
        raw_data = safe_parse_json(raw_text)

        # 파싱된 데이터 구조가 스키마에 맞는지 검증합니다.
        validated_data = validate_recommendation_schema(raw_data, errors_list)

        # 각 추천 도시명을 API 검색에 적절하게 표준화(정규화)합니다.
        for item in validated_data["recommendations"]:
            recommended_city = normalize_city_name(item["recommended_city"])
            item["recommended_city"] = recommended_city

        return validated_data

    except Exception as exc:
        # 첫 번째 시도에서 에러가 발생한 경우 딱 한 번만 재시도(Retry)해 봅니다.
        if not is_retry:
            print("  [경고] LLM JSON 파싱 실패. 1회 재시도합니다...")
            return get_llm_recommendation(date_str, errors_list, is_retry=True)

        # 재시도까지 모두 최종 실패한 경우 에러 목록에 로그를 남깁니다.
        error_record = {
            "step": "llm_recommendation",
            "type": "PARSE_ERROR",
            "message": f"JSON 파싱 최종 실패: {exc}"
        }
        errors_list.append(error_record)
        # 프로그램이 중단되지 않도록 최소한의 데이터가 담긴 기본 구조를 리턴합니다.
        return {
            "recommendations": [
                {
                    "recommended_city": "제주",
                    "weather": "날씨 정보 파싱 실패",
                    "events": [],
                    "reason": "기본 추천 도시로 대체되었습니다."
                }
            ]
        }


# ==========================================================
# 장소 검색 서비스 제공자(Place Search Provider) 추상화 레이어
# ==========================================================
# 확장성(새로운 지도 검색 API 연동 등)을 고려하여 객체지향의 추상 클래스(Interface 역할)로 틀을 구현해 둡니다.

class PlaceSearchProvider(ABC):
    """
    맛집이나 장소를 검색하는 클래스가 공통으로 구현해야 할 부모 추상 클래스입니다.
    """
    @abstractmethod
    def search_places(self, city: str, errors_list: list) -> list:
        pass


class KakaoPlaceSearchProvider(PlaceSearchProvider):
    """
    카카오 로컬 API를 구현체로 사용하는 실제 맛집 검색 클래스입니다.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        # 카카오 로컬 API의 키워드 검색 엔드포인트 URL
        self.base_url = "https://dapi.kakao.com/v2/local/search/keyword.json"

    def search_places(self, city: str, errors_list: list) -> list:
        # 카카오 API 호출에 필수적인 헤더(인증 정보)를 구성합니다.
        headers = {"Authorization": f"KakaoAK {self.api_key}"}
        
        # 검색 결과가 확실히 나올 수 있도록 점진적 쿼리 후보들(맛집 -> 식당 -> 카페)을 준비합니다.
        search_queries = [f"{city} 맛집", f"{city} 식당", f"{city} 카페"]

        for query in search_queries:
            # 한 번에 최대 5개의 검색 결과만 가져옵니다.
            params = {"query": query, "size": 5}
            try:
                # 5초의 타임아웃을 설정해 지도 API가 오랜 시간 먹통이 되는 상황을 방지합니다.
                res = requests.get(self.base_url, headers=headers, params=params, timeout=5)

                # 인증 오류(401, 403)인 경우 키 설정 에러로 간주해 즉시 빠져나옵니다.
                if res.status_code in [401, 403]:
                    print(f"  - 오류: 지도 API 인증 실패({res.status_code}). 키/권한 설정을 확인하세요.")
                    errors_list.append({
                        "step": "place_search",
                        "type": "AUTH_ERROR",
                        "message": f"Kakao HTTP {res.status_code}"
                    })
                    return []

                # HTTP 상태 코드가 200번대가 아닌 에러인 경우 예외를 발생시킵니다.
                res.raise_for_status()
                result = res.json()
                documents = result.get("documents", [])

                # 검색된 결과(식당/카페 정보)가 하나 이상 있다면 데이터를 정돈하여 리턴합니다.
                if documents:
                    places = []
                    for doc in documents:
                        places.append({
                            "name": doc.get("place_name", ""),
                            # 도로명 주소가 있으면 사용하고 없으면 지번 주소를 사용합니다.
                            "address": doc.get("road_address_name") or doc.get("address_name", ""),
                            "category": doc.get("category_name", ""),
                            "url": doc.get("place_url", ""),  # 카카오맵 웹 링크
                            "x": doc.get("x", ""),  # 경도
                            "y": doc.get("y", "")   # 위도
                        })
                    print(f"  - 맛집 {len(places)}곳 검색 완료 (쿼리: '{query}')")
                    return places

            except Exception as exc:
                # 네트워크 장애나 API 장애 발생 시 에러 로그를 남기고, 다음 백업 쿼리로 재시도합니다.
                print(f"  - 지도 API 호출 중 오류 발생 ('{query}'): {exc}")
                errors_list.append({
                    "step": "place_search",
                    "type": "NETWORK_OR_API_ERROR",
                    "message": f"Query '{query}' failed: {exc}"
                })

        # 모든 쿼리가 실패하여 검색된 장소가 없을 경우 기록을 남기고 빈 리스트를 리턴합니다.
        print("  - 검색 결과 0건 (데이터 없음으로 진행)")
        errors_list.append({
            "step": "place_search",
            "type": "EMPTY_RESULT",
            "message": f"0 results for city={city}"
        })
        return []


def get_place_search_provider() -> PlaceSearchProvider:
    """
    환경 변수(PLACE_SEARCH_PROVIDER) 설정을 조회하여 어떤 검색 공급자를 쓸지 결정하여 반환합니다.
    (현재는 기본값으로 Kakao를 반환하며, 향후 타 서비스 추가가 용이하도록 팩토리 함수 형태로 설계했습니다.)
    """
    provider_name = os.getenv("PLACE_SEARCH_PROVIDER", "kakao").lower()
    if provider_name == "kakao":
        return KakaoPlaceSearchProvider(api_key=KAKAO_REST_API_KEY)
    return KakaoPlaceSearchProvider(api_key=KAKAO_REST_API_KEY)


def generate_final_report(date_str, recommendations, errors_list):
    """
    (3단계) 수집된 모든 여행 정보와 맛집 데이터를 바탕으로 LLM을 활용해 풍성한 마크다운 리포트를 작성합니다.
    만약 LLM 리포트 작성 도중 장애가 나면, 로컬 데이터 기반의 템플릿(Fallback)으로 자동 대체합니다.
    """
    # LLM이 참고할 수 있도록 데이터를 문자열 형태의 JSON으로 변환합니다.
    rec_str = json.dumps(recommendations, ensure_ascii=False, indent=2)
    errors_str = json.dumps(errors_list, ensure_ascii=False, indent=2) if errors_list else "없음"

    prompt = f"""
    당신은 여행 리포트 작성가입니다. 아래 제공된 정보를 바탕으로 여러 추천 여행지들을 비교 및 제안하는 종합 여행 리포트를 Markdown 형식으로 작성해주세요.

    [기본 정보]
    - 여행 날짜: {date_str}
    - 추천 지역 및 맛집 목록: {rec_str}
    - 발생한 오류: {errors_str}

    [작성 규칙]
    - 마크다운 헤더(#, ##)를 활용하여 정돈된 문서로 만드세요.
    - 전체 개요(예: "추천 여행지 개요 및 비교")를 처음에 작성하고, 그 다음 각 추천 도시별로 세부 섹션을 나누어 상세히 작성하세요.
    - 각 도시별 맛집 정보가 비어 있거나 '데이터 없음'이면 맛집 섹션에 "데이터 없음 (장소 검색 결과 0건)"으로 강조 표기하고, 인근 대표 향토음식이나 전통시장을 대안으로 추천하세요.
    - 추천 도시 각각에 대해 오전/오후/저녁으로 나눈 1일 일정 제안 코너를 반드시 포함하세요.
    - 발생한 오류 내역(errors) 섹션을 리포트의 맨 마지막에 포함하세요.
    """

    try:
        # LLM을 불러 자유로운 줄글 마크다운 형식의 보고서를 작성시킵니다.
        report_text = call_gemini(prompt, is_json=False)
        return report_text
    except Exception as exc:
        # LLM을 통한 보고서 작성이 실패했을 때의 폴백(동작 보장 대안) 처리
        errors_list.append({
            "step": "report_generation",
            "type": "LLM_ERROR",
            "message": str(exc)
        })
        
        # 로컬에서 데이터 결합만으로 그럴싸한 마크다운을 직접 조립하여 생성합니다.
        fallback_md = []
        fallback_md.append(f"# ✈️ {date_str} 여행 계획 리포트 (예비 생성)")
        fallback_md.append(f"\n> **안내**: LLM을 통한 리포트 생성에 실패하여 로컬 데이터를 기반으로 리포트를 긴급 생성했습니다. (오류: {exc})\n")
        
        # 추천 도시 순회하며 마크다운 작성
        for idx, rec in enumerate(recommendations, 1):
            city = rec.get('recommended_city', '제주')
            reason = rec.get('reason', '기본 추천 도시로 대체되었습니다.')
            weather = rec.get('weather', '날씨 정보 파싱 실패')
            events = rec.get('events', [])
            places = rec.get('places', [])
            
            fallback_md.append(f"## 📍 추천 여행지 {idx}: {city}")
            fallback_md.append(f"- **추천 이유**: {reason}")
            fallback_md.append(f"- **날씨 요약**: {weather}")
            if events:
                fallback_md.append(f"- **주요 행사 및 축제**: {', '.join(events)}")
            fallback_md.append("")
            
            fallback_md.append("### 🍴 추천 맛집 및 장소")
            if places:
                # 검색된 맛집이 있으면 정보를 정리해서 출력
                for p_idx, p in enumerate(places, 1):
                    name = p.get("name", "이름 없음")
                    address = p.get("address", "주소 정보 없음")
                    category = p.get("category", "")
                    url = p.get("url", "")
                    
                    place_line = f"{p_idx}. **{name}**"
                    if category:
                        # 긴 카테고리 문자열(예: 음식점 > 한식 > 육류,고기)에서 맨 마지막 명칭만 추출
                        place_line += f" ({category.split(' > ')[-1]})"
                    fallback_md.append(place_line)
                    fallback_md.append(f"   - 주소: {address}")
                    if url:
                        fallback_md.append(f"   - [Kakao Map 바로가기]({url})")
            else:
                # 검색된 맛집이 없는 경우 대안 제시
                fallback_md.append("> **데이터 없음 (장소 검색 결과 0건)**")
                fallback_md.append("인근의 대표적인 전통시장이나 향토 음식점(예: 향토시장, 전통 5일장)을 대안으로 추천해 드립니다.")
            fallback_md.append("")
            
            # 하루 추천 일정 작성 (오전/오후/저녁)
            fallback_md.append("### 📅 제안 일정 (오전/오후/저녁)")
            fallback_md.append(f"- **오전 (09:00 - 12:00)**: {city} 도착 및 대표 관광 명소 탐방")
            if places:
                fallback_md.append(f"- **오후 (12:00 - 18:00)**: 맛집 `{places[0].get('name')}`에서 맛있는 식사 및 주변 카페/거리 투어")
            else:
                fallback_md.append(f"- **오후 (12:00 - 18:00)**: 현지 음식점에서 점심 식사 후 주변 관광지 방문")
            if len(places) > 1:
                fallback_md.append(f"- **저녁 (18:00 - 21:00)**: `{places[1].get('name')}`에서 저녁 식사 및 대표 야경 감상")
            else:
                fallback_md.append(f"- **저녁 (18:00 - 21:00)**: 저녁 식사 후 숙소 이동 및 휴식")
            fallback_md.append("\n---\n")
            
        # 프로그램 구동 중 에러가 있었다면 보고서 하단에 첨부
        fallback_md.append("## ⚠️ 발생한 오류 요약 (Errors Summary)")
        if errors_list:
            for err in errors_list:
                fallback_md.append(f"- **{err.get('step', 'N/A')}** ({err.get('type', 'N/A')}): {err.get('message', 'N/A')}")
        else:
            fallback_md.append("- 발생한 오류가 없습니다.")
            
        return "\n".join(fallback_md)


def sanitize_sensitive_data(text: str) -> str:
    """
    저장될 파일(JSON, MD 등) 내에 API 인증 키와 같은 민감 정보가 포함되어 유출되지 않도록
    특정 패턴을 감지하여 보호된 형태의 텍스트로 치환(마스킹)하는 안전 함수입니다.
    """
    if not text:
        return text
    sanitized = text
    # 현재 프로그램이 로드하고 있는 실제 구글/카카오 API 키를 감지하여 지워줍니다.
    if GEMINI_API_KEY:
        sanitized = sanitized.replace(GEMINI_API_KEY, "[PROTECTED_GEMINI_KEY]")
    if KAKAO_REST_API_KEY:
        sanitized = sanitized.replace(KAKAO_REST_API_KEY, "[PROTECTED_KAKAO_KEY]")
    # 정규식을 이용해 텍스트 내의 일반적인 구글 API 키 및 카카오 API 키 패턴을 찾아내 마스킹 처리합니다.
    sanitized = re.sub(r'AIzaSy[A-Za-z0-9_-]{33}', '[PROTECTED_API_KEY]', sanitized)
    sanitized = re.sub(r'KakaoAK\s+[0-9a-fA-F]{32}', 'KakaoAK [PROTECTED_KEY]', sanitized)
    return sanitized


def append_errors_history(date_str: str, errors: list):
    """
    개발자가 모니터링하고 디버깅할 수 있도록 프로그램 내부 에러 발생 히스토리를
    누적하여 JSON 파일로 기록해 두는 함수입니다.
    """
    if not errors:
        return
    try:
        history = []
        # 기존 기록 파일이 있다면 읽어오고, 새로 발생한 에러를 덧붙여(Append) 다시 씁니다.
        if os.path.exists(ERRORS_HISTORY_PATH):
            with open(ERRORS_HISTORY_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        history.append({
            "date": date_str,
            "timestamp": datetime.now().isoformat(),
            "errors": errors
        })
        with open(ERRORS_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def is_failed_report(md_path: str) -> bool:
    """
    저장된 마크다운 보고서가 없거나 내용이 비어있거나 혹은 예비 생성(LLM 리포트 실패 대안)으로
    불완전하게 생성된 상태인지 체크하는 함수입니다.
    """
    if not os.path.exists(md_path) or os.path.getsize(md_path) == 0:
        return True
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read(1024)  # 파일의 앞부분 1KB만 효율적으로 읽어 들여 확인합니다.
            # 실패를 의미하는 문구나 예비 생성이 기록되어 있다면 실패 상태로 판별합니다.
            if "리포트 생성 실패" in content or "오류가 발생했습니다" in content or "예비 생성" in content:
                return True
    except Exception:
        return True
    return False


def append_error_md(errors: list, date_str: str = None):
    """
    사람이 직관적으로 에러 원인과 발생 단계를 볼 수 있도록 error/error.md 파일에
    마크다운 포맷으로 에러 내역을 누적 기록해 두는 함수입니다.
    """
    if not errors:
        return
    try:
        # 에러 폴더가 생성되어 있지 않으면 만들어줍니다.
        os.makedirs(ERROR_DIR, exist_ok=True)
        # 처음 쓰는 상태인지 아니면 기존에 덧붙여 쓰는 상태인지 파일 확인을 거칩니다.
        write_header = not os.path.exists(ERROR_MD_PATH) or os.path.getsize(ERROR_MD_PATH) == 0

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        md_lines = []
        # 파일이 완전히 비어있거나 새로 만든 경우 제목과 안내 멘트를 적습니다.
        if write_header:
            md_lines.append("# 오류 기록 (Error History Log)")
            md_lines.append("\n이 파일은 프로그램 실행 중 발생한 오류들을 누적 기록하는 파일입니다.\n")
        
        if date_str:
            md_lines.append(f"## [{timestamp}] 여행 날짜: {date_str}")
        else:
            md_lines.append(f"## [{timestamp}] 시스템/초기화 오류")
            
        # 에러 내역들을 하나씩 포맷팅하여 적습니다.
        for err in errors:
            step = err.get("step", "N/A")
            err_type = err.get("type", "N/A")
            message = err.get("message", "N/A")
            # 로그에 API 키 같은 민감 정보가 포함되어 있다면 안전하게 제거한 뒤 적습니다.
            message = sanitize_sensitive_data(message)
            md_lines.append(f"- **단계 (Step)**: `{step}`")
            md_lines.append(f"  - **오류 유형 (Type)**: `{err_type}`")
            md_lines.append(f"  - **오류 메시지 (Message)**: {message}")
        
        md_lines.append("") # 문단 구분용 빈 줄
        
        output_content = "\n".join(md_lines) + "\n"
        if not write_header:
            output_content = "\n" + output_content
            
        with open(ERROR_MD_PATH, "a", encoding="utf-8") as f:
            f.write(output_content)
    except Exception as exc:
        print(f"[WARNING] error.md 기록 실패: {exc}", file=sys.stderr)


def main():
    """
    프로그램의 전체 실행 흐름을 제어하는 핵심 메인 함수입니다.
    """
    # 1. 인자 처리 및 날짜 유효성 검증
    date_str, use_cache = parse_arguments()
    errors_list = []

    # 결과를 저장할 디렉토리를 생성합니다.
    os.makedirs(RESULTS_DIR, exist_ok=True)
    json_path = os.path.join(RESULTS_DIR, f"{date_str}_raw.json")
    md_path = os.path.join(RESULTS_DIR, f"{date_str}_travel_plan.md")

    # 2. 캐시 확인 및 적용 (속도 개선과 API 비용 절감을 위한 로직)
    if use_cache and os.path.exists(json_path):
        print(f"[CACHE] 기존 캐시 데이터({json_path})를 발견하여 API 호출을 건너뛰고 재사용합니다.")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            
            # 캐시가 여러 실행 결과의 누적 리스트 구조일 경우 가장 마지막 데이터(최신)를 가져옵니다.
            if isinstance(cached_data, list):
                cached_raw = cached_data[-1] if cached_data else {}
            else:
                cached_raw = cached_data

            errors_list = cached_raw.get("errors", [])
            
            # 구버전 및 신버전 캐시 스키마(복수 추천 구조)와의 하위 호환성 매핑 처리
            if "recommendations" in cached_raw:
                recommendations = cached_raw["recommendations"]
            else:
                # 구버전 캐시 포맷인 경우 신버전 포맷(리스트)에 맞춰 강제로 변경해 줍니다.
                rec_data = cached_raw.get("recommendation", {})
                places = cached_raw.get("places", [])
                recommendations = [
                    {
                        "recommended_city": rec_data.get("recommended_city", "제주"),
                        "weather": rec_data.get("weather", "날씨 정보 없음"),
                        "events": rec_data.get("events", []),
                        "reason": rec_data.get("reason", ""),
                        "places": places
                    }
                ]

            cities_str = ", ".join([r.get("recommended_city", "") for r in recommendations])
            print(f"  - 캐시 로드 완료 (추천 도시: \"{cities_str}\")")

            # 만약 캐시는 있는데 마크다운 보고서 파일이 유실되었거나 이전 생성 과정에서 깨졌다면 다시 복원(LLM 리포트 재작성)해 줍니다.
            if is_failed_report(md_path):
                print(f"[3/3] 최종 리포트 재생성/복원 중(LLM)...")
                orig_err_count = len(errors_list)
                report_md = generate_final_report(date_str, recommendations, errors_list)
                with open(md_path, "w", encoding="utf-8") as file_obj:
                    file_obj.write(sanitize_sensitive_data(report_md))
                if len(errors_list) > orig_err_count:
                    new_errors = errors_list[orig_err_count:]
                    append_error_md(new_errors, date_str)

            print(f"\n완료 (캐시 활용)! {md_path} 및 {json_path} 를 확인하세요.")
            return
        except Exception as exc:
            print(f"  [경고] 캐시 로드 실패({exc}). 일반 실행으로 전환합니다.")

    # 3. 신규 여행지 추천 생성 (LLM 1단계 호출)
    print(f"[1/3] 1차 추천 생성 중(LLM)...")
    rec_data = get_llm_recommendation(date_str, errors_list)
    recommendations = rec_data.get("recommendations", [])
    cities_str = ", ".join([r.get("recommended_city", "") for r in recommendations])
    print(f"  - recommended_cities: \"{cities_str}\"")

    # 4. 지도 API를 이용해 추천된 각 도시의 맛집 장소 검색 (2단계 API 호출)
    print(f"[2/3] 맛집 검색 중(지도/장소 API)...")
    place_provider = get_place_search_provider()
    for rec in recommendations:
        city = rec.get("recommended_city", "제주")
        print(f"  - '{city}' 맛집 검색 중...")
        places = place_provider.search_places(city, errors_list)
        rec["places"] = places  # 검색된 맛집 목록을 해당 도시 정보 안에 통합합니다.

    # 5. 최종 종합 보고서 작성 (LLM 3단계 호출)
    print(f"[3/3] 최종 리포트 생성 중(LLM)...")
    report_md = generate_final_report(date_str, recommendations, errors_list)
    print("  - 리포트 생성 완료")

    # 저장할 원본 묶음 데이터 구성
    raw_data = {
        "date": date_str,
        "recommendations": recommendations,
        "errors": errors_list
    }

    # 6. JSON 파일 백업 및 마크다운 파일 저장
    # 기존 JSON 파일이 이미 존재한다면 내용을 가져와서 새로운 데이터와 합친 후(Append) 저장합니다.
    existing_list = []
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as file_obj:
                existing_data = json.load(file_obj)
            if isinstance(existing_data, list):
                existing_list = existing_data
            elif isinstance(existing_data, dict):
                existing_list = [existing_data]
        except Exception as exc:
            print(f"  [경고] 기존 JSON 파일 로드 실패({exc}). 새로운 파일로 재작성합니다.")
            existing_list = []

    existing_list.append(raw_data)

    # 저장 직전 모든 민감한 API 인증 키 정보를 지워줍니다(Sanitization).
    sanitized_json = sanitize_sensitive_data(json.dumps(existing_list, ensure_ascii=False, indent=2))
    sanitized_md = sanitize_sensitive_data(report_md)

    # 파일 쓰기 수행
    with open(json_path, "w", encoding="utf-8") as file_obj:
        file_obj.write(sanitized_json)

    # 기존 마크다운 결과 보고서가 있다면 내용을 덧붙이고, 없으면 새로 작성합니다.
    if os.path.exists(md_path) and os.path.getsize(md_path) > 0:
        with open(md_path, "a", encoding="utf-8") as file_obj:
            file_obj.write("\n\n---\n\n" + sanitized_md)
    else:
        with open(md_path, "w", encoding="utf-8") as file_obj:
            file_obj.write(sanitized_md)

    # 7. 장기적인 모니터링을 위한 에러 히스토리 추가 기록
    append_errors_history(date_str, errors_list)
    append_error_md(errors_list, date_str)

    print(f"\n완료! {md_path} 및 {json_path} 를 확인하세요.")


if __name__ == "__main__":
    # 파이썬 스크립트 실행 시의 시작점(EntryPoint)입니다.
    try:
        main()
    except Exception as e:
        # 프로그램 실행 중 처리되지 못한 예외(Unhandled exception)가 난 경우 로그를 기록하고 안전하게 종료합니다.
        err_msg = f"프로그램 실행 중 예기치 못한 에러가 발생했습니다: {e}"
        print(f"[FATAL] {err_msg}", file=sys.stderr)
        append_error_md([{"step": "main_execution", "type": "UNHANDLED_EXCEPTION", "message": err_msg}])
        sys.exit(1)
