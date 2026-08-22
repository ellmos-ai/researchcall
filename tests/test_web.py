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

    # --- wizard forward navigation (RC10) -----------------------------------

    def test_finishing_a_station_opens_the_next_one_automatically(self) -> None:
        """RC10 (Endabnahme 2026-08-22, Nutzervorgabe): finishing a station
        used to leave the researcher on the same page; the CLI/web wizard
        should move on by itself, the way a wizard does.
        """
        body = self.payload(STATIONS[0]) + "&action=complete"
        response = self.client.post(
            f"/station/{STATIONS[0]}?lang=en", content=body, headers=FORM_ENCODED
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.url.path, f"/station/{STATIONS[1]}")
        self.assertIn("Station finished. The next one is open.", response.text)
        self.assertIn(STATIONS[0], Workspace.load(self.directory).completed)

    def test_a_stale_completed_flag_shows_no_confirmation(self) -> None:
        """The flag names a real, currently-completed station or nothing at
        all — never whatever a visitor happens to put in the URL."""
        page = self.client.get(f"/station/{STATIONS[0]}?lang=en&completed=02-instrument")
        self.assertNotIn("Station finished. The next one is open.", page.text)
        page = self.client.get(f"/station/{STATIONS[0]}?lang=en&completed=not-a-station")
        self.assertNotIn("Station finished. The next one is open.", page.text)

    def test_finishing_the_last_station_opens_the_overview_with_a_completion_note(
        self,
    ) -> None:
        for station in STATIONS[:-1]:
            self.finish(station)
        body = self.payload(STATIONS[-1]) + "&action=complete"
        response = self.client.post(
            f"/station/{STATIONS[-1]}?lang=en", content=body, headers=FORM_ENCODED
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.url.path, "/")
        self.assertIn("All eight stations are finished.", response.text)

    def test_the_wizard_hand_off_speaks_the_visitor_s_language(self) -> None:
        body = self.payload(STATIONS[0], language="de") + "&action=complete"
        response = self.client.post(
            f"/station/{STATIONS[0]}?lang=de", content=body, headers=FORM_ENCODED
        )
        self.assertEqual(response.url.path, f"/station/{STATIONS[1]}")
        self.assertIn("Station abgeschlossen. Die nächste ist frei.", response.text)

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

    def test_test_mode_prefills_the_example_study_in_the_current_language(self) -> None:
        """RC1 (Endabnahme 2026-08-22): enabling test mode while the UI was
        already set to German still filled the example study with English
        text — ``example_values`` had only ever been given one, English,
        table to read from.
        """
        self.toggle_test_mode(language="de")

        station_one = self.client.get("/station/01-research-question?lang=de").text
        self.assertIn(
            "Wie wirkt sich die Taktfrequenz des lokalen Busverkehrs", station_one
        )
        self.assertNotIn("How does the frequency of local bus service", station_one)

        station_two = self.client.get("/station/02-instrument?lang=de").text
        self.assertIn(
            "Nutzen Sie den Bus normalerweise für Ihren Arbeitsweg", station_two
        )
        self.assertNotIn("Do you usually use the bus for your commute", station_two)

    def test_switching_language_translates_untouched_examples_not_a_researchers_edit(
        self,
    ) -> None:
        """RC1: the example text must follow a later language switch too, but
        never overwrite what a researcher typed while exploring in the other
        language.
        """
        self.toggle_test_mode(language="en")
        english = self.client.get("/station/01-research-question?lang=en").text
        self.assertIn("How does the frequency of local bus service", english)

        # The researcher edits the example question while touring in English.
        edited_question = "A hand-typed question the tour never suggested."
        body = self.payload(
            "01-research-question", language="en", question=edited_question
        )
        edit_response = self.client.post(
            "/station/01-research-question?lang=en", content=body, headers=FORM_ENCODED
        )
        self.assertEqual(edit_response.status_code, 200)

        # Switching the UI language settles the workspace file within this
        # one request (`shell()` runs on every page, including this POST's
        # own response) — no separate "apply language" action exists to wait
        # for.
        self.client.get("/station/02-instrument?lang=de")
        workspace = Workspace.load(self.directory)
        self.assertEqual(workspace.test_example_language, "de")
        self.assertEqual(workspace.test_values["question"], edited_question)
        self.assertIn(
            "Nutzen Sie den Bus normalerweise für Ihren Arbeitsweg",
            workspace.test_values["items"][0],
        )

        # …and the next page load in German shows exactly that split.
        station_two_de = self.client.get("/station/02-instrument?lang=de").text
        self.assertIn(
            "Nutzen Sie den Bus normalerweise für Ihren Arbeitsweg", station_two_de
        )
        station_one_de = self.client.get("/station/01-research-question?lang=de").text
        self.assertIn(edited_question, station_one_de)
        self.assertNotIn("Wie wirkt sich die Taktfrequenz", station_one_de)

    # --- structured row editors (RC9(a)) ------------------------------------
    #
    # RC9 (Endabnahme 2026-08-22): "veraltete Eingabemuster — Text nach einer
    # Parsing-Folge/Syntax eingeben statt getrennter Formularfelder". These
    # tests are deliberately about the *markup and schema*, not about
    # JavaScript behaviour — the row editor's own parse/serialize logic is
    # tested where it lives, in tests/instrument_editor_js.test.js
    # (``node --test tests/instrument_editor_js.test.js``). What matters here
    # is: (1) exactly the three fields with a real multi-part line syntax are
    # marked for the structured editor and nothing else is, (2) the schema a
    # browser reads is present and translated, and (3) the field the server
    # actually reads is completely unchanged — a plain multi-line string,
    # still parsed by researchcall.instrument the same way it always was.

    def open_every_station(self) -> None:
        """A fresh workspace only has station 1 open — every other GET or
        POST redirects there. These tests are about later stations' markup,
        so open the gate the same way test_each_station_renders_exactly_its_form_definitions does.
        """
        workspace = Workspace(path=self.directory)
        workspace.completed = {station: "now" for station in STATIONS}
        workspace.save()

    def test_only_the_multi_part_syntax_fields_get_a_structured_editor(self) -> None:
        self.open_every_station()
        instrument_page = self.client.get("/station/02-instrument?lang=en").text
        self.assertIn('data-structured="items"', instrument_page)
        self.assertIn('data-structured="questionnaire.jump_rules"', instrument_page)

        research_question_page = self.client.get(
            "/station/01-research-question?lang=en"
        ).text
        self.assertIn('data-structured="hypotheses"', research_question_page)

        # A single-value-per-line list — the finding is about a multi-part
        # syntax, and one value per line is not one. It keeps the plain
        # textarea it always had.
        ethics_page = self.client.get("/station/03-ethics?lang=en").text
        self.assertNotIn('data-structured="ethics.policies"', ethics_page)
        self.assertIn('name="ethics.policies"', ethics_page)

    def test_the_structured_editor_script_is_loaded_and_schemas_are_translated(
        self,
    ) -> None:
        self.open_every_station()
        instrument_page = self.client.get("/station/02-instrument?lang=en").text
        self.assertIn('src="/static/instrument_editor.js"', instrument_page)

        match = re.search(
            r'<script type="application/json" data-schema-for="items">(.*?)</script>',
            instrument_page,
        )
        self.assertIsNotNone(match)
        schema = json.loads(match.group(1))
        self.assertEqual(
            set(schema["fields"]), {"id", "hypothesis", "format", "wording", "options"}
        )
        self.assertEqual(schema["fields"]["wording"]["label"], "Wording")
        self.assertEqual(schema["add"], "Add row")
        format_values = {option["value"] for option in schema["fields"]["format"]["select"]}
        self.assertEqual(
            format_values,
            {"dichotomous", "scale", "scale_reversed", "choice", "open", "creative"},
        )

        instrument_page_de = self.client.get("/station/02-instrument?lang=de").text
        match_de = re.search(
            r'<script type="application/json" data-schema-for="items">(.*?)</script>',
            instrument_page_de,
        )
        self.assertIsNotNone(match_de)
        schema_de = json.loads(match_de.group(1))
        self.assertEqual(schema_de["fields"]["wording"]["label"], "Wortlaut")
        self.assertEqual(schema_de["add"], "Zeile hinzufügen")
        format_values_de = {
            option["value"] for option in schema_de["fields"]["format"]["select"]
        }
        self.assertEqual(
            format_values_de,
            {"dichotom", "skala", "skala_umgepolt", "auswahl", "offen", "kreativ"},
        )

    def test_the_structured_editor_never_changes_what_the_server_actually_reads(
        self,
    ) -> None:
        """The row editor is client-side sugar over the same textarea.

        A submission built exactly the way instrument_editor.js's
        serializeItemLine/serializeJumpRuleLine would build one — quoted
        wording, ``if <source> = <value> skip <targets>`` — is posted as the
        plain multi-line string coerce() has always expected, and reaches the
        workspace unchanged.
        """
        self.open_every_station()
        items_value = "\n".join(
            [
                'q1 | H1 | dichotomous | "Do you use the bus?" | free',
                'q2 | H1 | scale | "How satisfied are you?" | scale=5:very unsatisfied..very satisfied',
            ]
        )
        jump_rules_value = "if q1 = no skip q2"
        response = self.client.post(
            "/station/02-instrument?lang=en",
            content=self.payload(
                "02-instrument",
                items=items_value,
                **{"questionnaire.jump_rules": jump_rules_value},
            ),
            headers=FORM_ENCODED,
        )
        self.assertEqual(response.status_code, 200)

        workspace = Workspace.load(self.directory)
        self.assertEqual(
            workspace.values["items"],
            [
                'q1 | H1 | dichotomous | "Do you use the bus?" | free',
                'q2 | H1 | scale | "How satisfied are you?" | scale=5:very unsatisfied..very satisfied',
            ],
        )
        self.assertEqual(workspace.values["questionnaire.jump_rules"], ["if q1 = no skip q2"])

    def test_format_alias_dropdown_never_drifts_from_the_grammar_it_feeds(self) -> None:
        """The dropdown's canonical values are read from instrument.FORMATS,
        not duplicated as a second literal list — a format instrument.py
        learns to parse tomorrow could otherwise go unlisted here silently.
        """
        from researchcall import instrument
        from researchcall.web import render

        self.assertEqual(set(render.FORMAT_ALIASES), set(instrument.FORMATS.values()))
        self.assertEqual(set(render.FORMAT_LABELS), set(instrument.FORMATS.values()))

    def test_test_mode_never_supplies_or_reveals_a_locked_field(self) -> None:
        # The set, not the count. A bare number says that something changed;
        # the set says WHICH field became locked or lost its lock, which is the
        # part a person has to decide about. Deriving it from the registry
        # instead would assert the registry against itself and prove nothing.
        self.assertEqual(
            self.locked,
            {
                "analysis.keep_raw_alongside_coded",
                "analysis.report.answers_by_window",
                "analysis.report.dropout_by_window",
                "analysis.report.response_rate",
                "ethics.consent_explicit",
                "ethics.right_to_stop",
                "ethics.time_estimate",  # locked 2026-08-11, FINDINGS section 14
                "fieldwork.keep_raw_answer",
                "pretest.instrument_check.measure",
                "pretest.instrument_check.report_result_honestly",
                "publication.dry_run_first",
                "publication.source_check_before_upload",
            },
        )
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

    def test_answers_survive_a_full_workbench_restart(self) -> None:
        """RC11 (Endabnahme 2026-08-22, vom Nutzer NICHT getestet): a saved
        project must reopen with every field intact. A unit test cannot kill
        and restart a real process, so this simulates the closest analogue —
        a brand-new app instance (a fresh ``create_app()`` and ``TestClient``,
        with its own freshly-loaded field definitions and no shared Python
        state whatsoever with ``self.client``) bound to the SAME workspace
        directory on disk. Anything that survives this has to have come from
        the file, not from server memory.
        """
        self.finish_all()
        self.toggle_test_mode()
        edited_example = "The tour example, hand-edited before the restart."
        edit_body = self.payload(
            STATIONS[0], question=edited_example, hypotheses="H1 | Edited | I1 | Also edited"
        )
        self.client.post(
            f"/station/{STATIONS[0]}?lang=en", content=edit_body, headers=FORM_ENCODED
        )

        before_config = self.client.get("/config.json").json()
        before_workspace = Workspace.load(self.directory)
        # Something to lose in each of the two apart-kept workspaces, or this
        # test proves nothing: the real study's answer, and the tour's edit.
        self.assertEqual(before_workspace.values["question"], ANSWERS["question"])
        self.assertEqual(before_workspace.test_values["question"], edited_example)

        # --- the workbench restarts -----------------------------------------
        restarted_client = TestClient(create_app(self.directory))

        after_config = restarted_client.get("/config.json").json()
        self.assertEqual(after_config, before_config)

        after_workspace = Workspace.load(self.directory)
        self.assertEqual(after_workspace.values, before_workspace.values)
        self.assertEqual(after_workspace._completed, before_workspace._completed)
        self.assertEqual(set(before_workspace._completed), set(STATIONS))
        self.assertEqual(after_workspace.amendments, before_workspace.amendments)
        self.assertEqual(after_workspace.test_mode, before_workspace.test_mode)
        self.assertEqual(after_workspace.test_values, before_workspace.test_values)

        # And the field survives through the SAME public interface a
        # researcher actually uses — pre-filled into the reopened form, not
        # just present somewhere in a JSON export.
        station_one = restarted_client.get(f"/station/{STATIONS[0]}?lang=en").text
        self.assertIn(edited_example, station_one)

        # Test mode itself — an isolated workspace, not just a field — also
        # reopens exactly as it was left.
        overview = restarted_client.get("/?lang=en").text
        self.assertIn("Test mode — example data, not a real study", overview)

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
