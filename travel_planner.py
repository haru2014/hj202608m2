import argparse
import json
import os
import re
import sys
from abc import ABC, abstractmethod
from datetime import datetime

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(PROJECT_DIR, "results")
ERROR_DIR = os.path.join(PROJECT_DIR, "error")
ENV_PATH = os.path.join(PROJECT_DIR, ".env")
ERRORS_HISTORY_PATH = os.path.join(RESULTS_DIR, "errors_history.json")
ERROR_MD_PATH = os.path.join(ERROR_DIR, "error.md")


def load_runtime_env():
    env_path = ENV_PATH
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8-sig") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")

    load_dotenv(dotenv_path=env_path, override=False)


load_runtime_env()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")

if not GEMINI_API_KEY or not KAKAO_REST_API_KEY:
    err_msg = "API 키가 설정되지 않았습니다. .env 파일에 GEMINI_API_KEY와 KAKAO_REST_API_KEY가 바르게 입력되었는지 확인하세요."
    print(f"[ERROR] {err_msg}")
    append_error_md([{"step": "initialization", "type": "ENV_ERROR", "message": err_msg}])
    sys.exit(1)

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
CANDIDATE_GEMINI_MODELS = [
    os.getenv("GEMINI_MODEL", "gemini-3.7-flash"),
    "gemini-3-flash-preview",
    "gemini-flash-latest",
]


def call_gemini(prompt: str, is_json: bool = False, temperature: float = 0.7) -> str:
    """
    Call Gemini API with automatic model fallback and JSON structure enforcement.
    """
    config = types.GenerateContentConfig(
        response_mime_type="application/json" if is_json else "text/plain",
        temperature=temperature
    )

    last_error = None
    for model_name in CANDIDATE_GEMINI_MODELS:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            if response and response.text:
                return response.text
        except Exception as exc:
            last_error = exc
            continue

    raise last_error or RuntimeError("Gemini API 호출에 실패했습니다.")


def parse_arguments():
    """
    Parse and validate CLI arguments with regex and real calendar date validation.
    """
    parser = argparse.ArgumentParser(description="국내 여행지 및 맛집 추천 프로그램")
    parser.add_argument("--date", required=True, help="여행 날짜 (YYYY-MM-DD)")
    parser.add_argument("--use-cache", action="store_true", help="기존 동일 날짜 결과가 있을 경우 API 호출 생략 및 캐시 사용")
    args = parser.parse_args()

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        err_msg = f"올바르지 않은 날짜 형식입니다: '{args.date}'. 'YYYY-MM-DD' 형식으로 입력해주세요."
        print(f"[ERROR] {err_msg}")
        parser.print_help()
        append_error_md([{"step": "argument_parsing", "type": "VALIDATION_ERROR", "message": err_msg}])
        sys.exit(1)

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
    Robust JSON parser that handles markdown formatting, code fences, and whitespace.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("LLM 응답이 비어있습니다.")

    # Remove markdown code fences
    cleaned = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*```', r'\1', raw_text).strip()

    # If no markdown was found or brackets still need extraction
    if not cleaned or cleaned == raw_text.strip():
        json_match = re.search(r'\{[\s\S]*\}', cleaned or raw_text)
        if json_match:
            cleaned = json_match.group(0)

    try:
        result = json.loads(cleaned)
        if not isinstance(result, dict):
            raise ValueError("LLM 응답이 JSON 객체가 아닙니다.")
        return result
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 파싱 에러 발생: {e}")
        print(f"[DEBUG] Raw LLM Output:\n{raw_text}")
        print(f"[DEBUG] Cleaned Text:\n{cleaned}")
        raise e


def validate_recommendation_schema(data: dict, errors_list: list) -> dict:
    """
    Strict validation for LLM recommendation JSON schema.
    Validates presence and types of required keys: recommended_city, weather, events, reason.
    """
    if not isinstance(data, dict):
        error_msg = "LLM 응답이 딕셔너리(JSON Object) 형태가 아닙니다."
        errors_list.append({"step": "schema_validation", "type": "TYPE_ERROR", "message": error_msg})
        return {
            "recommended_city": "제주",
            "weather": "해당 시기 온화한 기후",
            "events": ["지역 대표 문화 행사"],
            "reason": "추천 스키마 검증 실패로 기본 추천이 제공됩니다."
        }

    validated = {}
    required_keys = {
        "recommended_city": (str, "제주"),
        "weather": (str, "해당 시기 온화한 기후"),
        "events": (list, ["지역 대표 문화 행사"]),
        "reason": (str, "해당 시기에 방문하기 적합한 추천 여행지입니다.")
    }

    for key, (expected_type, default_val) in required_keys.items():
        val = data.get(key)
        if val is None:
            errors_list.append({
                "step": "schema_validation",
                "type": "MISSING_KEY",
                "message": f"필수 키 '{key}'가 누락되어 기본값으로 대체되었습니다."
            })
            validated[key] = default_val
        elif not isinstance(val, expected_type):
            errors_list.append({
                "step": "schema_validation",
                "type": "INVALID_TYPE",
                "message": f"키 '{key}'의 타입({type(val).__name__})이 예상 타입({expected_type.__name__})과 일치하지 않습니다."
            })
            validated[key] = default_val
        elif isinstance(val, str) and not val.strip():
            errors_list.append({
                "step": "schema_validation",
                "type": "EMPTY_STRING",
                "message": f"키 '{key}'가 빈 문자열이어서 기본값으로 대체되었습니다."
            })
            validated[key] = default_val
        elif isinstance(val, list):
            cleaned_list = [str(item).strip() for item in val if str(item).strip()]
            validated[key] = cleaned_list if cleaned_list else default_val
        else:
            validated[key] = val.strip() if isinstance(val, str) else val

    return validated


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
    Advanced city normalization with alias dictionary, sub-region cleaning, and suffix pruning.
    """
    if not city:
        return "제주"

    cleaned = city.strip()
    cleaned = re.sub(r'[\(\)\[\]\{\}\'\"`<>]', '', cleaned).strip()

    # Direct alias match
    if cleaned in CITY_ALIASES:
        return CITY_ALIASES[cleaned]

    # Partial alias matching (e.g., "강원도 강릉" -> "강릉")
    for alias, standard in CITY_ALIASES.items():
        if alias in cleaned and len(alias) >= 2:
            return standard

    # Remove province and administrative suffixes
    cleaned = re.sub(r'^(서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|세종특별자치시|경기도|강원특별자치도|강원도|충청북도|충청남도|전라북도|전북특별자치도|전라남도|경상북도|경상남도|제주특별자치도)\s*', '', cleaned)
    cleaned = re.sub(r'특별자치도|특별시|광역시|자치시|시$|군$|구$|도$', '', cleaned).strip()

    return cleaned if cleaned else "제주"


def get_llm_recommendation(date_str, errors_list, is_retry=False):
    """
    Step 1: Request structured travel recommendation from Gemini LLM.
    """
    prompt = f"""
    당신은 여행 전문가입니다. 여행 날짜 '{date_str}'에 가기 좋은 한국의 도시 1곳을 추천해주세요.
    응답은 반드시 아래 JSON 스키마를 엄격히 준수하여 오직 JSON 형식의 텍스트만 출력하세요. 다른 설명은 포함하지 마세요.

    JSON 스키마:
    {{
      "recommended_city": "도시명 (예: 제주, 강릉)",
      "weather": "해당 시기 일반적 날씨 요약",
      "events": ["행사 또는 축제 후보 1~3개"],
      "reason": "추천 근거 2~4문장"
    }}
    """

    if is_retry:
        prompt += "\n주의: 이전 응답의 JSON 파싱에 실패했습니다. 규칙에 맞춰 정확한 JSON만 반환하세요."

    try:
        # Generate JSON content with forced MIME type and model fallback
        raw_text = call_gemini(prompt, is_json=True, temperature=0.7)

        # Use robust JSON parser
        raw_data = safe_parse_json(raw_text)

        # Strict schema validation
        validated_data = validate_recommendation_schema(raw_data, errors_list)

        # Advanced City name normalization
        recommended_city = normalize_city_name(validated_data["recommended_city"])
        validated_data["recommended_city"] = recommended_city

        return validated_data

    except Exception as exc:
        if not is_retry:
            print("  [경고] LLM JSON 파싱 실패. 1회 재시도합니다...")
            return get_llm_recommendation(date_str, errors_list, is_retry=True)

        error_record = {
            "step": "llm_recommendation",
            "type": "PARSE_ERROR",
            "message": f"JSON 파싱 최종 실패: {exc}"
        }
        errors_list.append(error_record)
        return {
            "recommended_city": "제주",
            "weather": "날씨 정보 파싱 실패",
            "events": [],
            "reason": "기본 추천 도시로 대체되었습니다."
        }


# ==========================================
# Place Search Provider Abstraction Layer
# ==========================================

class PlaceSearchProvider(ABC):
    @abstractmethod
    def search_places(self, city: str, errors_list: list) -> list:
        pass


class KakaoPlaceSearchProvider(PlaceSearchProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://dapi.kakao.com/v2/local/search/keyword.json"

    def search_places(self, city: str, errors_list: list) -> list:
        headers = {"Authorization": f"KakaoAK {self.api_key}"}
        # Multi-query fallback strategy
        search_queries = [f"{city} 맛집", f"{city} 식당", f"{city} 카페"]

        for query in search_queries:
            params = {"query": query, "size": 5}
            try:
                res = requests.get(self.base_url, headers=headers, params=params, timeout=5)

                if res.status_code in [401, 403]:
                    print(f"  - 오류: 지도 API 인증 실패({res.status_code}). 키/권한 설정을 확인하세요.")
                    errors_list.append({
                        "step": "place_search",
                        "type": "AUTH_ERROR",
                        "message": f"Kakao HTTP {res.status_code}"
                    })
                    return []

                res.raise_for_status()
                result = res.json()
                documents = result.get("documents", [])

                if documents:
                    places = []
                    for doc in documents:
                        places.append({
                            "name": doc.get("place_name", ""),
                            "address": doc.get("road_address_name") or doc.get("address_name", ""),
                            "category": doc.get("category_name", ""),
                            "url": doc.get("place_url", ""),
                            "x": doc.get("x", ""),
                            "y": doc.get("y", "")
                        })
                    print(f"  - 맛집 {len(places)}곳 검색 완료 (쿼리: '{query}')")
                    return places

            except Exception as exc:
                print(f"  - 지도 API 호출 중 오류 발생 ('{query}'): {exc}")
                errors_list.append({
                    "step": "place_search",
                    "type": "NETWORK_OR_API_ERROR",
                    "message": f"Query '{query}' failed: {exc}"
                })

        print("  - 검색 결과 0건 (데이터 없음으로 진행)")
        errors_list.append({
            "step": "place_search",
            "type": "EMPTY_RESULT",
            "message": f"0 results for city={city}"
        })
        return []


def get_place_search_provider() -> PlaceSearchProvider:
    provider_name = os.getenv("PLACE_SEARCH_PROVIDER", "kakao").lower()
    if provider_name == "kakao":
        return KakaoPlaceSearchProvider(api_key=KAKAO_REST_API_KEY)
    return KakaoPlaceSearchProvider(api_key=KAKAO_REST_API_KEY)


def generate_final_report(date_str, rec_data, places, errors_list):
    """
    Step 3: Generate rich Markdown travel report using LLM.
    """
    places_str = json.dumps(places, ensure_ascii=False, indent=2) if places else "데이터 없음 (장소 검색 결과 0건)"
    errors_str = json.dumps(errors_list, ensure_ascii=False, indent=2) if errors_list else "없음"

    prompt = f"""
    당신은 여행 리포트 작성가입니다. 아래 제공된 정보로 여행 리포트를 Markdown 형식으로 작성해주세요.

    [기본 정보]
    - 여행 날짜: {date_str}
    - 추천 지역: {rec_data.get('recommended_city')}
    - 추천 이유: {rec_data.get('reason')}
    - 날씨 요약: {rec_data.get('weather')}
    - 행사/축제: {', '.join(rec_data.get('events', []))}
    - 맛집 정보: {places_str}
    - 발생한 오류: {errors_str}

    [작성 규칙]
    - 마크다운 헤더(#, ##)를 활용하여 정돈된 문서로 만드세요.
    - 맛집 정보가 '데이터 없음'이거나 빈 배열이면 맛집 섹션에 "데이터 없음 (장소 검색 결과 0건)"으로 강조 표기하고, 인근 대표 향토음식이나 전통시장을 대안으로 추천하세요.
    - 오전/오후/저녁으로 나눈 1일 일정 제안 코너를 포함하세요.
    - 오류 내역(errors) 섹션을 마지막에 포함하세요.
    """

    try:
        report_text = call_gemini(prompt, is_json=False)
        return report_text
    except Exception as exc:
        errors_list.append({
            "step": "report_generation",
            "type": "LLM_ERROR",
            "message": str(exc)
        })
        
        # Local fallback markdown generator
        fallback_md = []
        fallback_md.append(f"# ✈️ {date_str} 여행 계획 리포트 (예비 생성)")
        fallback_md.append(f"\n> **안내**: LLM을 통한 리포트 생성에 실패하여 로컬 데이터를 기반으로 리포트를 긴급 생성했습니다. (오류: {exc})\n")
        
        city = rec_data.get('recommended_city', '제주')
        reason = rec_data.get('reason', '기본 추천 도시로 대체되었습니다.')
        weather = rec_data.get('weather', '날씨 정보 파싱 실패')
        events = rec_data.get('events', [])
        
        fallback_md.append(f"## 📍 추천 여행지: {city}")
        fallback_md.append(f"- **추천 이유**: {reason}")
        fallback_md.append(f"- **날씨 요약**: {weather}")
        if events:
            fallback_md.append(f"- **주요 행사 및 축제**: {', '.join(events)}")
        fallback_md.append("")
        
        fallback_md.append("## 🍴 추천 맛집 및 장소")
        if places:
            for idx, p in enumerate(places, 1):
                name = p.get("name", "이름 없음")
                address = p.get("address", "주소 정보 없음")
                category = p.get("category", "")
                url = p.get("url", "")
                
                place_line = f"{idx}. **{name}**"
                if category:
                    place_line += f" ({category.split(' > ')[-1]})"
                fallback_md.append(place_line)
                fallback_md.append(f"   - 주소: {address}")
                if url:
                    fallback_md.append(f"   - [Kakao Map 바로가기]({url})")
        else:
            fallback_md.append("> **데이터 없음 (장소 검색 결과 0건)**")
            fallback_md.append("인근의 대표적인 전통시장이나 향토 음식점(예: 향토시장, 전통 5일장)을 대안으로 추천해 드립니다.")
        fallback_md.append("")
        
        # 1-day itinerary suggestion
        fallback_md.append("## 📅 제안 일정 (오전/오후/저녁)")
        fallback_md.append(f"- **오전 (09:00 - 12:00)**: {city} 도착 및 대표 관광 명소 탐방")
        if places:
            fallback_md.append(f"- **오후 (12:00 - 18:00)**: 맛집 `{places[0].get('name')}`에서 맛있는 식사 및 주변 카페/거리 투어")
        else:
            fallback_md.append(f"- **오후 (12:00 - 18:00)**: 현지 음식점에서 점심 식사 후 주변 관광지 방문")
        if len(places) > 1:
            fallback_md.append(f"- **저녁 (18:00 - 21:00)**: `{places[1].get('name')}`에서 저녁 식사 및 대표 야경 감상")
        else:
            fallback_md.append(f"- **저녁 (18:00 - 21:00)**: 저녁 식사 후 숙소 이동 및 휴식")
        fallback_md.append("")
        
        # Errors section
        fallback_md.append("## ⚠️ 발생한 오류 요약 (Errors Summary)")
        if errors_list:
            for err in errors_list:
                fallback_md.append(f"- **{err.get('step', 'N/A')}** ({err.get('type', 'N/A')}): {err.get('message', 'N/A')}")
        else:
            fallback_md.append("- 발생한 오류가 없습니다.")
            
        return "\n".join(fallback_md)


def sanitize_sensitive_data(text: str) -> str:
    """
    Ensure no API keys or sensitive tokens leak into saved files.
    """
    if not text:
        return text
    sanitized = text
    if GEMINI_API_KEY:
        sanitized = sanitized.replace(GEMINI_API_KEY, "[PROTECTED_GEMINI_KEY]")
    if KAKAO_REST_API_KEY:
        sanitized = sanitized.replace(KAKAO_REST_API_KEY, "[PROTECTED_KAKAO_KEY]")
    sanitized = re.sub(r'AIzaSy[A-Za-z0-9_-]{33}', '[PROTECTED_API_KEY]', sanitized)
    sanitized = re.sub(r'KakaoAK\s+[0-9a-fA-F]{32}', 'KakaoAK [PROTECTED_KEY]', sanitized)
    return sanitized


def append_errors_history(date_str: str, errors: list):
    """
    Persist error history for long-term monitoring and debugging.
    """
    if not errors:
        return
    try:
        history = []
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
    Check if the markdown report doesn't exist, is empty, or represents a failed generation attempt.
    """
    if not os.path.exists(md_path) or os.path.getsize(md_path) == 0:
        return True
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read(1024)  # Read the first 1KB
            if "리포트 생성 실패" in content or "오류가 발생했습니다" in content or "예비 생성" in content:
                return True
    except Exception:
        return True
    return False


def append_error_md(errors: list, date_str: str = None):
    """
    Append error logs in Markdown format to error/error.md.
    """
    if not errors:
        return
    try:
        os.makedirs(ERROR_DIR, exist_ok=True)
        write_header = not os.path.exists(ERROR_MD_PATH) or os.path.getsize(ERROR_MD_PATH) == 0

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        md_lines = []
        if write_header:
            md_lines.append("# 오류 기록 (Error History Log)")
            md_lines.append("\n이 파일은 프로그램 실행 중 발생한 오류들을 누적 기록하는 파일입니다.\n")
        
        if date_str:
            md_lines.append(f"## [{timestamp}] 여행 날짜: {date_str}")
        else:
            md_lines.append(f"## [{timestamp}] 시스템/초기화 오류")
            
        for err in errors:
            step = err.get("step", "N/A")
            err_type = err.get("type", "N/A")
            message = err.get("message", "N/A")
            # Sanitize sensitive data in error messages
            message = sanitize_sensitive_data(message)
            md_lines.append(f"- **단계 (Step)**: `{step}`")
            md_lines.append(f"  - **오류 유형 (Type)**: `{err_type}`")
            md_lines.append(f"  - **오류 메시지 (Message)**: {message}")
        
        md_lines.append("") # Empty line separator
        
        output_content = "\n".join(md_lines) + "\n"
        if not write_header:
            output_content = "\n" + output_content
            
        with open(ERROR_MD_PATH, "a", encoding="utf-8") as f:
            f.write(output_content)
    except Exception as exc:
        print(f"[WARNING] error.md 기록 실패: {exc}", file=sys.stderr)


def main():
    date_str, use_cache = parse_arguments()
    errors_list = []

    os.makedirs(RESULTS_DIR, exist_ok=True)
    json_path = os.path.join(RESULTS_DIR, f"{date_str}_raw.json")
    md_path = os.path.join(RESULTS_DIR, f"{date_str}_travel_plan.md")

    # Cache check (Bonus feature: Cost and speed optimization)
    if use_cache and os.path.exists(json_path):
        print(f"[CACHE] 기존 캐시 데이터({json_path})를 발견하여 API 호출을 건너뛰고 재사용합니다.")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                cached_raw = json.load(f)
            rec_data = cached_raw.get("recommendation", {})
            places = cached_raw.get("places", [])
            errors_list = cached_raw.get("errors", [])
            print(f"  - 캐시 로드 완료 (추천 도시: \"{rec_data.get('recommended_city')}\", 맛집: {len(places)}곳)")

            # Re-generate report if md is missing or was a failed attempt
            if is_failed_report(md_path):
                print(f"[3/3] 최종 리포트 재생성/복원 중(LLM)...")
                orig_err_count = len(errors_list)
                report_md = generate_final_report(date_str, rec_data, places, errors_list)
                with open(md_path, "w", encoding="utf-8") as file_obj:
                    file_obj.write(sanitize_sensitive_data(report_md))
                if len(errors_list) > orig_err_count:
                    new_errors = errors_list[orig_err_count:]
                    append_error_md(new_errors, date_str)

            print(f"\n완료 (캐시 활용)! {md_path} 및 {json_path} 를 확인하세요.")
            return
        except Exception as exc:
            print(f"  [경고] 캐시 로드 실패({exc}). 일반 실행으로 전환합니다.")

    print(f"[1/3] 1차 추천 생성 중(LLM)...")
    rec_data = get_llm_recommendation(date_str, errors_list)
    city = rec_data.get("recommended_city", "제주")
    print(f"  - recommended_city: \"{city}\"")

    print(f"[2/3] 맛집 검색 중(지도/장소 API)...")
    place_provider = get_place_search_provider()
    places = place_provider.search_places(city, errors_list)

    print(f"[3/3] 최종 리포트 생성 중(LLM)...")
    report_md = generate_final_report(date_str, rec_data, places, errors_list)
    print("  - 리포트 생성 완료")

    raw_data = {
        "date": date_str,
        "recommendation": rec_data,
        "places": places,
        "errors": errors_list
    }

    # Sanitize and write files
    sanitized_json = sanitize_sensitive_data(json.dumps(raw_data, ensure_ascii=False, indent=2))
    sanitized_md = sanitize_sensitive_data(report_md)

    with open(json_path, "w", encoding="utf-8") as file_obj:
        file_obj.write(sanitized_json)

    with open(md_path, "w", encoding="utf-8") as file_obj:
        file_obj.write(sanitized_md)

    # Append errors to persistent log if any
    append_errors_history(date_str, errors_list)
    append_error_md(errors_list, date_str)

    print(f"\n완료! {md_path} 및 {json_path} 를 확인하세요.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        err_msg = f"프로그램 실행 중 예기치 못한 에러가 발생했습니다: {e}"
        print(f"[FATAL] {err_msg}", file=sys.stderr)
        append_error_md([{"step": "main_execution", "type": "UNHANDLED_EXCEPTION", "message": err_msg}])
        sys.exit(1)
