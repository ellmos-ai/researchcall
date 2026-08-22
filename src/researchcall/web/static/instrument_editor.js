/*
 * instrument_editor.js — labelled rows instead of a remembered pipe syntax.
 *
 * RC9(a) (Endabnahme 2026-08-22): "veraltete Eingabemuster — Text nach einer
 * Parsing-Folge/Syntax eingeben statt getrennter Formularfelder". The station
 * pages already send a plain multi-line string for every "list"/"table"
 * field (see coerce() in workspace.py); this file changes nothing about that
 * wire format. It builds a small row editor beside the <textarea> for the
 * three fields whose line syntax is genuinely a syntax to remember — items,
 * hypotheses, questionnaire.jump_rules — and keeps the textarea's value in
 * exact sync on every edit, so the field the server reads never changes
 * shape. A line this file cannot confidently split into columns is shown as
 * one editable raw-text row instead of being guessed at or dropped.
 *
 * Grammar authority stays server-side, in researchcall.instrument
 * (parse_items, parse_jump_rules) — this file only removes the memorised
 * syntax from data *entry*. Semantic problems (duplicate ids, an unknown
 * item, a bad scale) are still reported the same way they always were: on
 * the /instrument preview and the /pretest dry run.
 *
 * Run the pure half with:  node --test tests/instrument_editor_js.test.js
 */

(function (global) {
  "use strict";

  // --- shared line helpers -----------------------------------------------

  function splitPipes(line) {
    return String(line).split("|").map(function (part) { return part.trim(); });
  }

  function joinPipes(parts) {
    return parts.map(function (part) { return part == null ? "" : String(part); }).join(" | ");
  }

  // Mirrors instrument.py's _unquote: strips at most one quote-like
  // character from each end. Deliberately not stricter than the Python
  // side — a line either side considers unquoted stays unquoted here too.
  var QUOTE = /^\s*["“„'’]?([\s\S]*?)["“„'’]?\s*$/;

  function unquote(text) {
    var match = QUOTE.exec(String(text));
    return match ? match[1].trim() : String(text).trim();
  }

  function quoteWording(text) {
    return '"' + (text == null ? "" : String(text)) + '"';
  }

  // --- items: id | hypothesis | format | "wording" | option | option -----

  function parseItemLine(line) {
    var parts = splitPipes(line);
    if (parts.length < 4) {
      return { raw: line, error: true };
    }
    return {
      id: parts[0],
      hypothesis: parts[1],
      format: parts[2],
      wording: unquote(parts[3]),
      options: parts.slice(4).filter(function (part) { return part; }).join(" | "),
      error: false
    };
  }

  function serializeItemLine(row) {
    if (row.error) return row.raw || "";
    var head = [row.id, row.hypothesis, row.format, quoteWording(row.wording)];
    var tail = String(row.options || "")
      .split("|")
      .map(function (part) { return part.trim(); })
      .filter(function (part) { return part; });
    return joinPipes(head.concat(tail));
  }

  // --- hypotheses: id | statement | indicator | falsification ------------
  //
  // Never read by parse_items or any other server code (confirmed against
  // instrument.py and research-question.forms.yaml) — the four-part
  // convention is documentation the researcher writes for themselves, so
  // this half carries no round-trip risk beyond "the text looks right".

  function parseHypothesisLine(line) {
    var parts = splitPipes(line);
    if (parts.length !== 4) {
      return { raw: line, error: true };
    }
    return { id: parts[0], statement: parts[1], indicator: parts[2], falsification: parts[3], error: false };
  }

  function serializeHypothesisLine(row) {
    if (row.error) return row.raw || "";
    return joinPipes([row.id, row.statement, row.indicator, row.falsification]);
  }

  // --- jump rules: if <source> = <value> skip <targets> -------------------
  //
  // Mirrors instrument.py's _JUMP regex exactly (same alternatives, same
  // case-insensitivity) so a line this accepts is a line parse_jump_rules
  // accepts too.

  var JUMP = /^\s*(?:if\s+|wenn\s+)?([\w.-]+)\s*(?:=|==|ist)\s*([^\s|]+)\s*(?:->|=>|then\s+|dann\s+)?\s*(?:skip|überspringe|ueberspringe)\s+(.+)$/i;

  function parseJumpRuleLine(line) {
    var match = JUMP.exec(String(line));
    if (!match) return { raw: line, error: true };
    return {
      source: match[1],
      value: unquote(match[2]),
      targets: match[3].split(/[,\s]+/).filter(function (part) { return part; }).join(", "),
      error: false
    };
  }

  function serializeJumpRuleLine(row) {
    if (row.error) return row.raw || "";
    var targets = String(row.targets || "")
      .split(/[,\s]+/)
      .filter(function (part) { return part; })
      .join(", ");
    return "if " + (row.source || "") + " = " + (row.value || "") + " skip " + targets;
  }

  var SCHEMAS = {
    items: { parse: parseItemLine, serialize: serializeItemLine, columns: ["id", "hypothesis", "format", "wording", "options"] },
    hypotheses: { parse: parseHypothesisLine, serialize: serializeHypothesisLine, columns: ["id", "statement", "indicator", "falsification"] },
    "questionnaire.jump_rules": { parse: parseJumpRuleLine, serialize: serializeJumpRuleLine, columns: ["source", "value", "targets"] }
  };

  function textToRows(schema, text) {
    var lines = String(text || "").split("\n").map(function (l) { return l.trim(); }).filter(Boolean);
    return lines.map(schema.parse);
  }

  function rowsToText(schema, rows) {
    return rows.map(schema.serialize).join("\n");
  }

  var pure = {
    parseItemLine: parseItemLine,
    serializeItemLine: serializeItemLine,
    parseHypothesisLine: parseHypothesisLine,
    serializeHypothesisLine: serializeHypothesisLine,
    parseJumpRuleLine: parseJumpRuleLine,
    serializeJumpRuleLine: serializeJumpRuleLine,
    textToRows: textToRows,
    rowsToText: rowsToText,
    SCHEMAS: SCHEMAS
  };

  // --- DOM wiring — only runs where there is a document -------------------

  function readSchemaLabels(name) {
    var selector = 'script[data-schema-for="' + name.replace(/"/g, '\\"') + '"]';
    var el = document.querySelector(selector);
    if (!el) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (err) {
      return null;
    }
  }

  function buildCell(fieldMeta, key, value, onChange) {
    var input = fieldMeta && fieldMeta.select
      ? document.createElement("select")
      : document.createElement("input");
    input.className = "row-editor-cell";
    input.dataset.key = key;
    if (fieldMeta && fieldMeta.select) {
      fieldMeta.select.forEach(function (option) {
        var opt = document.createElement("option");
        opt.value = option.value;
        opt.textContent = option.label;
        input.appendChild(opt);
      });
      input.value = value || (fieldMeta.select[0] && fieldMeta.select[0].value) || "";
    } else {
      input.type = "text";
      input.value = value || "";
      if (fieldMeta && fieldMeta.placeholder) input.placeholder = fieldMeta.placeholder;
    }
    if (fieldMeta && fieldMeta.label) input.setAttribute("aria-label", fieldMeta.label);
    input.title = (fieldMeta && fieldMeta.label ? fieldMeta.label + " — " : "") + (input.title || "");
    input.addEventListener("input", onChange);
    input.addEventListener("change", onChange);
    return input;
  }

  function removeButton(labels, onClick) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "row-editor-remove quiet";
    button.textContent = labels.remove || "×";
    button.addEventListener("click", onClick);
    return button;
  }

  function mount(container) {
    var name = container.dataset.structured;
    var schema = SCHEMAS[name];
    var labels = readSchemaLabels(name);
    if (!schema || !labels) return;

    var rows = textToRows(schema, container.value);

    var editor = document.createElement("div");
    editor.className = "row-editor";
    var rowsHost = document.createElement("div");
    editor.appendChild(rowsHost);

    function sync() {
      container.value = rowsToText(schema, rows);
      container.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function renderRows() {
      rowsHost.innerHTML = "";
      rows.forEach(function (row, index) {
        var wrap = document.createElement("div");
        wrap.className = "row-editor-row";
        if (row.error) {
          wrap.className += " row-editor-raw";
          var rawInput = document.createElement("input");
          rawInput.type = "text";
          rawInput.className = "row-editor-cell row-editor-cell-wide mono";
          rawInput.value = row.raw || "";
          rawInput.title = labels.raw_hint || "";
          rawInput.addEventListener("input", function () {
            rows[index] = { raw: rawInput.value, error: true };
            sync();
          });
          wrap.appendChild(rawInput);
          wrap.appendChild(removeButton(labels, function () {
            rows.splice(index, 1); renderRows(); sync();
          }));
          rowsHost.appendChild(wrap);
          return;
        }
        schema.columns.forEach(function (key) {
          var fieldMeta = labels.fields[key];
          var cell = buildCell(fieldMeta, key, row[key], function (event) {
            row[event.target.dataset.key] = event.target.value;
            sync();
          });
          wrap.appendChild(cell);
        });
        wrap.appendChild(removeButton(labels, function () {
          rows.splice(index, 1); renderRows(); sync();
        }));
        rowsHost.appendChild(wrap);
      });
    }

    var addButton = document.createElement("button");
    addButton.type = "button";
    addButton.className = "row-editor-add quiet";
    addButton.textContent = labels.add || "+";
    addButton.addEventListener("click", function () {
      var blank = { error: false };
      schema.columns.forEach(function (key) { blank[key] = ""; });
      rows.push(blank);
      renderRows();
      sync();
    });
    editor.appendChild(addButton);

    renderRows();
    // Only hidden once the editor has actually mounted — a script error
    // above this line leaves the plain textarea visible and working.
    container.classList.add("row-editor-source");
    container.parentNode.insertBefore(editor, container.nextSibling);
  }

  function boot() {
    var nodes = document.querySelectorAll("textarea[data-structured]");
    for (var i = 0; i < nodes.length; i += 1) mount(nodes[i]);
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = pure;
  }
  global.instrumentEditor = pure;

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", boot);
    } else {
      boot();
    }
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
