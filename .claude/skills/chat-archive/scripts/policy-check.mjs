#!/usr/bin/env node
// policy-check.mjs: the loud-failure check of fairbay/ops docs/decision-routing/DESIGN.md §5.
// Synced into every repo with the chat-archive skill. Run from the repo root:
//
//   node .claude/skills/chat-archive/scripts/policy-check.mjs [--root DIR] [--skip-s8] [--base REF] [--require-base]
//
// Checks, one line per failure, exit 1 on any:
//   (a) policy  .claude/policy.json parses and has the schema's required keys; every
//               decision-table `then` names a class (the JSON schema cannot check that).
//   (b) pointer every `policy: <class>` token in the rule files names a class, and the
//               sentence it sits in names that class's route (a word for asking, a card or
//               his OK; for logging and shipping; for filing a line; for stopping).
//   (c) S7      a rule sentence that routes work to Baylee (Baylee, him, his OK/go/…, with a
//               routing verb) carries a `policy:` token. Attributions are not routing: quoted
//               words and dated parentheticals ("Baylee's yes, 2026-10-06") are set aside first.
//               A flagged sentence that routes nothing is listed, whole and verbatim, in
//               signals.S7_uncited_routing_sentences.not_routing with its reason (ops S7 pass,
//               Grove dd1e9787). The match is the whole sentence (list marker and ** stripped),
//               so a later edit to an exempt sentence makes it fail again, and an entry that
//               matches no flagged sentence fails, so the list cannot go stale silently.
//   (d) S8      session_handoff.py measure: the entry hook, given a worst-case PR table, cuts
//               no character of the handoff (and, where lanes are declared, of any lane's baton).
//   (e) lanes   only where .claude/landing.yaml declares `lanes:` (fairbay/ops docs/lanes/DESIGN.md §3.4):
//               HANDOFF.yaml holds only meta and progress; progress keys are declared lanes with a blank line
//               between keys; every handoffs/lane-*.yaml names a declared lane; and the change against --base
//               (default origin/main; CI passes HEAD^1) touches at most one lane's baton (its file or its
//               progress line). The cross-lane check is skipped, with a note, when the base declares no lanes
//               (the migration), when the change edits the lane list, or when the base cannot be resolved
//               (--require-base, as CI passes it, makes that last one a failure). Each progress line is at
//               most 200 characters. Lane files with no lanes declared fail.
// The rule files are signals.S7_uncited_routing_sentences.files in policy.json. .claude/global.md
// is never linted here: it is a synced copy, linted in fairbay/ops only.
// Dependency-free (Node's own modules), so rules.yml runs it without an install.

import { readFileSync, existsSync, readdirSync, realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, relative } from "node:path";
import { spawnSync } from "node:child_process";
import { progressEntries, declaredLanes } from "./handoff-merge.mjs";
export { declaredLanes };

const STRICTER =
  "On a red S7 or S8, prose and policy both bind and the stricter reading wins (fairbay/ops docs/decision-routing/DESIGN.md §4).";
const POLICY = ".claude/policy.json";
const HANDOFF_SCRIPT = ".claude/skills/session-start/scripts/session_handoff.py";
const REQUIRED = ["version", "classes", "decision_table", "signals", "changelog"];
const ROUTE_RE = /^(proceed_log|card|card_then_owner|stop|one line to [a-z0-9-]+)$/;
const DEFAULT_FILES = ["CLAUDE.md", "docs/rules/*.md"];
const NEVER_LINTED = new Set([".claude/global.md"]);

// Words that show a sentence names a route: each class's own markers, not common words, so a
// pointer that contradicts its sentence (a "needs his OK" sentence cited as upkeep) fails.
const CARD_MARK =
  /\b(ask|asks|asked|asking|OK|approv\w*|rules? on|ruled|ruling|decid\w*|cards?|adjudicat\w*|screenshots?|taps?|escalat\w*|owner|consent|sign(s|ed)?[- ]off|(Baylee['’]s|his) (go|yes|call|word|say|review)|(is|are) shown|he sees|waits? (for|on)|shown to|show (him|Baylee)|until (he|Baylee)|judg\w*|(reach|reaches|reached|goes to|go to|put to|in front of|needs|need) (him|Baylee|his))\b/i;
// Markers that send a thing to Baylee whoever the subject is: a pointer that cites only a
// proceed_log class on such a sentence contradicts it.
const SEND_MARK =
  /\b(OK|approv\w*|screenshots?|(Baylee['’]s|his) (go|yes|OK|review|approval|sign-off)|waits? (for|on) (Baylee|him|his)|until (he|Baylee)|shown to (Baylee|him)|show (him|Baylee))\b/;
const PROCEED_MARK =
  /\b(log|logs|logged|rung 3|without (Baylee|him|his)|upkeep|merges itself|overrul\w*|revers\w*|settled?|goes ahead)\b/i;
const ROUTE_CUES = {
  card: CARD_MARK,
  proceed_log: PROCEED_MARK,
  one_line: /\b(file|files|filed|one line|real[- ]world|rotate|launch-ops|only he|say so|says so)\b/i,
  stop: /\b(stop\w*|block\w*|blocking_on)\b/i,
};
const routeKind = (route) =>
  route === "card" || route === "card_then_owner" ? "card" : route.startsWith("one line to ") ? "one_line" : route;

// S7, mechanically (DESIGN.md §4): a subject that is Baylee, and a routing verb.
// "Baylee's" counts only before a word for his say ("Baylee's opening message" routes nothing).
const SAY = "(OK|go|yes|call|review|tap|ruling|answer|say|word|approval|sign-off)";
const SUBJECT_RE = new RegExp(
  String.raw`\bBaylee\b(?!['’]s\b)|\bBaylee['’]s ${SAY}\b|\bBaylee['’]s\.|\bhis\b|\bhim\b|\bhe\b`
);
// History, not routing: Baylee as the subject of a past-tense verb with a definite object
// ("Baylee approved the list", "Baylee asked how it was derived").
const HISTORY_RE =
  /\bBaylee (approved|asked|decided|ruled|sent|said|picked|answered|chose|wrote|withdrew|confirmed|reframed|gave|named|agreed|reversed|reframed) (the|a|an|this|that|these|those|it|them|how|what|whether|why|for (the|a)|earlier|\d)\b|\bhe (approved|asked|decided|ruled|said|reframed|picked|answered|chose|withdrew|confirmed) (the|a|an|this|that|it|how|what)\b/g;
const VERB_RE =
  /\b(ask|asks|asked|asking|approve|approves|approved|approval|rules? on|ruled|ruling on|decide|decides|decided|screenshots?|wait|waits|waiting|hold|holds|held|escalate|escalates|escalated|show|shows|shown|showing|reach|reaches|reached|send|sends|sent|file|files|filed|taps?|cards?|adjudications?|say so|says so|needs?|needed|go(es)? to|bring|brings|check with|hands?|surface|surfaces|sign(s|ed)? off|sign-off|reviews|reviewed|judges?|last word|sees?|put to|ping)\b|\bOK\b/i;
const POINTER_RE = /(?<![\w-])policy:\s*([a-z][a-z0-9_]*)/g;

function args(argv) {
  const out = { root: process.cwd(), s8: true, base: null };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--root") out.root = argv[++i];
    else if (argv[i] === "--skip-s8") out.s8 = false;
    else if (argv[i] === "--base") out.base = argv[++i];
    else if (argv[i] === "--require-base") out.requireBase = true;
  }
  return out;
}

function expand(root, patterns) {
  const files = [];
  for (const p of patterns) {
    const star = p.lastIndexOf("*");
    if (star === -1) {
      if (existsSync(join(root, p))) files.push(p);
      continue;
    }
    const slash = p.lastIndexOf("/", star);
    const dir = slash === -1 ? "." : p.slice(0, slash);
    const re = new RegExp("^" + p.slice(slash + 1).replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, "[^/]*") + "$");
    if (!existsSync(join(root, dir))) continue;
    for (const f of readdirSync(join(root, dir)).sort()) if (re.test(f)) files.push(dir === "." ? f : `${dir}/${f}`);
  }
  return files.filter((f) => !NEVER_LINTED.has(f));
}

// (a)
export function checkPolicy(text) {
  const fails = [];
  let pol;
  try {
    pol = JSON.parse(text);
  } catch (e) {
    return { pol: null, fails: [`${POLICY} does not parse: ${e.message}`] };
  }
  if (!pol || typeof pol !== "object" || Array.isArray(pol)) return { pol: null, fails: [`${POLICY} is not an object`] };
  for (const k of REQUIRED) if (!(k in pol)) fails.push(`${POLICY} lacks required key "${k}"`);
  const classes = pol.classes && typeof pol.classes === "object" ? pol.classes : {};
  for (const k of ["upkeep", "direction"]) if (!(k in classes)) fails.push(`${POLICY} classes lacks "${k}"`);
  for (const [name, c] of Object.entries(classes)) {
    if (!c || typeof c.is !== "string" || !c.is) fails.push(`${POLICY} class "${name}" has no "is"`);
    if (!c || typeof c.route !== "string" || !ROUTE_RE.test(c.route))
      fails.push(`${POLICY} class "${name}" route ${JSON.stringify(c && c.route)} is not a known route`);
  }
  const table = Array.isArray(pol.decision_table) ? pol.decision_table : [];
  table.forEach((row, i) => {
    if ("then" in row && !(row.then in classes)) fails.push(`${POLICY} decision_table row ${i + 1} "then": "${row.then}" names no class`);
    if (!("then" in row) && !("else" in row)) fails.push(`${POLICY} decision_table row ${i + 1} has neither "then" nor "else"`);
  });
  if (table.length && !("else" in table[table.length - 1])) fails.push(`${POLICY} decision_table's last row is not the "else"`);
  return { pol, fails };
}

// Markdown into sentences: {line, text}. Headings and fenced code are skipped; a list item, a
// table row and a paragraph each start a new unit; a unit splits at a sentence end outside
// parentheses, quotes and code spans (so a pointer after a ";" stays with its sentence).
export function sentences(md) {
  const units = [];
  let cur = null;
  let fence = false;
  md.split("\n").forEach((raw, i) => {
    const line = raw.trimEnd();
    if (/^\s*(```|~~~)/.test(line)) {
      fence = !fence;
      cur = null;
      return;
    }
    if (fence) return;
    if (!line.trim() || /^\s*#/.test(line) || /^\s*\|?\s*-{3,}/.test(line)) {
      cur = null;
      return;
    }
    if (/^\s*([-*+]|\d+[.)])\s/.test(line) || /^\s*\|/.test(line) || !cur) {
      cur = { line: i + 1, text: line.trim() };
      units.push(cur);
    } else cur.text += " " + line.trim();
  });
  const out = [];
  for (const u of units) {
    let depth = 0, code = false, quote = false, start = 0;
    const t = u.text;
    for (let j = 0; j < t.length; j++) {
      const ch = t[j];
      if (ch === "`") code = !code;
      if (code) continue;
      if (ch === "(") depth++;
      else if (ch === ")") depth = Math.max(0, depth - 1);
      else if (ch === "“") quote = true;
      else if (ch === "”") quote = false;
      else if (ch === '"') quote = quote ? false : t.indexOf('"', j + 1) !== -1; // an inch mark opens nothing
      else if ((ch === "." || ch === "?" || ch === "!") && depth === 0 && !quote) {
        const rest = t.slice(j + 1);
        const m = rest.match(/^[*_'’"”)\]]*\s+(?=[A-Z*“"(`])/);
        if (!m || /^\s*\(`policy:/.test(rest.slice(m[0].length - 1))) continue; // a trailing pointer stays with its sentence
        const before = t.slice(start, j + 1);
        if (/\b(e\.g|i\.e|vs|etc|No|St|Dr|Mr|Ms|cf|approx)\.$/.test(before) || /\b[A-Z]\.$/.test(before)) continue;
        out.push({ line: u.line, text: before.trim() });
        start = j + 1 + m[0].length;
        j = start - 1;
      }
    }
    const tail = t.slice(start).trim();
    if (tail) out.push({ line: u.line, text: tail });
  }
  return out;
}

// What S7 reads: the sentence without quoted words, without dated or id-only parentheticals,
// and without the pointers themselves.
export function routingText(s) {
  // Quoted words are his or a screen's, unless the quote itself names him.
  const unquote = (m) => (/\b(Baylee|him|his|he)\b/.test(m) ? m : " ");
  let t = s.replace(/“[^”]*”/g, unquote).replace(/"[^"]*"/g, unquote).replace(/`[^`]*`/g, (m) => (m.includes("policy:") ? " " : m));
  t = t.replace(HISTORY_RE, " ");
  t = t.replace(/\bBaylee(['’]s (yes|go|call|ruling|rulings|note|pick|words|OK))?[,:]? \d{4}-\d{2}-\d{2}\b/g, " ");
  t = t.replace(/\b(Grove|decision|card|adjudication|ruling) [0-9a-f]{8}\b/g, " ");
  // A parenthetical is set aside only when it is an attribution: it opens with Baylee, a
  // date, an id or a migration, and runs at most 200 characters; elsewhere only the date and id
  // tokens go, so "(Grove 6e8b5c1c: ask Baylee first)" still routes.
  let prev;
  do {
    prev = t;
    t = t.replace(/\(([^()]*)\)/g, (m, inner) =>
      inner.length <= 200 &&
      /^\s*(Baylee['’]s (yes|go|call|ruling|rulings|note|pick|words|OK)\b|Baylee\b[,:]|\d{4}-\d{2}-\d{2}\b|[0-9a-f]{8}([;,\s]|$)|m\d{3,4}\b)/.test(inner)
        ? " "
        : m
    );
  } while (t !== prev);
  return t;
}

export function isRouting(s) {
  const t = routingText(s);
  return SUBJECT_RE.test(t) && VERB_RE.test(t);
}

// (b) and (c) over one file's text
// A sentence as a not_routing entry's `sentence` matches it: list marker and bold stripped.
const bare = (text) => text.replace(/^([-*+]|\d+[.)])\s+/, "").replace(/\*\*/g, "").trim();

export function lintText(file, md, classes, exempt = []) {
  const fails = [];
  const mine = exempt.filter((e) => e && e.file === file);
  const used = new Set();
  for (const { line, text } of sentences(md)) {
    const pointers = [...text.matchAll(POINTER_RE)].map((m) => m[1]);
    for (const p of pointers) {
      const c = classes[p];
      if (!c) {
        fails.push(`pointer ${file}:${line}: "policy: ${p}" names no class in ${POLICY}: ${text}`);
        continue;
      }
      const kind = routeKind(c.route);
      // "without Baylee's review" names the opposite of a card route
      const said = kind === "card" ? text.replace(/\bwithout (Baylee(['’]s)?|his|him)( \w+)?/g, " ") : text;
      if (ROUTE_CUES[kind] && !ROUTE_CUES[kind].test(said.replace(POINTER_RE, " ")))
        fails.push(`pointer ${file}:${line}: "policy: ${p}" routes ${c.route}, but the sentence names no such route: ${text}`);
    }
    const kinds = pointers.map((p) => classes[p] && routeKind(classes[p].route));
    if (kinds.length && kinds.every((k) => k === "proceed_log") && SEND_MARK.test(routingText(text)))
      fails.push(`pointer ${file}:${line}: cited only as proceed_log, but the sentence sends it to Baylee: ${text}`);
    if (!pointers.length && isRouting(text)) {
      const hit = mine.find((e) => typeof e.sentence === "string" && bare(text) === e.sentence.trim());
      if (hit) used.add(hit);
      else fails.push(`S7 ${file}:${line}: routes work to Baylee with no policy: pointer: ${text}`);
    }
  }
  for (const e of mine)
    if (!used.has(e))
      fails.push(`S7 ${file}: not_routing entry matches no flagged sentence (stale or edited; remove or update it): "${e.sentence}"`);
  return fails;
}

// (d)
function checkS8(root) {
  if (!existsSync(join(root, HANDOFF_SCRIPT))) return [`S8: ${HANDOFF_SCRIPT} missing; cannot measure the entry hook`];
  const r = spawnSync("python3", [HANDOFF_SCRIPT, "measure"], {
    cwd: root, encoding: "utf8", timeout: 60000, env: { ...process.env, CLAUDE_PROJECT_DIR: root },
  });
  const last = (r.stdout || "").trim().split("\n").pop() || "";
  let res;
  try {
    res = JSON.parse(last);
  } catch {
    return [`S8: session_handoff.py measure gave no result (exit ${r.status}): ${(r.stderr || "").trim().slice(0, 200)}`];
  }
  if (res.ok) return [];
  if (res.error) return [`S8: ${res.error}`];
  const what = [...res.cut.map((k) => `${k} cut`), ...res.omitted.map((k) => `${k} left out`)].join(", ");
  if (/lane index|progress/.test(what) && !/^lane [a-z0-9]+:/.test(what))
    return [
      `S8: with a worst-case PR table the entry hook cuts ${res.chars_cut} characters of HANDOFF.yaml's progress lines or the lane index (${what}; payload ${res.size} of ${res.limit}). ` +
        `Every lane's line rides every startup payload: shorten this lane's progress line, and say in the PR body which other lanes' lines are longest (each lane trims its own).`,
    ];
  return [
    `S8: with a worst-case PR table the entry hook cuts ${res.chars_cut} characters of ${/lane /.test(what) ? "the batons" : "HANDOFF.yaml"} (${what}; payload ${res.size} of ${res.limit}). ` +
      `Prune next: to 3-5 items and park the rest with a location (chat-archive references/handoff-schema.md).`,
  ];
}

// (e) lanes
const LANDING = ".claude/landing.yaml";
const LANE_FILE = /^lane-([a-z][a-z0-9]*)\.yaml$/;
const PROGRESS_LINE_MAX = 200; // every lane's line rides every startup payload: 7 lines of 220 already fill S8 (docs/lanes/DESIGN.md §7)
const BATON_KEYS = ["next", "done", "carried_forward", "decisions_made", "parked", "watch_outs", "blocking_on"];

// Layout checks over the working tree's HANDOFF.yaml and lane file names.
export function checkLaneLayout(handoff, laneFileNames, lanes) {
  const fails = [];
  if (handoff !== null) {
    const top = [...handoff.matchAll(/^([a-z_]+):/gm)].map((m) => m[1]);
    for (const k of new Set(top.filter((k, i) => top.indexOf(k) !== i)))
      fails.push(`lanes: HANDOFF.yaml has two top-level \`${k}:\` keys; a YAML reader keeps only the last one`);
    for (const k of top)
      if (!["meta", "progress"].includes(k))
        fails.push(`lanes: HANDOFF.yaml has a top-level \`${k}:\`; with lanes declared it holds only meta and progress` +
          (BATON_KEYS.includes(k) ? ` (${k} belongs in handoffs/lane-<x>.yaml)` : ""));
    const entries = progressEntries(handoff);
    entries.forEach((e, j) => {
      if (!lanes.includes(e.key)) fails.push(`lanes: HANDOFF.yaml progress key \`${e.key}\` is not a declared lane (${lanes.join(", ")})`);
      if (e.line.length > PROGRESS_LINE_MAX)
        fails.push(`lanes: HANDOFF.yaml progress line \`${e.key}\` is ${e.line.length} characters (at most ${PROGRESS_LINE_MAX}; the detail goes in handoffs/lane-${e.key}.yaml)`);
      if (j > 0 && e.index === entries[j - 1].index + 1)
        fails.push(`lanes: HANDOFF.yaml progress keys \`${entries[j - 1].key}\` and \`${e.key}\` are adjacent: put a blank line between them (adjacent edits from two lanes conflict)`);
    });
  }
  for (const f of laneFileNames) {
    const m = f.match(LANE_FILE);
    if (m && !lanes.includes(m[1])) fails.push(`lanes: handoffs/${f} names lane \`${m[1]}\`, which .claude/landing.yaml does not declare`);
  }
  return fails;
}

// The lanes a change touches: lane files changed, and progress keys whose line differs from the base.
export function touchedLanes(changedPaths, baseHandoff, handoff) {
  const out = new Set();
  for (const p of changedPaths) {
    const m = p.match(/^handoffs\/lane-([a-z][a-z0-9]*)\.yaml$/);
    if (m) out.add(m[1]);
  }
  const before = new Map(progressEntries(baseHandoff).map((e) => [e.key, e.line]));
  const after = new Map(progressEntries(handoff).map((e) => [e.key, e.line]));
  for (const k of new Set([...before.keys(), ...after.keys()])) if (before.get(k) !== after.get(k)) out.add(k);
  return [...out].sort();
}

function checkLanes(root, base, requireBase = false) {
  const fails = [];
  const notes = [];
  const read = (p) => (existsSync(join(root, p)) ? readFileSync(join(root, p), "utf8") : null);
  const lanes = declaredLanes(read(LANDING));
  const dir = join(root, "handoffs");
  const laneFiles = existsSync(dir) ? readdirSync(dir).filter((f) => LANE_FILE.test(f)).sort() : [];
  if (!lanes.length) {
    if (laneFiles.length) fails.push(`lanes: handoffs/${laneFiles[0]} exists but .claude/landing.yaml declares no lanes`);
    return { fails, notes };
  }
  const handoff = read("HANDOFF.yaml");
  fails.push(...checkLaneLayout(handoff, laneFiles, lanes));
  const g = (args) => spawnSync("git", args, { cwd: root, encoding: "utf8", maxBuffer: 1 << 26 });
  const ref = base || "origin/main";
  if (g(["rev-parse", "-q", "--verify", `${ref}^{commit}`]).status !== 0) {
    (requireBase ? fails : notes).push(`lanes: cross-lane check ${requireBase ? "cannot run" : "skipped"}: base ${ref} not found (fetch it, or pass --base)`);
    return { fails, notes };
  }
  const mb = (g(["merge-base", ref, "HEAD"]).stdout || "").trim() || ref;
  const at = (p) => {
    const r = g(["show", `${mb}:${p}`]);
    return r.status === 0 ? r.stdout : null;
  };
  const baseLanes = declaredLanes(at(LANDING));
  if (!baseLanes.length) {
    notes.push(`lanes: cross-lane check skipped: the base declares no lanes (the migration)`);
    return { fails, notes };
  }
  if (baseLanes.join(",") !== lanes.join(",")) {
    notes.push(`lanes: cross-lane check skipped: this change edits the lane list (${baseLanes.join(", ")} → ${lanes.join(", ")})`);
    return { fails, notes };
  }
  const changed = [
    ...(g(["diff", "--name-only", mb]).stdout || "").split("\n"),
    ...(g(["ls-files", "--others", "--exclude-standard", "--", "handoffs"]).stdout || "").split("\n"),
  ].filter(Boolean);
  const touched = touchedLanes(changed, at("HANDOFF.yaml"), handoff);
  if (touched.length > 1)
    fails.push(`lanes: this change edits the batons of lanes ${touched.join(", ")} (against ${ref}); a lane writes only its own ` +
      `handoffs/lane-<x>.yaml and its own progress line. After a merge of main, resolve with handoff-merge.mjs --lane <x>.`);
  return { fails, notes };
}

export function run(root, { s8 = true, base = null, requireBase = false } = {}) {
  const fails = [];
  const ppath = join(root, POLICY);
  if (!existsSync(ppath)) return { fails: [`${POLICY} missing: this repo has no routing policy to check against`], files: [] };
  const { pol, fails: pf } = checkPolicy(readFileSync(ppath, "utf8"));
  fails.push(...pf);
  const classes = (pol && pol.classes) || {};
  const sig = pol && pol.signals && pol.signals.S7_uncited_routing_sentences;
  const patterns = sig && Array.isArray(sig.files) && sig.files.length ? sig.files : null;
  if (sig && !patterns) fails.push(`${POLICY} signals.S7_uncited_routing_sentences.files is empty: S7 would check nothing`);
  const files = expand(root, patterns || DEFAULT_FILES);
  if (!files.length) fails.push(`S7: no rule file matches ${JSON.stringify(patterns || DEFAULT_FILES)}: S7 would check nothing`);
  for (const p of patterns || DEFAULT_FILES)
    if (!p.includes("*") && !files.includes(p) && !NEVER_LINTED.has(p)) fails.push(`S7: rule file ${p} is missing`);
  const exempt = sig && Array.isArray(sig.not_routing) ? sig.not_routing : [];
  for (const e of exempt)
    if (!e || typeof e.file !== "string" || typeof e.sentence !== "string" || typeof e.why !== "string" || !e.why.trim())
      fails.push(`${POLICY} signals.S7_uncited_routing_sentences.not_routing entry needs file, sentence and why: ${JSON.stringify(e)}`);
    else if (!files.includes(e.file)) fails.push(`S7: not_routing entry names ${e.file}, which is not a linted rule file`);
  for (const f of files) fails.push(...lintText(f, readFileSync(join(root, f), "utf8"), classes, exempt));
  if (s8) fails.push(...checkS8(root));
  const lanes = checkLanes(root, base, requireBase);
  fails.push(...lanes.fails);
  return { fails, files, notes: lanes.notes };
}

const isMain = (() => {
  try {
    return !!process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url));
  } catch {
    return false;
  }
})();
if (isMain) {
  const a = args(process.argv.slice(2));
  const { fails, files, notes = [] } = run(a.root, a);
  for (const n of notes) console.log(`note ${n}`);
  for (const f of fails) console.log(`FAIL ${f}`);
  if (fails.length) {
    console.log(`policy-check: ${fails.length} failure(s) in ${relative(process.cwd(), a.root) || "."} (${files.length} rule files). ${STRICTER}`);
    process.exit(1);
  }
  console.log(`policy-check: ok (${POLICY}, ${files.length} rule files${a.s8 ? ", S8" : ""})`);
}
