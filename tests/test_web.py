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
from researchcall.web import test_mode  # noqa: E402
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
    # Required since 2026-08-11: both are spoken aloud in every call, so a
    # study that has not named them cannot be finished here or run live.
    "ethics.commissioner": "Example University",
    "ethics.privacy_short": "Answers are stored pseudonymously and deleted after two years.",
    "ethics.withdrawal_contact": "withdraw@example.invalid",
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

    def toggle_test_mode(self, language: str = "en", next_path: str = "/") -> str:
        response = self.client.post(
            "/test-mode/toggle?"
            + urllib.parse.urlencode({"lang": language, "next": next_path})
        )
        self.assertEqual(response.status_code, 200)
        return response.text

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
            pages = [
                self.client.get(f"/?lang={language}").text,
                self.client.get(f"/config?lang={language}").text,
                self.client.get(f"/instrument?lang={language}").text,
                self.client.get(f"/pretest?lang={language}").text,
                self.client.get(f"/fieldwork?lang={language}").text,
                self.client.get(f"/report?lang={language}").text,
            ]
            pages.extend(
                self.client.get(f"/station/{station}?lang={language}").text
                for station in STATIONS
            )
            for page_number, html in enumerate(pages, start=1):
                for path in self.locked:
                    with self.subTest(
                        language=language, page=page_number, field=path
                    ):
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
        self.assertIn(
            f"Eight stations contain {len(forms.form(self.fields))} visible decisions.",
            html,
        )
        self.assertIn(
            f"An agent asks {len(forms.interview(self.fields))} of them", html
        )

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

    def test_direct_workflow_actions_obey_the_station_gate(self) -> None:
        pretest = self.client.post("/pretest/run?lang=en")
        self.assertIn("Finish stations 1 to 5", pretest.text)
        fieldwork = self.client.post("/fieldwork/prepare?lang=en")
        self.assertIn("Finish stations 1 to 6", fieldwork.text)

        for station in STATIONS[:5]:
            self.finish(station)
        pretest = self.client.post("/pretest/run?lang=en")
        self.assertNotIn("Finish stations 1 to 5", pretest.text)
        self.assertIn("Not measurable in a dry run", pretest.text)

        fieldwork = self.client.post("/fieldwork/prepare?lang=en")
        self.assertIn("Finish stations 1 to 6", fieldwork.text)
        self.finish("06-fieldwork")
        fieldwork = self.client.post("/fieldwork/prepare?lang=en")
        self.assertNotIn("Finish stations 1 to 6", fieldwork.text)
        self.assertTrue((self.directory / "fieldwork.db").exists())
        opened = self.client.get("/fieldwork?lang=en")
        self.assertIn("Continue prepared dry run", opened.text)
        self.assertNotIn("new EventSource", opened.text)

    def test_test_mode_is_off_by_default_and_keeps_the_normal_gate(self) -> None:
        overview = self.client.get("/?lang=en")
        self.assertIn("Test mode is off", overview.text)
        self.assertIn("Enable test mode", overview.text)
        self.assertFalse(Workspace.load(self.directory).test_mode)

        station = self.client.get("/station/08-reporting?lang=en")
        self.assertEqual(station.url.path, f"/station/{STATIONS[0]}")

    def test_test_mode_opens_every_station_and_prefills_an_example(self) -> None:
        html = self.toggle_test_mode()
        self.assertIn("Test mode — example data, not a real study", html)
        self.assertIn("Network disabled · fixture transport · no real calls", html)

        for station in STATIONS:
            with self.subTest(station=station):
                response = self.client.get(f"/station/{station}?lang=en")
                self.assertEqual(response.url.path, f"/station/{station}")
                self.assertEqual(response.status_code, 200)
        station_one = self.client.get("/station/01-research-question?lang=en").text
        self.assertIn("How does the frequency of local bus service", station_one)
        station_two = self.client.get("/station/02-instrument?lang=en").text
        self.assertIn("Do you usually use the bus for your commute?", station_two)

        german = self.client.get("/?lang=de").text
        self.assertIn("Testmodus — Beispieldaten, keine echte Studie", german)
        self.assertIn("Netzwerk deaktiviert · Fixture-Transport · keine echten Anrufe", german)

    def test_test_mode_never_supplies_or_reveals_a_locked_field(self) -> None:
        self.assertEqual(len(self.locked), 11)
        examples = test_mode.example_values(self.fields)
        self.assertEqual(set(examples), {field.path for field in self.fields if not field.locked})
        self.assertTrue(set(examples).isdisjoint(self.locked))

        self.toggle_test_mode()
        pages = [self.client.get("/?lang=en").text, self.client.get("/config?lang=en").text]
        pages.extend(
            self.client.get(f"/station/{station}?lang=en").text for station in STATIONS
        )
        for html in pages:
            for path in self.locked:
                self.assertNotIn(path, html)
                self.assertNotIn(f'name="{path}"', html)

    def test_test_mode_keeps_example_answers_apart_from_study_answers(self) -> None:
        study = Workspace(path=self.directory)
        study.values["question"] = "This is the actual study question."
        study.completed = {STATIONS[0]: "actual-study"}
        study.save()

        self.toggle_test_mode()
        active = Workspace.load(self.directory)
        self.assertTrue(active.test_mode)
        self.assertEqual(active.values["question"], "This is the actual study question.")
        self.assertNotEqual(active.value(next(f for f in self.fields if f.path == "question")), active.values["question"])

        body = self.payload(
            STATIONS[0],
            question="A changed tour example.",
            hypotheses="H1 | Tour only | I1 | No difference",
        )
        self.client.post(
            f"/station/{STATIONS[0]}?lang=en",
            content=body + "&action=complete",
            headers=FORM_ENCODED,
        )
        self.toggle_test_mode()

        restored = Workspace.load(self.directory)
        self.assertFalse(restored.test_mode)
        self.assertEqual(restored.values["question"], "This is the actual study question.")
        self.assertEqual(restored.completed, {STATIONS[0]: "actual-study"})
        self.assertNotIn("A changed tour example", self.client.get("/config.json").text)

    def test_test_mode_bypasses_action_prerequisites_but_stays_fixture_only(self) -> None:
        self.toggle_test_mode()

        pretest = self.client.post("/pretest/run?lang=en")
        self.assertNotIn("Finish stations 1 to 5", pretest.text)
        self.assertIn("Not measurable in a dry run", pretest.text)

        prepared = self.client.post("/fieldwork/prepare?lang=en")
        self.assertNotIn("Finish stations 1 to 6", prepared.text)
        self.assertFalse((self.directory / "fieldwork.db").exists())
        self.assertTrue(
            (self.directory / "test-mode-artifacts" / "fieldwork.db").exists()
        )

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
        written = self.directory / "report.md"
        self.assertTrue(written.exists(), "the field phase must really write its report")
        self.assertEqual(written.read_text(encoding="utf-8"), markdown.text)

    def test_an_existing_field_phase_is_never_silently_replaced(self) -> None:
        self.finish_all()
        self.client.post("/fieldwork/prepare?lang=en")
        database = self.directory / "fieldwork.db"
        before = database.read_bytes()

        changed = self.payload("04-sampling", **{"sample.size": "10"})
        self.client.post(
            "/station/04-sampling?lang=en",
            content=changed + "&action=save",
            headers=FORM_ENCODED,
        )
        response = self.client.post("/fieldwork/prepare?lang=en")
        self.assertIn("different instrument or sampling plan", response.text)
        self.assertEqual(database.read_bytes(), before)

        original_sampling = self.payload("04-sampling", **{"sample.size": "9"})
        self.client.post(
            "/station/04-sampling?lang=en",
            content=original_sampling + "&action=save",
            headers=FORM_ENCODED,
        )
        non_resumable = self.payload(
            "06-fieldwork", **{"fieldwork.resumable": ""}
        )
        self.client.post(
            "/station/06-fieldwork?lang=en",
            content=non_resumable + "&action=save",
            headers=FORM_ENCODED,
        )
        response = self.client.post("/fieldwork/prepare?lang=en")
        self.assertIn("never deletes it", response.text)
        self.assertEqual(database.read_bytes(), before)

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
                self.assertIn('<div class="config-stack">', config)
                self.assertIn(
                    ".config-stack { display: grid; grid-template-columns: minmax(0, 1fr);",
                    config,
                )
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
        # The fixture run flags paraphrased calls on purpose; an export over
        # undecided conflicts is refused. Decide them the way a person would,
        # through the review page, then export.
        blocked = self.client.get("/export/findings.md")
        self.assertEqual(blocked.status_code, 409)
        for review_id in re.findall(
            r'name="review_id" value="(\d+)"', self.client.get("/reviews?lang=en").text
        ):
            decided = self.client.post(
                "/reviews/decide?lang=en",
                content=(
                    f"review_id={review_id}&decision=gate_passed"
                    "&note=checked+in+the+test"
                ),
                headers=FORM_ENCODED,
            )
            self.assertEqual(decided.status_code, 200)
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

    def test_the_data_phase_end_to_end_through_the_interface(self) -> None:
        """Call list, mask, manual flag, rule run, seal, exports, project zip."""
        self.finish_all()
        self.client.post("/fieldwork/prepare?lang=en")
        with self.client.stream("GET", "/fieldwork/stream") as stream:
            list(stream.iter_lines())

        # The call list renders and the conflict filter finds the flagged runs.
        calls = self.client.get("/calls?lang=en")
        self.assertEqual(calls.status_code, 200)
        conflicts = self.client.get("/calls?status=conflict&lang=en")
        sample_ids = re.findall(r'href="/calls/(\d+)\?lang=en"', conflicts.text)
        self.assertTrue(sample_ids, "the fixture run flags paraphrased calls")

        # The mask shows the suggestion, and the decision lands beside the case.
        mask = self.client.get(f"/calls/{sample_ids[0]}?lang=en")
        self.assertIn("Suggestion", mask.text)
        review_id = re.findall(r'name="review_id" value="(\d+)"', mask.text)[0]
        decided = self.client.post(
            f"/calls/{sample_ids[0]}/decide?lang=en",
            content=f"review_id={review_id}&decision=gate_passed&note=transcript+held",
            headers=FORM_ENCODED,
        )
        self.assertIn("gate_passed", decided.text)

        # A green call can be flagged manually, with grounds shown on reopening.
        successful = self.client.get("/calls?status=successful&lang=en")
        green_ids = re.findall(r'href="/calls/(\d+)\?lang=en"', successful.text)
        green_mask = self.client.get(f"/calls/{green_ids[0]}?lang=en")
        attempt_id = re.findall(r'name="attempt_id" value="(\d+)"', green_mask.text)[0]
        flagged = self.client.post(
            f"/calls/{green_ids[0]}/flag?lang=en",
            content=f"attempt_id={attempt_id}&note=reads+coached",
            headers=FORM_ENCODED,
        )
        self.assertIn("reads coached", flagged.text)

        # The rule closes everything still open, marked as a rule ruling.
        ruled = self.client.post(
            "/reviews/rule?lang=en",
            content="decision=dropout&note=default+policy+for+this+study",
            headers=FORM_ENCODED,
        )
        self.assertIn("decided by rule", ruled.text)
        self.assertNotIn('name="review_id"', self.client.get("/reviews?lang=en").text)

        # Exports open now that no case is open -- each in its real format.
        xlsx = self.client.get("/export/dataset.xlsx")
        self.assertEqual(xlsx.status_code, 200)
        self.assertTrue(xlsx.content.startswith(b"PK"), "an .xlsx is a zip")
        self.assertIn("GET DATA", self.client.get("/export/import.sps").text)
        self.assertIn("read.csv", self.client.get("/export/analysis.R").text)
        project = self.client.get("/project/export.zip")
        self.assertEqual(project.status_code, 200)
        self.assertTrue(project.content.startswith(b"PK"))

        # Sealing works once and needs grounds; afterwards the panel says so.
        sealed = self.client.post(
            "/dataphase/seal?lang=en",
            content="note=fieldwork+finished",
            headers=FORM_ENCODED,
        )
        self.assertIn("sealed", sealed.text.lower())

    def test_data_phase_panel_stays_in_the_fieldwork_content_area(self) -> None:
        """Supplemental fieldwork panels must not become shell-grid siblings.

        The rail owns the first column of ``.shell``.  If the data-phase card
        sits outside the fieldwork ``main``, CSS grid places it beneath that
        rail at x=0 instead of in the content column.
        """
        self.finish_all()
        page = self.client.get("/fieldwork?lang=en").text
        data_panel = page.index("<h3>Data phase</h3>")
        content_start = page.index("<main>")
        content_end = page.index("</main>", content_start)

        self.assertLess(content_start, data_panel)
        self.assertLess(data_panel, content_end)
        self.assertEqual(page.count("<main>"), 1)

    def test_the_transcript_retention_answer_travels_with_the_study(self) -> None:
        """What the researcher answers in station 6 has to reach the run.

        The default keeps the transcript, matching the form definition and the
        user decision of 2026-08-11; unticking the box has to switch it off for
        real, not only in the saved answer.
        """
        from researchcall.web import field_phase

        self.finish_all()
        questionnaire, _ = field_phase.build(
            Workspace.load(self.directory), self.fields
        )
        self.assertTrue(questionnaire["run_rules"]["keep_transcript"])

        body = (
            self.payload("06-fieldwork", **{"fieldwork.keep_transcript": ""})
            + "&action=complete"
        )
        response = self.client.post(
            "/station/06-fieldwork?lang=en", content=body, headers=FORM_ENCODED
        )
        self.assertEqual(response.status_code, 200)
        questionnaire, _ = field_phase.build(
            Workspace.load(self.directory), self.fields
        )
        self.assertFalse(questionnaire["run_rules"]["keep_transcript"])

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
