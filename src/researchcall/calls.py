from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .questionnaire import build_task, result_schema


TERMINAL_STATUSES = {
    "COMPLETED",
    "FAILED",
    "NO_ANSWER",
    "DECLINED",
    "CANCELED",
    "CANCELLED",
    "VOICEMAIL",
    "BUSY",
    "EXPIRED",
}

OBSERVED_SETUP_SECONDS = 40
ProgressCallback = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class CallOutcome:
    status: str
    run_id: str | None
    structured_result: dict[str, Any] | None
    detail: dict[str, Any]
    transcript: str | None = None


class FixtureCallClient:
    """Offline client. It never imports an SDK and never opens a network connection."""

    def __init__(self, patterns: list[dict[str, Any]]) -> None:
        if not patterns:
            raise ValueError("Fixture outcome list must not be empty")
        self.patterns = patterns

    @classmethod
    def from_file(cls, path: str | Path) -> "FixtureCallClient":
        patterns = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(patterns, list) or not all(isinstance(item, dict) for item in patterns):
            raise ValueError("Fixture outcomes must be a JSON array of objects")
        return cls(patterns)

    def call(
        self,
        sample: dict[str, Any],
        questionnaire: dict[str, Any],
        idempotency_key: str,
    ) -> CallOutcome:
        del idempotency_key
        pattern = self.patterns[(int(sample["sample_id"]) - 1) % len(self.patterns)]
        status = str(pattern.get("status", "FAILED")).upper()
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"Fixture uses unsupported terminal status: {status}")

        structured: dict[str, Any] | None = None
        if pattern.get("structured", status == "COMPLETED"):
            answers_in = pattern.get("answers", {})
            if not isinstance(answers_in, dict):
                raise ValueError("Fixture answers must be an object")
            answers = {
                question["id"]: answers_in.get(question["id"])
                for question in questionnaire["questions"]
            }
            raw_answers_in = pattern.get("raw_answers")
            if not isinstance(raw_answers_in, dict):
                raise ValueError("Fixture raw_answers must be an object")
            raw_answers = {
                question["id"]: raw_answers_in.get(question["id"])
                for question in questionnaire["questions"]
            }
            asked_verbatim = bool(pattern.get("asked_verbatim", True))
            consent = str(pattern.get("consent", "granted"))
            spoken: dict[str, str | None] = {}
            changed = False
            for question in questionnaire["questions"]:
                question_id = question["id"]
                if answers[question_id] is None:
                    spoken[question_id] = None
                elif asked_verbatim or changed:
                    spoken[question_id] = question["wording"]
                else:
                    spoken[question_id] = "Fixture paraphrase: " + question["wording"]
                    changed = True
            consent_wording: str | None
            if consent == "not_obtained":
                consent_wording = None
            elif asked_verbatim:
                consent_wording = questionnaire["consent_text"]
            else:
                consent_wording = "Fixture paraphrase: " + questionnaire["consent_text"]
            structured = {
                "consent": consent,
                "withdrawal_requested": bool(pattern.get("withdrawal_requested", False)),
                "asked_verbatim": asked_verbatim,
                "spoken_consent_wording": consent_wording,
                "spoken_wording": spoken,
                "answers": answers,
                "raw_answers": raw_answers,
            }
        return CallOutcome(
            status=status,
            run_id=f"fixture-{sample['sample_id']}",
            structured_result=structured,
            detail={"transport": "fixture", "pattern": (int(sample["sample_id"]) - 1) % len(self.patterns)},
        )


class LiveCallClient:
    """Minimal, deliberately serial CALL-E Developer API adapter.

    This path is present for later operator validation. It is never selected unless the
    CLI receives all explicit live-call gates.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        first_poll_seconds: float = 60.0,
        poll_seconds: float = 10.0,
        poll_timeout_seconds: float = 900.0,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("CALLE_API_KEY is required for live mode")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.first_poll_seconds = first_poll_seconds
        self.poll_seconds = poll_seconds
        self.poll_timeout_seconds = poll_timeout_seconds
        self.progress_callback = progress_callback

    @classmethod
    def from_environment(
        cls, progress_callback: ProgressCallback | None = None
    ) -> "LiveCallClient":
        return cls(
            api_key=os.environ.get("CALLE_API_KEY", ""),
            base_url=os.environ.get("CALLE_BASE_URL", "https://api.heycall-e.com"),
            progress_callback=progress_callback,
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                value = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"CALL-E API returned HTTP {error.code}") from error
        if not isinstance(value, dict):
            raise RuntimeError("CALL-E API returned a non-object response")
        return value

    @staticmethod
    def _status(value: dict[str, Any]) -> str | None:
        containers = [value]
        if isinstance(value.get("result"), dict):
            containers.append(value["result"])
        for container in containers:
            status = container.get("status") or container.get("call_status")
            if isinstance(status, str):
                return status.upper()
        return None

    @staticmethod
    def _activity(value: dict[str, Any]) -> list[Any]:
        if isinstance(value.get("activity"), list):
            return value["activity"]
        result = value.get("result")
        if isinstance(result, dict) and isinstance(result.get("activity"), list):
            return result["activity"]
        return []

    @classmethod
    def _activity_progress(cls, value: dict[str, Any]) -> dict[str, Any] | None:
        activity = cls._activity(value)
        if not activity:
            return None
        latest = activity[-1]
        timestamp = None
        if isinstance(latest, dict):
            for key in ("timestamp", "created_at", "time"):
                if isinstance(latest.get(key), str):
                    timestamp = latest[key]
                    break
        return {
            "activity_events": len(activity),
            "latest_activity_at": timestamp,
        }

    @staticmethod
    def _transcript(value: dict[str, Any]) -> str | None:
        result = value.get("result")
        if isinstance(result, dict) and isinstance(result.get("transcript"), str):
            return result["transcript"]
        return None

    @staticmethod
    def _structured_result(value: dict[str, Any]) -> dict[str, Any] | None:
        containers = [value]
        if isinstance(value.get("result"), dict):
            containers.insert(0, value["result"])
        for container in containers:
            for key in ("structured_result", "structuredResult"):
                if isinstance(container.get(key), dict):
                    return container[key]
            recipients = container.get("recipients")
            if (
                isinstance(recipients, list)
                and recipients
                and isinstance(recipients[0], dict)
            ):
                recipient = recipients[0]
                for key in ("structured_result", "structuredResult"):
                    if isinstance(recipient.get(key), dict):
                        return recipient[key]
        return None

    def call(
        self,
        sample: dict[str, Any],
        questionnaire: dict[str, Any],
        idempotency_key: str,
    ) -> CallOutcome:
        payload = {
            "task": build_task(questionnaire),
            "recipients": [
                {
                    "phones": [sample["phone_e164"]],
                    "region": "DE",
                    "locale": questionnaire["language"],
                }
            ],
            "result_schema": {
                "type": "object",
                "properties": {"completed_count": {"type": "integer"}},
            },
            "recipient_result_schema": result_schema(questionnaire),
            "metadata": {"researchcall_sample_id": str(sample["sample_id"])},
        }
        created = self._request(
            "POST", "/v1/calls", payload=payload, idempotency_key=idempotency_key
        )
        run_id = created.get("id") or created.get("call_id") or created.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise RuntimeError("CALL-E create response did not include a call id")

        deadline = time.monotonic() + self.poll_timeout_seconds
        time.sleep(self.first_poll_seconds)
        latest = created
        activity_fingerprint: str | None = None
        while True:
            latest = self._request("GET", f"/v1/calls/{run_id}")
            activity = self._activity(latest)
            new_fingerprint = json.dumps(
                activity, ensure_ascii=False, sort_keys=True, default=str
            )
            progress = self._activity_progress(latest)
            if (
                progress is not None
                and new_fingerprint != activity_fingerprint
                and self.progress_callback is not None
            ):
                self.progress_callback(progress)
            activity_fingerprint = new_fingerprint
            status = self._status(latest)
            if status in TERMINAL_STATUSES:
                transcript = self._transcript(latest)
                detail: dict[str, Any] = {
                    "transport": "live-api",
                    "progress_source": "activity",
                    "transcript_location": "result.transcript",
                }
                if progress is not None:
                    detail.update(progress)
                return CallOutcome(
                    status=status,
                    run_id=run_id,
                    structured_result=self._structured_result(latest),
                    detail=detail,
                    transcript=transcript,
                )
            if time.monotonic() >= deadline:
                raise TimeoutError("CALL-E status polling exceeded the configured timeout")
            time.sleep(self.poll_seconds)
