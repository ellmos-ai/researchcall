"""The workbench renders the pipeline — and nothing besides it.

The load-bearing assertions are the negative ones: no control the definitions do
not declare, no locked setting anywhere in the HTML, no phone number in any
response, and no route that could reach the live transport.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from researchcall import forms  # noqa: E402
from researchcall.web.workspace import STATIONS, Workspace  # noqa: E402

try:  # the web surface is an optional extra; the command line needs nothing
    from fastapi.testclient import TestClient

    from researchcall.web.app import create_app

    WEB_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the extra
    WEB_AVAILABLE = False


FORM_ENCODED = {"content-type": "application/x-www-form-urlencoded"}
CONTROL = re.compile(r"<(?:input|select|textarea)[^>]*\sname=\"([^\"]+)\"")
# Any E.164-looking run of digits. Fixtures use +1555…, so a hit means a leak.
PHONE = re.compile(r"\+\d{7,}")

ANSWERS = {
    "question": "Does rural bus frequency shape commuting choice?",
    "hypotheses": "H1 | more departures raise bus use | share of bus trips",
    "items": 'I1 | H1 | dichotomous | "Do you use the bus?"',
    "ethics.instruction": "This is an automated research call from an independent study.",
    "ethics.privacy_text": "Answers are stored pseudonymously and deleted on request.",
    "ethics.number_origin": "public directory",
    "ethics.greeting": "Good afternoon",
    "ethics.closing": "Thank you for your time",
    "sample.source": "frame.csv",
    "sample.size": "9",
    "pretest.instrument_check.syntactic_marker": "Would you say that you, the bus, use often?",
}


@unittest.skipUnless(WEB_AVAILABLE, "the web extra is not installed")
class WorkbenchTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.client = TestClient(create_app(self.directory))
        self.fields = forms.load_fields()
        self.locked = {field.path for field in self.fields if field.locked}

    # --- helpers -----------------------------------------------------------

    def controls(self, html: str) -> set[str]:
        return set(CONTROL.findall(html)) - {"action"}

    def payload(self, station: str, language: str = "en", **overrides: str) -> str:
        pairs: list[tuple[str, str]] = []
        for descriptor in forms.form(self.fields, station, language):
            name = descriptor["name"]
            value = overrides.get(name, ANSWERS.get(name, descriptor["value"]))
            if descriptor["type"] == "bool":
                if value:
                    pairs.append((name, "on"))
            elif descriptor["type"] == "multi":
                pairs.extend((name, str(item)) for item in (value or []))
            elif isinstance(value, list):
                pairs.append((name, "\n".join(str(item) for item in value)))
            else:
                pairs.append((name, "" if value is None else str(value)))
        return urllib.parse.urlencode(pairs)

    def finish(self, station: str, language: str = "en") -> str:
        body = self.payload(station, language) + "&action=complete"
        response = self.client.post(
            f"/station/{station}?lang={language}", content=body, headers=FORM_ENCODED
        )
        self.assertEqual(response.status_code, 200)
        return response.text

    def finish_all(self, language: str = "en") -> None:
        for station in STATIONS:
            text = self.finish(station, language)
            self.assertNotIn("Still missing", text, station)

    # --- what the interface shows -----------------------------------------

    def test_each_station_renders_exactly_its_form_definitions(self) -> None:
        for language in ("en", "de"):
            with self.subTest(language=language):
                workspace = Workspace(path=self.directory)
                workspace.completed = {station: "now" for station in STATIONS}
                workspace.save()
                for station in STATIONS:
                    response = self.client.get(f"/station/{station}?lang={language}")
                    self.assertEqual(response.status_code, 200, station)
                    expected = {
                        descriptor["name"]
                        for descriptor in forms.form(self.fields, station, language)
                    }
                    self.assertEqual(self.controls(response.text), expected, station)

    def test_no_locked_setting_appears_anywhere_in_the_interface(self) -> None:
        workspace = Workspace(path=self.directory)
        workspace.completed = {station: "now" for station in STATIONS}
        workspace.save()
        for language in ("en", "de"):
            for station in STATIONS:
                html = self.client.get(f"/station/{station}?lang={language}").text
                for path in self.locked:
                    with self.subTest(language=language, station=station, field=path):
                        self.assertNotIn(path, html)
                        self.assertNotIn(f'name="{path}"', html)

    def test_the_interface_invents_no_control(self) -> None:
        """Every rendered name is a declared field path — nothing extra."""
        declared = {field.path for field in self.fields}
        workspace = Workspace(path=self.directory)
        workspace.completed = {station: "now" for station in STATIONS}
        workspace.save()
        for station in STATIONS:
            html = self.client.get(f"/station/{station}?lang=en").text
            self.assertTrue(self.controls(html) <= declared, station)

    def test_the_overview_counts_come_from_the_definitions(self) -> None:
        html = self.client.get("/?lang=en").text
        self.assertIn(str(len(self.fields)), html)
        self.assertIn(str(len(forms.form(self.fields))), html)
        self.assertIn(str(len(self.locked)), html)

    # --- language ----------------------------------------------------------

    def test_both_languages_are_served_in_full(self) -> None:
        english = self.client.get("/?lang=en").text
        german = self.client.get("/?lang=de").text
        self.assertIn('lang="en"', english)
        self.assertIn('lang="de"', german)
        self.assertIn("A research method, not a call script", english)
        self.assertIn("Eine Forschungsmethode, kein Anrufskript", german)

    def test_german_keeps_real_umlauts(self) -> None:
        """Real ä ö ü ß, never an HTML entity and never an ae/oe/ue spelling."""
        german = self.client.get("/station/01-research-question?lang=de").text
        self.assertIn("Fragestellung", german)
        self.assertIn("Maßstab", german)
        self.assertIn("prüfbare", german)
        self.assertRegex(german, r"[äöüÄÖÜß]")
        for entity in ("&auml;", "&ouml;", "&uuml;", "&szlig;", "&#228;"):
            self.assertNotIn(entity, german)
        self.assertNotIn("abschliessen", german)
        self.assertIn("abschließen", german)

    def test_the_chosen_language_survives_the_next_request(self) -> None:
        self.client.get("/?lang=de")
        self.assertIn('lang="de"', self.client.get("/").text)
        self.client.get("/?lang=en")
        self.assertIn('lang="en"', self.client.get("/").text)

    def test_every_interface_string_has_every_language(self) -> None:
        sys.path.insert(0, str(ROOT))
        import manage_translations

        from researchcall.web import i18n

        keys = manage_translations.used_keys()
        self.assertTrue(keys)
        for language in i18n.LANGUAGES:
            with self.subTest(language=language):
                self.assertEqual(i18n.untranslated(keys, language), [])

    # --- gating ------------------------------------------------------------

    def test_a_station_stays_shut_until_its_predecessor_is_finished(self) -> None:
        response = self.client.get("/station/02-instrument?lang=en")
        self.assertEqual(response.url.path, f"/station/{STATIONS[0]}")
        self.finish(STATIONS[0])
        response = self.client.get("/station/02-instrument?lang=en")
        self.assertEqual(response.url.path, "/station/02-instrument")

    def test_a_station_will_not_close_while_a_required_answer_is_missing(self) -> None:
        body = self.payload(STATIONS[0], question="") + "&action=complete"
        response = self.client.post(
            f"/station/{STATIONS[0]}?lang=en", content=body, headers=FORM_ENCODED
        )
        self.assertIn("Still missing", response.text)
        self.assertIn("question", response.text)
        stored = Workspace.load(self.directory)
        self.assertNotIn(STATIONS[0], stored.completed)

    def test_a_change_after_the_station_closed_is_marked_as_a_later_addition(self) -> None:
        self.finish(STATIONS[0])
        body = self.payload(STATIONS[0], question="A different question entirely?")
        response = self.client.post(
            f"/station/{STATIONS[0]}?lang=en", content=body + "&action=save",
            headers=FORM_ENCODED,
        )
        self.assertIn("added later", response.text)
        stored = Workspace.load(self.directory)
        self.assertEqual([entry["field"] for entry in stored.amendments], ["question"])
        self.assertIn(STATIONS[0], stored.completed)

    # --- configuration -----------------------------------------------------

    def test_the_configuration_carries_the_frame_even_though_no_control_does(self) -> None:
        config = self.client.get("/config.json").json()
        self.assertIs(config["ethics"]["consent_explicit"], True)
        self.assertIs(config["analysis"]["keep_raw_alongside_coded"], True)

    def test_answers_reach_the_configuration(self) -> None:
        self.finish_all()
        config = self.client.get("/config.json").json()
        self.assertEqual(config["sample"]["size"], 9)
        self.assertEqual(config["question"], ANSWERS["question"])

    # --- field phase and report -------------------------------------------

    def test_the_dry_run_keeps_the_outcome_kinds_apart(self) -> None:
        self.finish_all()
        prepared = self.client.post("/fieldwork/prepare?lang=en")
        self.assertEqual(prepared.status_code, 200)
        with self.client.stream("GET", "/fieldwork/stream") as stream:
            events = [
                json.loads(line[6:])
                for line in stream.iter_lines()
                if line.startswith("data: ")
            ]
        self.assertTrue(events)
        self.assertTrue(events[-1]["done"])
        # Calls, not people: nine records were drawn, and whoever declined but
        # invited a later call is dialled again, up to the configured limit.
        self.assertGreaterEqual(events[-1]["processed"], 9)
        totals = events[-1]["totals"]
        self.assertIn("COMPLETED", totals)
        self.assertGreater(len(totals), 1, "distinct terminal statuses must stay distinct")

        report = self.client.get("/report?lang=en")
        self.assertEqual(report.status_code, 200)
        self.assertIn("NO_ANSWER", report.text)
        self.assertIn("DECLINED", report.text)
        markdown = self.client.get("/report.md")
        self.assertEqual(markdown.status_code, 200)
        self.assertIn("Included records: 9", markdown.text)
        self.assertIn("Attempts recorded: " + str(events[-1]["processed"]), markdown.text)

    def test_a_person_who_invited_a_later_call_is_dialled_again_and_the_report_says_so(
        self,
    ) -> None:
        """Repeated contact is allowed, bounded, and never silent."""
        self.finish_all()
        self.client.post("/fieldwork/prepare?lang=en")
        with self.client.stream("GET", "/fieldwork/stream") as stream:
            events = [
                json.loads(line[6:])
                for line in stream.iter_lines()
                if line.startswith("data: ")
            ]
        markdown = self.client.get("/report.md").text
        attempts = events[-1]["processed"]
        self.assertGreater(attempts, 9, "the callback rule should produce repeat calls")
        self.assertIn("## Repeated contact", markdown)
        self.assertIn("Attempts allowed per person: 1", markdown)
        self.assertIn("Callbacks allowed after a refusal: 3", markdown)
        self.assertRegex(markdown, r"Records dialled more than once: [1-9]")
        # A repeat lands in a different time of day; anything else would measure
        # the same availability twice.
        self.assertRegex(
            markdown, r"Attempts made in a time window other than the assigned one: [1-9]"
        )

    def test_a_setting_without_effect_says_so_on_its_own_control(self) -> None:
        """The honesty layer has to be visible where the decision is made."""
        from researchcall import effect

        workspace = Workspace(path=self.directory)
        workspace.completed = {station: "now" for station in STATIONS}
        workspace.save()
        declared = {field.path for field in effect.declared_only(self.fields)}
        self.assertTrue(declared)
        for language, badge in (("en", "recorded only"), ("de", "nur erfasst")):
            with self.subTest(language=language):
                html = self.client.get(f"/station/04-sampling?lang={language}").text
                self.assertIn(badge, html)
                self.assertIn("contact_rules.calling_hours", declared)
                config = self.client.get(f"/config?lang={language}").text
                for path in sorted(declared):
                    self.assertIn(path, config, path)

    def test_a_method_the_frame_cannot_support_is_refused_not_faked(self) -> None:
        self.finish_all()
        body = self.payload("04-sampling", **{"sample.method": "stratified"})
        self.client.post(
            "/station/04-sampling?lang=en", content=body + "&action=save",
            headers=FORM_ENCODED,
        )
        response = self.client.post("/fieldwork/prepare?lang=en")
        self.assertIn("stratifying attributes", response.text)
        self.assertFalse((self.directory / "fieldwork.db").exists())

    def test_the_instrument_pages_show_the_call_that_will_be_spoken(self) -> None:
        self.finish_all()
        page = self.client.get("/instrument?lang=en")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Do you use the bus?", page.text)
        task = self.client.get("/instrument.task.txt")
        self.assertEqual(task.status_code, 200)
        self.assertIn('I1 (say exactly): "Do you use the bus?"', task.text)
        self.assertIn("automated research call", task.text)
        self.assertIn("public directory", task.text)
        document = self.client.get("/instrument.md")
        self.assertEqual(document.status_code, 200)
        self.assertIn("[consent]", document.text)

    def test_switching_the_questionnaire_export_off_withdraws_the_download(self) -> None:
        """A setting the register calls effective has to change something."""
        self.finish_all()
        self.assertEqual(self.client.get("/instrument.md").status_code, 200)
        body = self.payload("05-pretest", **{"pretest.export_questionnaire": ""})
        self.client.post(
            "/station/05-pretest?lang=en", content=body + "&action=save",
            headers=FORM_ENCODED,
        )
        self.assertEqual(self.client.get("/instrument.md").status_code, 404)
        self.assertNotIn("/instrument.md", self.client.get("/instrument?lang=en").text)

    def test_the_findings_note_is_named_by_station_eight_and_starts_from_the_numbers(
        self,
    ) -> None:
        self.finish_all()
        self.client.post("/fieldwork/prepare?lang=en")
        with self.client.stream("GET", "/fieldwork/stream") as stream:
            list(stream.iter_lines())
        note = self.client.get("/export/findings.md")
        self.assertEqual(note.status_code, 200)
        self.assertIn(ANSWERS["question"], note.text)
        self.assertIn("Included records: 9", note.text)
        self.assertIn("## Reading", note.text)
        self.assertIn("BEFUNDE.md", self.client.get("/report?lang=en").text)

    def test_the_instrument_check_runs_and_names_its_own_limits(self) -> None:
        self.finish_all()
        result = self.client.post("/pretest/run?lang=en")
        self.assertEqual(result.status_code, 200)
        self.assertIn("Not measurable in a dry run", result.text)
        self.assertIn("unplanned_follow_ups", result.text)
        self.assertIn("not the CALL-E agent", result.text)

    def test_the_report_says_so_when_no_field_phase_has_run(self) -> None:
        self.assertIn("nothing to report", self.client.get("/report?lang=en").text)
        self.assertEqual(self.client.get("/report.md").status_code, 404)

    # --- what the interface must never do ---------------------------------

    def test_no_response_ever_carries_a_phone_number(self) -> None:
        self.finish_all()
        self.client.post("/fieldwork/prepare?lang=en")
        with self.client.stream("GET", "/fieldwork/stream") as stream:
            streamed = "".join(stream.iter_text())
        pages = [streamed]
        for language in ("en", "de"):
            pages.append(self.client.get(f"/?lang={language}").text)
            pages.append(self.client.get(f"/report?lang={language}").text)
            pages.append(self.client.get(f"/config?lang={language}").text)
            pages.append(self.client.get(f"/fieldwork?lang={language}").text)
            for station in STATIONS:
                pages.append(self.client.get(f"/station/{station}?lang={language}").text)
        pages.append(self.client.get("/report.md").text)
        pages.append(json.dumps(self.client.get("/config.json").json()))
        for page in pages:
            self.assertIsNone(PHONE.search(page), "a phone number reached a response")

    def test_the_web_package_cannot_reach_the_live_transport(self) -> None:
        package = ROOT / "src" / "researchcall" / "web"
        for path in package.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            with self.subTest(module=path.name):
                self.assertNotIn("LiveCallClient", source)
                self.assertNotIn("CALLE_API_KEY", source)

    def test_no_route_accepts_a_live_flag(self) -> None:
        for route in create_app(self.directory).routes:
            parameters = getattr(getattr(route, "dependant", None), "query_params", [])
            for parameter in parameters:
                self.assertNotIn("live", parameter.name.lower())


if __name__ == "__main__":
    unittest.main()
