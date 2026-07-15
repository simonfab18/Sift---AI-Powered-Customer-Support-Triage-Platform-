"""Run a real Gemini triage smoke check with synthetic pilot emails.

This script calls the same Gemini prompt/schema path used by ticket triage, but it does
not create tickets or write to the database. It is intended for staging/pilot provider
verification after Gemini quota or billing changes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from app.integrations.gemini.client import GeminiQuotaExceededError, classify_ticket_with_gemini
from app.integrations.gemini.prompts import build_triage_prompt


@dataclass(frozen=True)
class SmokeCase:
    name: str
    subject: str
    body: str
    expected_category: str
    expected_priorities: tuple[str, ...]


SMOKE_CASES = [
    SmokeCase(
        name="refund_billing_urgent",
        subject="Charged twice and I need a refund today",
        body=(
            "Hi support, my card was charged twice for order COCO-1001. "
            "This overdrew my account and I need the duplicate charge refunded today."
        ),
        expected_category="refund",
        expected_priorities=("high", "critical"),
    ),
    SmokeCase(
        name="damaged_item",
        subject="My blender arrived broken",
        body=(
            "The glass jar on my blender arrived cracked and the box was dented. "
            "Please send a replacement or tell me how to return it."
        ),
        expected_category="damaged_item",
        expected_priorities=("high",),
    ),
    SmokeCase(
        name="account_access",
        subject="I cannot sign in to my account",
        body=(
            "I am locked out of my account and password reset emails are not arriving. "
            "I need access because I have an open order."
        ),
        expected_category="account_access",
        expected_priorities=("medium", "high"),
    ),
    SmokeCase(
        name="product_question",
        subject="Do you sell this shirt in blue?",
        body=(
            "Hello, I am interested in the cotton travel shirt. "
            "Do you have it in blue and is it available in size medium?"
        ),
        expected_category="product_question",
        expected_priorities=("low", "medium"),
    ),
]


def build_case_prompt(case: SmokeCase) -> str:
    return build_triage_prompt(
        customer_name="Pilot Smoke Tester",
        customer_email=f"{case.name}@example.test",
        subject=case.subject,
        message=case.body,
    )


def case_result(case: SmokeCase, output: Any) -> dict[str, Any]:
    category = output.category.value
    priority = output.priority.value
    passed = category == case.expected_category and priority in case.expected_priorities
    return {
        "name": case.name,
        "passed": passed,
        "expected_category": case.expected_category,
        "actual_category": category,
        "expected_priorities": list(case.expected_priorities),
        "actual_priority": priority,
        "sentiment": output.sentiment.value,
        "confidence_score": output.confidence_score,
        "requires_human_review": output.requires_human_review,
        "summary": output.summary,
        "reasoning": output.reasoning,
    }


async def run_smoke(stop_after_first_provider_error: bool) -> tuple[int, dict[str, Any]]:
    results: list[dict[str, Any]] = []
    provider_error: str | None = None
    provider_error_type: str | None = None
    retry_after_seconds: int | None = None

    for case in SMOKE_CASES:
        try:
            output, _raw = await classify_ticket_with_gemini(build_case_prompt(case))
            results.append(case_result(case, output))
        except GeminiQuotaExceededError as exc:
            provider_error = str(exc)
            provider_error_type = "quota_or_credits"
            retry_after_seconds = exc.retry_after_seconds
            results.append({"name": case.name, "passed": False, "blocked": True, "error": str(exc)})
            if stop_after_first_provider_error:
                break
        except HTTPException as exc:
            provider_error = str(exc.detail)
            provider_error_type = "provider_http_error"
            results.append({"name": case.name, "passed": False, "blocked": True, "error": str(exc.detail)})
            if stop_after_first_provider_error:
                break

    attempted = len(results)
    passed = sum(1 for item in results if item.get("passed") is True)
    blocked = any(item.get("blocked") for item in results)
    status = "passed" if attempted == len(SMOKE_CASES) and passed == len(SMOKE_CASES) else "blocked" if blocked else "failed"
    payload: dict[str, Any] = {
        "status": status,
        "attempted": attempted,
        "passed": passed,
        "total": len(SMOKE_CASES),
        "provider_error_type": provider_error_type,
        "provider_error": provider_error,
        "retry_after_seconds": retry_after_seconds,
        "results": results,
    }
    return (0 if status == "passed" else 2 if status == "blocked" else 1), payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the real Gemini pilot triage smoke set.")
    parser.add_argument(
        "--continue-after-provider-error",
        action="store_true",
        help="Keep trying all cases after a provider quota/HTTP error. Defaults to stopping early to save quota.",
    )
    args = parser.parse_args()

    exit_code, payload = asyncio.run(
        run_smoke(stop_after_first_provider_error=not args.continue_after_provider_error)
    )
    print(json.dumps(payload, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())


