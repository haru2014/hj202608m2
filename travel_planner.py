import argparse
import json
import os
import re
import sys

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(PROJECT_DIR, "results")
ENV_PATH = os.path.join(PROJECT_DIR, ".env")


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
    print("[ERROR] API 키가 설정되지 않았습니다.")
    print(".env 파일에 GEMINI_API_KEY와 KAKAO_REST_API_KEY가 바르게 입력되었는지 확인하세요.")
    sys.exit(1)

gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def parse_arguments():
    parser = argparse.ArgumentParser(description="국내 여행지 및 맛집 추천 프로그램")
    parser.add_argument("--date", required=True, help="여행 날짜 (YYYY-MM-DD)")
    args = parser.parse_args()

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        print("[ERROR] 올바르지 않은 날짜 형식입니다. 'YYYY-MM-DD' 형식으로 입력해주세요.")
        parser.print_help()
        sys.exit(1)

    return args.date


def extract_json_text(raw_text):
    text = (raw_text or "").strip()
    if not text:
        return "{}"

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE)

    return text.strip()


def get_llm_recommendation(date_str, errors_list, is_retry=False):
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
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )

        cleaned_text = extract_json_text(response.text)
        data = json.loads(cleaned_text)

        if not isinstance(data, dict):
            raise ValueError("LLM 응답이 JSON 객체가 아닙니다.")

        return {
            "recommended_city": data.get("recommended_city", "제주"),
            "weather": data.get("weather", "날씨 정보 없음"),
            "events": data.get("events", []) if isinstance(data.get("events", []), list) else [],
            "reason": data.get("reason", "추천 근거를 확인할 수 없습니다.")
        }

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


def search_places(city, errors_list):
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    params = {"query": f"{city} 맛집", "size": 5}

    places = []

    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)

        if res.status_code in [401, 403]:
            print(f"  - 오류: 지도 API 인증 실패({res.status_code}). 키/권한 설정을 확인하세요.")
            errors_list.append({
                "step": "place_search",
                "type": "AUTH_ERROR",
                "message": f"HTTP {res.status_code}"
            })
            return []

        res.raise_for_status()
        result = res.json()
        documents = result.get("documents", [])

        if not documents:
            print("  - 검색 결과 0건 (데이터 없음으로 진행)")
            errors_list.append({
                "step": "place_search",
                "type": "EMPTY_RESULT",
                "message": f"0 results for query={city} 맛집"
            })
            return []

        for doc in documents:
            places.append({
                "name": doc.get("place_name", ""),
                "address": doc.get("road_address_name") or doc.get("address_name", ""),
                "category": doc.get("category_name", ""),
                "url": doc.get("place_url", ""),
                "x": doc.get("x", ""),
                "y": doc.get("y", "")
            })

        print(f"  - 맛집 {len(places)}곳 검색 완료")
        return places

    except Exception as exc:
        print(f"  - 지도 API 호출 중 오류 발생: {exc}")
        errors_list.append({
            "step": "place_search",
            "type": "NETWORK_OR_API_ERROR",
            "message": str(exc)
        })
        return []


def generate_final_report(date_str, rec_data, places, errors_list):
    places_str = json.dumps(places, ensure_ascii=False, indent=2) if places else "데이터 없음"
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
    - 맛집 정보가 '데이터 없음'이거나 빈 배열이면 맛집 섹션에 "데이터 없음 (장소 검색 결과 0건)" 표기하세요.
    - 오전/오후/저녁으로 나눈 1일 일정 제안 코너를 포함하세요.
    - 오류 내역(errors) 섹션을 마지막에 포함하세요.
    """

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text
    except Exception as exc:
        errors_list.append({
            "step": "report_generation",
            "type": "LLM_ERROR",
            "message": str(exc)
        })
        return f"# {date_str} 여행 리포트 생성 실패\n\n리포트 생성 중 오류가 발생했습니다: {exc}"


def main():
    date_str = parse_arguments()
    errors_list = []

    os.makedirs(RESULTS_DIR, exist_ok=True)

    print(f"[1/3] 1차 추천 생성 중(LLM)...")
    rec_data = get_llm_recommendation(date_str, errors_list)
    city = rec_data.get("recommended_city", "제주")
    print(f"  - recommended_city: \"{city}\"")

    print(f"[2/3] 맛집 검색 중(지도/장소 API)...")
    places = search_places(city, errors_list)

    print(f"[3/3] 최종 리포트 생성 중(LLM)...")
    report_md = generate_final_report(date_str, rec_data, places, errors_list)
    print("  - 리포트 생성 완료")

    raw_data = {
        "date": date_str,
        "recommendation": rec_data,
        "places": places,
        "errors": errors_list
    }

    json_path = os.path.join(RESULTS_DIR, f"{date_str}_raw.json")
    md_path = os.path.join(RESULTS_DIR, f"{date_str}_travel_plan.md")

    with open(json_path, "w", encoding="utf-8") as file_obj:
        json.dump(raw_data, file_obj, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as file_obj:
        file_obj.write(report_md)

    print(f"\n완료! {md_path} 및 {json_path} 를 확인하세요.")


if __name__ == "__main__":
    main()
