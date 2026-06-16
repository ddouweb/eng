import os
from urllib.parse import quote

import requests

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
PUBLIC_API_BASE = os.environ.get("PUBLIC_API_URL", API_BASE)
_TIMEOUT = 30
_token: str | None = None


def set_token(token: str | None):
    global _token
    _token = token


def get_token() -> str | None:
    return _token


def _url(path: str) -> str:
    return f"{API_BASE}{path}"


def _request(method: str, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", _TIMEOUT)
    headers = kwargs.pop("headers", {})
    if _token and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {_token}"
    kwargs["headers"] = headers
    try:
        return requests.request(method, url, **kwargs)
    except requests.ConnectionError:
        return _error_response(503, "无法连接到服务器，请检查后端是否启动")
    except requests.Timeout:
        return _error_response(504, "请求超时，请稍后重试")


class _FakeResp:
    def __init__(self, code: int, msg: str):
        self.status_code = code
        self._body = {"code": code, "message": msg, "data": None}

    def json(self):
        return self._body


def _error_response(code: int, msg: str) -> _FakeResp:
    return _FakeResp(code, msg)


def _handle(resp: requests.Response) -> dict:
    if resp.status_code >= 400:
        try:
            body = resp.json()
            return {"code": resp.status_code, "message": body.get("message", resp.text), "data": None}
        except Exception:
            return {"code": resp.status_code, "message": resp.text, "data": None}
    try:
        return resp.json()
    except Exception:
        return {"code": 500, "message": "服务器返回非 JSON 响应", "data": None}


# ── Units ──────────────────────────────────────────────

def list_units(page: int = 1, page_size: int = 20) -> dict:
    return _handle(_request("GET", _url("/units"), params={"page": page, "page_size": page_size}))


def get_unit(unit_id: int) -> dict:
    return _handle(_request("GET", _url(f"/units/{unit_id}")))


def create_unit(title: str, sequence: int) -> dict:
    return _handle(_request("POST", _url("/units"), json={"title": title, "sequence": sequence}))


def delete_unit(unit_id: int) -> dict:
    return _handle(_request("DELETE", _url(f"/units/{unit_id}")))


# ── Words ──────────────────────────────────────────────

def list_words(unit_id: int, page: int = 1, page_size: int = 50, word_type: str | None = None) -> dict:
    params = {"page": page, "page_size": page_size}
    if word_type:
        params["type"] = word_type
    return _handle(_request("GET", _url(f"/words/units/{unit_id}/words"), params=params))


def batch_create_words(unit_id: int, words: list[dict]) -> dict:
    return _handle(_request("POST", _url(f"/words/units/{unit_id}/words"), json={"words": words}))


def update_word(word_id: int, **data) -> dict:
    return _handle(_request("PUT", _url(f"/words/{word_id}"), json=data))


def delete_word(word_id: int) -> dict:
    return _handle(_request("DELETE", _url(f"/words/{word_id}")))


def set_tags(word_id: int, tags: list[str]) -> dict:
    return _handle(_request("POST", _url(f"/words/{word_id}/tags"), json={"tags": tags}))


def remove_tag(word_id: int, tag: str) -> dict:
    return _handle(_request("DELETE", _url(f"/words/{word_id}/tags/{tag}")))


# ── Practice ───────────────────────────────────────────

def start_practice(member_id: int, mode: str, unit_ids: list[int], count: int = 10) -> dict:
    return _handle(_request("POST", _url("/practice/start"), json={
        "member_id": member_id, "mode": mode, "unit_ids": unit_ids, "count": count,
    }))


def submit_answer(session_id: int, word_id: int, is_correct: bool, user_answer: str | None = None) -> dict:
    return _handle(_request("POST", _url(f"/practice/{session_id}/submit"), json={
        "word_id": word_id, "is_correct": is_correct, "user_answer": user_answer,
    }))


def finish_practice(session_id: int) -> dict:
    return _handle(_request("POST", _url(f"/practice/{session_id}/finish")))


def get_practice_session(session_id: int) -> dict:
    return _handle(_request("GET", _url(f"/practice/{session_id}")))


# ── Plans ──────────────────────────────────────────────

def create_plan(name: str, daily_goal: int, unit_ids: list[int], deadline: str | None = None) -> dict:
    body: dict = {"name": name, "daily_goal": daily_goal, "unit_ids": unit_ids}
    if deadline:
        body["deadline"] = deadline
    return _handle(_request("POST", _url("/plans"), json=body))


def list_plans(status: str | None = None) -> dict:
    params = {}
    if status:
        params["status"] = status
    return _handle(_request("GET", _url("/plans"), params=params))


def get_plan(plan_id: int) -> dict:
    return _handle(_request("GET", _url(f"/plans/{plan_id}")))


def update_task(plan_id: int, task_id: int, completed_new: int, completed_review: int) -> dict:
    return _handle(_request("PUT", _url(f"/plans/{plan_id}/tasks/{task_id}"), json={
        "completed_new": completed_new, "completed_review": completed_review,
    }))


def pause_plan(plan_id: int) -> dict:
    return _handle(_request("POST", _url(f"/plans/{plan_id}/pause")))


def resume_plan(plan_id: int) -> dict:
    return _handle(_request("POST", _url(f"/plans/{plan_id}/resume")))


# ── Stats ──────────────────────────────────────────────

def get_stats_overview(member_id: int = 1) -> dict:
    return _handle(_request("GET", _url("/stats/overview"), params={"member_id": member_id}))


def get_stats_unit(unit_id: int, member_id: int = 1) -> dict:
    return _handle(_request("GET", _url(f"/stats/units/{unit_id}"), params={"member_id": member_id}))


def get_stats_trend(days: int = 30, member_id: int = 1) -> dict:
    return _handle(_request("GET", _url("/stats/trend"), params={"days": days, "member_id": member_id}))


def get_leaderboard() -> dict:
    return _handle(_request("GET", _url("/leaderboard")))


# ── AI ──────────────────────────────────────────────────

def generate_dialogue(unit_ids: list[int], scenario: str = "日常对话") -> dict:
    body: dict = {"unit_ids": unit_ids, "scenario": scenario}
    return _handle(_request("POST", _url("/ai/dialogue"), json=body))


def generate_exercise(unit_ids: list[int], mode: str = "choice") -> dict:
    body: dict = {"unit_ids": unit_ids, "mode": mode}
    return _handle(_request("POST", _url("/ai/exercise"), json=body))


def parse_words(text: str) -> dict:
    body: dict = {"text": text}
    return _handle(_request("POST", _url("/ai/parse-words"), json=body))


# ── TTS ─────────────────────────────────────────────────

def get_tts_url(text: str, lang: str = "en") -> str:
    return f"{PUBLIC_API_BASE}/tts/generate?text={quote(text)}&lang={lang}"


# ── Auth ─────────────────────────────────────────────────

def login(username: str, password: str) -> dict:
    resp = _request("POST", _url("/auth/login"), json={"username": username, "password": password})
    data = _handle(resp)
    if data["code"] == 200:
        set_token(data["data"]["token"])
    return data
