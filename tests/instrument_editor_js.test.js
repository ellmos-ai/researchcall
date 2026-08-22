/*
 * The row editor's pure half: parsing and serializing one line at a time.
 *
 * Run with:  node --test tests/instrument_editor_js.test.js
 *
 * These functions never touch a document, so they are tested directly here.
 * The DOM-mounting half (querySelector, event listeners) is exercised by
 * hand in a browser — a stubbed document would prove the stub, the same
 * reasoning huckepack_js.test.js already documents for its own file.
 *
 * What matters most is not roundtripping *this* file's own parser, but that
 * a line it serializes is a line researchcall.instrument.parse_items and
 * parse_jump_rules would accept without a Problem — that half of the
 * contract is proven on the Python side, in tests/test_render.py, against
 * strings built the same way this file would build them.
 */

const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");

const editor = require(path.join(__dirname, "..", "src", "researchcall", "web", "static", "instrument_editor.js"));

// --- items --------------------------------------------------------------

test("an item line splits into its five parts", () => {
  const row = editor.parseItemLine('q1 | H1 | dichotomous | "Do you use the bus?" | free');
  assert.strictEqual(row.error, false);
  assert.strictEqual(row.id, "q1");
  assert.strictEqual(row.hypothesis, "H1");
  assert.strictEqual(row.format, "dichotomous");
  assert.strictEqual(row.wording, "Do you use the bus?");
  assert.strictEqual(row.options, "free");
});

test("an item line with several options keeps them joined for the options cell", () => {
  const row = editor.parseItemLine('q2 | H1 | scale | "How satisfied are you?" | scale=5:very unsatisfied..very satisfied | rule=mean');
  assert.strictEqual(row.options, "scale=5:very unsatisfied..very satisfied | rule=mean");
});

test("a line with fewer than four parts is a raw fallback row, not a guess", () => {
  const row = editor.parseItemLine("q1 | H1 | dichotomous");
  assert.strictEqual(row.error, true);
  assert.strictEqual(row.raw, "q1 | H1 | dichotomous");
});

test("an item row serializes back to the pipe form, wording quoted", () => {
  const line = editor.serializeItemLine({
    id: "q1", hypothesis: "H1", format: "dichotomous", wording: "Do you use the bus?", options: "free"
  });
  assert.strictEqual(line, 'q1 | H1 | dichotomous | "Do you use the bus?" | free');
});

test("an item row with an empty options cell serializes without a trailing pipe", () => {
  const line = editor.serializeItemLine({
    id: "q1", hypothesis: "H1", format: "open", wording: "What did you think?", options: ""
  });
  assert.strictEqual(line, 'q1 | H1 | open | "What did you think?"');
});

test("parse then serialize returns the same line for a well-formed item", () => {
  const original = 'q1 | H1 | dichotomous | "Do you use the bus?" | free';
  const row = editor.parseItemLine(original);
  assert.strictEqual(editor.serializeItemLine(row), original);
});

test("a raw fallback row serializes back to exactly what was typed", () => {
  const row = editor.parseItemLine("not enough parts here");
  assert.strictEqual(editor.serializeItemLine(row), "not enough parts here");
});

// --- hypotheses -----------------------------------------------------------

test("a hypothesis line needs exactly four parts", () => {
  const row = editor.parseHypothesisLine("H1 | Riders prefer the express line | share choosing express | share does not differ from baseline");
  assert.strictEqual(row.error, false);
  assert.strictEqual(row.id, "H1");
  assert.strictEqual(row.statement, "Riders prefer the express line");
  assert.strictEqual(row.indicator, "share choosing express");
  assert.strictEqual(row.falsification, "share does not differ from baseline");
});

test("a hypothesis line with the wrong number of parts is a raw fallback", () => {
  const row = editor.parseHypothesisLine("H1 | only two parts");
  assert.strictEqual(row.error, true);
});

test("a hypothesis row serializes back with the same four parts", () => {
  const original = "H1 | Riders prefer express | mode share | no difference from baseline";
  const row = editor.parseHypothesisLine(original);
  assert.strictEqual(editor.serializeHypothesisLine(row), original);
});

// --- jump rules -------------------------------------------------------------

test("an English jump rule line parses into source, value and targets", () => {
  const row = editor.parseJumpRuleLine("if q1 = no skip q4, q5");
  assert.strictEqual(row.error, false);
  assert.strictEqual(row.source, "q1");
  assert.strictEqual(row.value, "no");
  assert.strictEqual(row.targets, "q4, q5");
});

test("a German jump rule line parses the same way — the grammar is bilingual", () => {
  const row = editor.parseJumpRuleLine("wenn q1 = nein überspringe q4, q5");
  assert.strictEqual(row.error, false);
  assert.strictEqual(row.source, "q1");
  assert.strictEqual(row.value, "nein");
  assert.strictEqual(row.targets, "q4, q5");
});

test("a line that is not a jump rule at all is a raw fallback, not a mis-parse", () => {
  const row = editor.parseJumpRuleLine("this is not a rule");
  assert.strictEqual(row.error, true);
});

test("a jump rule row serializes to the canonical if/skip form", () => {
  const line = editor.serializeJumpRuleLine({ source: "q1", value: "no", targets: "q4, q5" });
  assert.strictEqual(line, "if q1 = no skip q4, q5");
});

test("parse then serialize normalises a German rule into the same canonical form the Python side accepts either way", () => {
  const row = editor.parseJumpRuleLine("wenn q1 = nein überspringe q4,q5");
  assert.strictEqual(editor.serializeJumpRuleLine(row), "if q1 = nein skip q4, q5");
});

// --- whole-textarea round trip ---------------------------------------------

test("a multi-line items textarea round-trips through rows and back to the same text", () => {
  const text = [
    'q1 | H1 | dichotomous | "Do you use the bus?" | free',
    'q2 | H1 | scale | "How satisfied are you?" | scale=3:low..high'
  ].join("\n");
  const rows = editor.textToRows(editor.SCHEMAS.items, text);
  assert.strictEqual(rows.length, 2);
  assert.strictEqual(editor.rowsToText(editor.SCHEMAS.items, rows), text);
});

test("a blank line is dropped, matching parse_items' own line reader", () => {
  const rows = editor.textToRows(editor.SCHEMAS.items, "\nq1 | H1 | open | \"What did you think?\"\n\n");
  assert.strictEqual(rows.length, 1);
});
