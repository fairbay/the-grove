#!/usr/bin/env node
// handoff-merge.mjs: resolve a merge of main whose only conflicts are handoff files, mechanically (fairbay/ops
// docs/lanes/DESIGN.md §3.3). Synced into every repo with the chat-archive skill. Run from the repo root, mid-merge:
//
//   git fetch origin main && git merge origin/main      # conflicts stop the merge
//   node .claude/skills/chat-archive/scripts/handoff-merge.mjs --lane <x> [--no-commit]
//
// For each conflicted path:
//   handoffs/lane-<x>.yaml        the branch's copy (this lane's baton is this session's to write)
//   handoffs/lane-<other>.yaml    main's copy (another lane's baton is never this session's)
//   HANDOFF.yaml                  main's copy, with the branch's own `progress:` line for <x> spliced back; a branch
//                                 whose HANDOFF.yaml predates the split (a top-level `next:`) gets main's as is, and the
//                                 session writes its baton again with `session_handoff.py write --lane <x>`
//   anything else                 left conflicted and listed; exit 1 (code, resolved as code)
// Refused (left conflicted, exit 1): main changed this lane's own file or progress line since the merge base. Lanes run
// one session at a time, so that is another session's baton; taking the branch's copy would drop it silently. A re-run
// changes nothing until the session has read main's copy and rewritten its baton on top of it.
// When every conflict is resolved it commits the merge (unless --no-commit). Exit 0 when nothing is left conflicted,
// 1 when other paths are, 2 on a usage error (no merge in progress, no --lane, a lane landing.yaml does not declare). Dependency-free (Node's own modules).

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const LANE_FILE = /^handoffs\/lane-([a-z][a-z0-9]*)\.yaml$/;

const git = (args, opts = {}) => execFileSync("git", args, { encoding: "utf8", maxBuffer: 1 << 26, ...opts });

// The lane ids a landing.yaml text declares (`lanes: [a, c]` or a block list); YAML booleans are not ids.
const NOT_IDS = new Set(["y", "n", "yes", "no", "on", "off", "true", "false", "null"]);
export function declaredLanes(text) {
  if (!text) return [];
  let items = [];
  const inline = text.match(/^lanes:[ \t]*\[([^\]]*)\]/m);
  if (inline) items = inline[1].split(",");
  else {
    const lines = text.split("\n");
    const i = lines.findIndex((l) => /^lanes:[ \t]*(#.*)?$/.test(l));
    if (i !== -1)
      for (const l of lines.slice(i + 1)) {
        const m = l.match(/^\s+-\s+([^\s#]+)/);
        if (!m) break;
        items.push(m[1]);
      }
  }
  const out = [];
  for (const raw of items) {
    const x = raw.trim().replace(/^['"]|['"]$/g, "").toLowerCase();
    if (/^[a-z][a-z0-9]{0,15}$/.test(x) && !NOT_IDS.has(x) && !out.includes(x)) out.push(x);
  }
  return out;
}

// Every `  <key>: …` line of the `progress:` section, in order, with its line index (policy-check (e) reads these too).
export function progressEntries(text) {
  const lines = (text || "").split("\n");
  const start = lines.findIndex((l) => /^progress:\s*(#.*)?$/.test(l));
  const out = [];
  if (start === -1) return out;
  for (let i = start + 1; i < lines.length; i++) {
    if (/^[a-z_]+:/.test(lines[i])) break;
    const m = lines[i].match(/^  ([a-z][a-z0-9_]*):(\s|$)/);
    if (m) out.push({ key: m[1], line: lines[i], index: i });
  }
  return out;
}

const keyRe = (lane) => new RegExp(`^  ${lane}:(\\s|$)`);

// The `  <x>: …` line under `progress:` in a HANDOFF.yaml text, or null.
export function progressLine(text, lane) {
  const hit = progressEntries(text).find((e) => e.key === lane);
  return hit ? hit.line : null;
}

// main's HANDOFF.yaml text with this lane's progress line set to `line` (replaced in place, or added after the
// section's last line with a blank line before it, so lane keys are never adjacent). null line: main's text as is.
export function spliceProgress(text, lane, line) {
  if (!line) return text;
  const lines = text.replace(/\n$/, "").split("\n");
  let start = lines.findIndex((l) => /^progress:\s*(#.*)?$/.test(l));
  if (start === -1) {
    while (lines.length && !lines[lines.length - 1].trim()) lines.pop();
    lines.push("", "progress:", line);
    return lines.join("\n") + "\n";
  }
  let end = lines.length;
  for (let i = start + 1; i < lines.length; i++) if (/^[a-z_]+:/.test(lines[i])) { end = i; break; }
  const hit = lines.slice(start + 1, end).findIndex((l) => keyRe(lane).test(l));
  if (hit !== -1) lines[start + 1 + hit] = line;
  else {
    let last = start;
    for (let i = start; i < end; i++) if (lines[i].trim()) last = i;
    lines.splice(last + 1, 0, ...(last === start ? [line] : ["", line]));
  }
  return lines.join("\n") + "\n";
}

// What to do with one conflicted path: "ours" | "theirs" | "handoff" | null (not a handoff file).
export function plan(path, lane) {
  if (path === "HANDOFF.yaml") return "handoff";
  const m = path.match(LANE_FILE);
  if (!m) return null;
  return m[1] === lane ? "ours" : "theirs";
}

function stage(n, path, cwd) {
  try {
    return git(["show", `:${n}:${path}`], { cwd, stdio: ["ignore", "pipe", "ignore"] });
  } catch {
    return null; // the side deleted it, or the path has no such stage
  }
}

export function run({ lane, commit = true, cwd = process.cwd() }) {
  const g = (args) => git(args, { cwd });
  try {
    git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], { cwd, stdio: ["ignore", "pipe", "ignore"] });
  } catch {
    return { code: 2, lines: ["handoff-merge: no merge in progress (run git merge origin/main first)"] };
  }
  const landing = join(cwd, ".claude/landing.yaml");
  const lanes = declaredLanes(existsSync(landing) ? readFileSync(landing, "utf8") : "");
  if (!lanes.includes(lane))
    return { code: 2, lines: [`handoff-merge: lane ${lane} is not declared in .claude/landing.yaml (${lanes.join(", ") || "no lanes"})`] };
  const conflicted = g(["diff", "--name-only", "--diff-filter=U"]).split("\n").filter(Boolean);
  const lines = [];
  const left = [];
  for (const path of conflicted) {
    const what = plan(path, lane);
    if (!what) {
      left.push(path);
      continue;
    }
    if (what === "handoff") {
      const theirs = stage(3, path, cwd);
      const ours = stage(2, path, cwd);
      if (theirs === null) {
        left.push(path);
        continue;
      }
      const base = stage(1, path, cwd);
      const oldBase = base !== null && /^next:/m.test(base); // a branch cut before the split: no lane line to protect
      if (base !== null && !oldBase && progressLine(base, lane) !== progressLine(theirs, lane)) {
        left.push(`${path} (main changed lane ${lane}'s own progress line)`);
        continue;
      }
      const oldLayout = ours !== null && /^next:/m.test(ours);
      const mine = ours === null || oldLayout ? null : progressLine(ours, lane);
      const text = spliceProgress(theirs, lane, mine);
      if (oldLayout) {
        const lines0 = ours.split("\n");
        const i = lines0.findIndex((l) => /^next:/.test(l));
        let j = i + 1;
        while (j < lines0.length && !/^[a-z_]+:/.test(lines0[j])) j++;
        lines.push(`${path}: the branch's copy predates the split. Its own next: is below; carry what is this lane's into ` +
          `session_handoff.py write --lane ${lane}, the rest into Grove tasks tagged by lane:\n${lines0.slice(i, j).join("\n").trimEnd()}`);
      }
      writeFileSync(join(cwd, path), text);
      g(["add", "--", path]);
      lines.push(`resolved ${path}: main's, with lane ${lane}'s progress line ${mine ? "kept" : "(none on the branch)"}`);
      continue;
    }
    if (what === "ours") {
      const base = stage(1, path, cwd);
      if (base !== stage(3, path, cwd)) {
        left.push(`${path} (main changed this lane's own baton since the merge base)`);
        continue;
      }
    }
    const side = what === "ours" ? 2 : 3;
    if (stage(side, path, cwd) === null) {
      g(["rm", "-q", "--", path]);
      lines.push(`resolved ${path}: deleted (as on ${what === "ours" ? "the branch" : "main"})`);
      continue;
    }
    g(["checkout", `--${what}`, "--", path]);
    g(["add", "--", path]);
    lines.push(`resolved ${path}: ${what === "ours" ? "the branch's (this lane)" : "main's (another lane)"}`);
  }
  if (left.length) {
    lines.push(`left conflicted: ${left.join(", ")}. Code is resolved as code; a lane baton main changed is read and rewritten on top of main's; then commit the merge`);
    return { code: 1, lines };
  }
  if (commit) {
    g(["commit", "-q", "--no-edit"]);
    lines.push(`merge committed (lane ${lane}'s baton kept, other lanes from main)`);
  }
  return { code: 0, lines };
}

const isMain = (() => {
  try {
    return !!process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url));
  } catch {
    return false;
  }
})();
if (isMain) {
  const argv = process.argv.slice(2);
  const i = argv.indexOf("--lane");
  const lane = i !== -1 ? (argv[i + 1] || "").toLowerCase() : "";
  if (!/^[a-z][a-z0-9]*$/.test(lane)) {
    console.error("usage: handoff-merge.mjs --lane <x> [--no-commit]");
    process.exit(2);
  }
  const { code, lines } = run({ lane, commit: !argv.includes("--no-commit") });
  for (const l of lines) console.log(l);
  process.exit(code);
}
