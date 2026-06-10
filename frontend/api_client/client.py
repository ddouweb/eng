import requests

API_BASE = "http://localhost:8000/api/v1"


def _url(path: str) -> str:
    return f"{API_BASE}{path}"


def _handle(resp: requests.Response) -> dict:
    if resp.status_code >= 400:
        try:
            body = resp.json()
            return {"code": resp.status_code, "message": body.get("message", resp.text), "data": None}
        except Exception:
            return {"code": resp.status_code, "message": resp.text, "data": None}
    return resp.json()


# ── Units ──────────────────────────────────────────────

def list_units(page: int = 1, page_size: int = 20) -> dict:
    return _handle(requests.get(_url("/units"), params={"page": page, "page_size": page_size}))


def get_unit(unit_id: int) -> dict:
    return _handle(requests.get(_url(f"/units/{unit_id}")))


def create_unit(title: str, sequence: int, image_url: str | None = None) -> dict:
    return _handle(requests.post(_url("/units"), json={"title": title, "sequence": sequence, "image_url": image_url}))


def delete_unit(unit_id: int) -> dict:
    return _handle(requests.delete(_url(f"/units/{unit_id}")))


# ── Words ──────────────────────────────────────────────

def list_words(unit_id: int, page: int = 1, page_size: int = 50, word_type: str | None = None) -> dict:
    params = {"page": page, "page_size": page_size}
    if word_type:
        params["type"] = word_type
    return _handle(requests.get(_url(f"/words/units/{unit_id}/words"), params=params))


def batch_create_words(unit_id: int, words: list[dict]) -> dict:
    return _handle(requests.post(_url(f"/words/units/{unit_id}/words"), json={"words": words}))


def update_word(word_id: int, **data) -> dict:
    return _handle(requests.put(_url(f"/words/{word_id}"), json=data))


def delete_word(word_id: int) -> dict:
    return _handle(requests.delete(_url(f"/words/{word_id}")))


def set_tags(word_id: int, tags: list[str]) -> dict:
    return _handle(requests.post(_url(f"/words/{word_id}/tags"), json={"tags": tags}))


def remove_tag(word_id: int, tag: str) -> dict:
    return _handle(requests.delete(_url(f"/words/{word_id}/tags/{tag}")))


# ── OCR ────────────────────────────────────────────────

def upload_image(unit_id: int, file_bytes: bytes, filename: str) -> dict:
    return _handle(requests.post(
        _url(f"/units/{unit_id}/upload-image"),
        files={"file": (filename, file_bytes)},
    ))


def get_ocr_result(unit_id: int) -> dict:
    return _handle(requests.get(_url(f"/units/{unit_id}/ocr-result")))


def confirm_ocr(unit_id: int, words: list[dict]) -> dict:
    return _handle(requests.post(_url(f"/units/{unit_id}/confirm-ocr"), json={"words": words}))


# ── Practice ───────────────────────────────────────────

def start_practice(member_id: int, mode: str, unit_ids: list[int], count: int = 10) -> dict:
    return _handle(requests.post(_url("/practice/start"), json={
        "member_id": member_id, "mode": mode, "unit_ids": unit_ids, "count": count,
    }))


def submit_answer(session_id: int, word_id: int, is_correct: bool, user_answer: str | None = None) -> dict:
    return _handle(requests.post(_url(f"/practice/{session_id}/submit"), json={
        "word_id": word_id, "is_correct": is_correct, "user_answer": user_answer,
    }))


def finish_practice(session_id: int) -> dict:
    return _handle(requests.post(_url(f"/practice/{session_id}/finish")))


def get_practice_session(session_id: int) -> dict:
    return _handle(requests.get(_url(f"/practice/{session_id}")))


# ── Plans ──────────────────────────────────────────────

def create_plan(name: str, daily_goal: int, unit_ids: list[int], deadline: str | None = None) -> dict:
    body: dict = {"name": name, "daily_goal": daily_goal, "unit_ids": unit_ids}
    if deadline:
        body["deadline"] = deadline
    return _handle(requests.post(_url("/plans"), json=body))


def list_plans(status: str | None = None) -> dict:
    params = {}
    if status:
        params["status"] = status
    return _handle(requests.get(_url("/plans"), params=params))


def get_plan(plan_id: int) -> dict:
    return _handle(requests.get(_url(f"/plans/{plan_id}")))


def update_task(plan_id: int, task_id: int, completed_new: int, completed_review: int) -> dict:
    return _handle(requests.put(_url(f"/plans/{plan_id}/tasks/{task_id}"), json={
        "completed_new": completed_new, "completed_review": completed_review,
    }))


def pause_plan(plan_id: int) -> dict:
    return _handle(requests.post(_url(f"/plans/{plan_id}/pause")))


def resume_plan(plan_id: int) -> dict:
    return _handle(requests.post(_url(f"/plans/{plan_id}/resume")))


# ── Stats ──────────────────────────────────────────────

def get_stats_overview() -> dict:
    return _handle(requests.get(_url("/stats/overview")))


def get_stats_unit(unit_id: int) -> dict:
    return _handle(requests.get(_url(f"/stats/units/{unit_id}")))


def get_stats_trend(days: int = 30) -> dict:
    return _handle(requests.get(_url("/stats/trend"), params={"days": days}))
