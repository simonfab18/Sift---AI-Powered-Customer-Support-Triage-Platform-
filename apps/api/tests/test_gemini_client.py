import httpx

from app.integrations.gemini.client import extract_gemini_output_text, parse_retry_after_seconds


def test_extract_gemini_output_text_from_output_text() -> None:
    assert extract_gemini_output_text({"output_text": "{}"}) == "{}"


def test_extract_gemini_output_text_from_model_output_step() -> None:
    raw_output = {
        "steps": [
            {"type": "other", "content": [{"text": "ignore me"}]},
            {"type": "model_output", "content": [{"type": "text", "text": '{"priority":"high"}'}]},
        ]
    }

    assert extract_gemini_output_text(raw_output) == '{"priority":"high"}'


def test_extract_gemini_output_text_returns_none_when_missing() -> None:
    assert extract_gemini_output_text({"steps": []}) is None

def test_parse_retry_after_seconds_prefers_header() -> None:
    response = httpx.Response(429, headers={"retry-after": "42"}, text="retry in 12s")

    assert parse_retry_after_seconds(response) == 42


def test_parse_retry_after_seconds_from_gemini_message() -> None:
    response = httpx.Response(429, text="Please retry in 57.798570996s.")

    assert parse_retry_after_seconds(response) == 58
