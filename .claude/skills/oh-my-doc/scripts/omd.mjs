#!/usr/bin/env node
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { adoptProject, syncProject } from '../runtime/adopt.mjs';
import { applyFileOperations } from '../runtime/fs-ops.mjs';
import { inspectProject } from '../runtime/inspect.mjs';
import { planCreateDocument } from '../runtime/create-document.mjs';
import { doctorProject } from '../runtime/doctor.mjs';
import { validatePlanning } from '../runtime/planning.mjs';
import { readProject, readState, digest, stableStringify } from '../runtime/omd-contract.mjs';
import { DEFAULT_UI_VOCABULARY } from '../runtime/omd-contract.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = resolve(__dirname, '..');
const TEMPLATE_ROOT = join(SKILL_ROOT, 'templates/default');
const SCHEMAS_DIR = join(SKILL_ROOT, 'schemas');

/**
 * @param {readonly string[]} argv
 */
function parseArgs(argv) {
  const args = [...argv];
  const action = args.shift();
  /** @type {Record<string, string | boolean>} */
  const flags = {};
  /** @type {string[]} */
  const positionals = [];
  while (args.length > 0) {
    const token = args.shift();
    if (!token) break;
    if (token.startsWith('--')) {
      const key = token.slice(2);
      if (key === 'dry-run' || key === 'yes' || key === 'json' || key === 'force') {
        flags[key] = true;
        continue;
      }
      const next = args.shift();
      if (!next || next.startsWith('--')) {
        throw new Error(`Missing value for --${key}`);
      }
      flags[key] = next;
      continue;
    }
    positionals.push(token);
  }
  return { action, flags, positionals };
}

function printJson(value) {
  console.log(JSON.stringify(value, null, 2));
}

/**
 * @param {readonly string[]} argv
 */
export async function main(argv = process.argv.slice(2)) {
  let parsed;
  try {
    parsed = parseArgs(argv);
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
    return;
  }

  const { action, flags, positionals } = parsed;
  if (!action || action === 'help' || action === '--help') {
    printHelp();
    return;
  }

  const cwd = resolve(process.cwd(), typeof flags.directory === 'string' ? flags.directory : positionals[0] && action === 'adopt' ? positionals[0] : '.');
  const json = flags.json === true;
  const dryRun = flags['dry-run'] === true;
  const force = flags.force === true;
  const yes = flags.yes === true;

  try {
    switch (action) {
      case 'inspect': {
        const report = inspectProject({
          cwd,
          ...(typeof flags['ui-path'] === 'string' ? { uiPath: flags['ui-path'] } : {}),
        });
        if (json) printJson(report);
        else {
          console.log(`mode: ${report.mode}`);
          console.log(`docs: ${report.project.docsPath ?? '(none)'}`);
          console.log(`ui: ${report.project.uiPath ?? '(none)'}`);
          console.log(`.omd: ${report.omd.present ? 'present' : 'missing'}`);
          console.log(`recommended: ${report.recommended.join(', ')}`);
          for (const note of report.doctor.notes) console.log(`- ${note}`);
        }
        if (!report.doctor.ok && report.mode !== 'greenfield') process.exitCode = 1;
        return;
      }
      case 'adopt': {
        if (!dryRun && !yes) {
          console.error('Refusing to write without --yes (or use --dry-run).');
          process.exitCode = 1;
          return;
        }
        const target = resolve(process.cwd(), positionals[0] ?? '.');
        const result = adoptProject({
          cwd: target,
          templateRoot: TEMPLATE_ROOT,
          skillRoot: SKILL_ROOT,
          schemasDir: SCHEMAS_DIR,
          dryRun,
          force,
          ...(typeof flags['ui-path'] === 'string' ? { uiPath: flags['ui-path'] } : {}),
          ...(typeof flags['package-manager'] === 'string'
            ? { packageManager: flags['package-manager'] }
            : {}),
        });
        if (json) printJson(result);
        else {
          console.log(`adopt ${result.mode}${dryRun ? ' (dry-run)' : ''}`);
          console.log(`operations: ${result.operations.length}, conflicts: ${result.conflicts.length}`);
          if (result.applied) {
            console.log(`applied: ${result.applied.applied.length}, skipped: ${result.applied.skipped.length}`);
          }
        }
        if (result.conflicts.length > 0 && !force) process.exitCode = 2;
        return;
      }
      case 'new': {
        const kind = positionals[0];
        const title = flags.title;
        if (!kind || typeof title !== 'string') {
          console.error('Usage: omd.mjs new <prd|story|spec|plan|adr> --title "..." [--id ID] --yes');
          process.exitCode = 1;
          return;
        }
        if (!dryRun && !yes) {
          console.error('Refusing to write without --yes (or use --dry-run).');
          process.exitCode = 1;
          return;
        }
        const planned = planCreateDocument({
          cwd,
          kind,
          title,
          ...(typeof flags.id === 'string' ? { id: flags.id } : {}),
          ...(typeof flags['docs-path'] === 'string' ? { docsPath: flags['docs-path'] } : {}),
        });
        if (planned.validationProblems.length > 0) {
          if (json) printJson({ ok: false, planned, problems: planned.validationProblems });
          else {
            console.error('Created document would fail planning validation:');
            for (const problem of planned.validationProblems) console.error(`- ${problem}`);
          }
          process.exitCode = 1;
          return;
        }
        const result = applyFileOperations(cwd, planned.operations, { dryRun, force });
        if (json) printJson({ ok: true, planned, result });
        else {
          console.log(`Create ${planned.kind} ${planned.id} → ${planned.relativePath}`);
          console.log(`applied: ${result.applied.length}, skipped: ${result.skipped.length}`);
        }
        return;
      }
      case 'check': {
        const report = doctorProject({ cwd });
        const docsPath =
          typeof flags['docs-path'] === 'string' ? flags['docs-path'] : report.project.docsPath;
        const problems = [];
        if (!docsPath) problems.push('No docs app found (expected docs/ or apps/docs/).');
        else {
          const contentDirectory = resolve(cwd, docsPath, 'content/docs');
          problems.push(...validatePlanning(contentDirectory));
        }
        const contract = readProject(cwd);
        const state = readState(cwd);
        if (contract) {
          if (contract.ui?.base !== 'fumadocs') {
            problems.push('.omd/project.json ui.base must be fumadocs');
          }
          if (contract.ui?.distribution !== 'skill-template') {
            problems.push('.omd/project.json ui.distribution must be skill-template');
          }
          if (!Array.isArray(contract.ui?.shellDependencies) || !contract.ui.shellDependencies.includes('fumadocs-ui')) {
            problems.push('.omd/project.json ui.shellDependencies must include fumadocs-ui');
          }
          const declared = new Set((contract.ui?.vocabulary ?? []).map((item) => item.name));
          for (const item of DEFAULT_UI_VOCABULARY) {
            if (!declared.has(item.name) && item.surface !== 'fumadocs-mdx') {
              problems.push(`UI vocabulary missing declared component: ${item.name}`);
            }
          }
          if (state && digest(stableStringify(contract)) !== state.projectDigest) {
            problems.push('.omd/state.json projectDigest does not match project.json');
          }
        } else {
          problems.push('.omd/project.json is missing — run adopt first');
        }
        const ok = problems.length === 0;
        if (json) printJson({ ok, problems, doctor: report });
        else if (!ok) {
          console.error(`check found ${problems.length} problem(s):`);
          for (const problem of problems) console.error(`- ${problem}`);
        } else {
          console.log('Planning graph, .omd contract, and UI vocabulary look valid.');
        }
        if (!ok) process.exitCode = 1;
        return;
      }
      case 'sync': {
        if (!dryRun && !yes) {
          console.error('Refusing to write without --yes (or use --dry-run).');
          process.exitCode = 1;
          return;
        }
        const result = syncProject({
          cwd,
          dryRun,
          force,
          schemasDir: SCHEMAS_DIR,
        });
        if (json) printJson(result);
        else {
          console.log(`sync${dryRun ? ' (dry-run)' : ''}: ${result.operations.length} operation(s)`);
        }
        return;
      }
      default:
        console.error(`Unknown action: ${action}`);
        printHelp();
        process.exitCode = 1;
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (json) printJson({ ok: false, error: message });
    else console.error(message);
    process.exitCode = 1;
  }
}

function printHelp() {
  console.log(`Oh My Docs runtime

Usage:
  node scripts/omd.mjs <action> [options]

Actions:
  inspect   Report project mode, docs/UI/.omd state
  adopt     Greenfield scaffold or brownfield import
  new       Create prd|story|spec|plan|adr
  check     Validate planning graph + .omd contract
  sync      Refresh managed IA/markers from .omd

Common flags:
  --json --dry-run --yes --force
  --ui-path <path> --docs-path <path> --title <title> --id <id>
`);
}

const isDirect =
  process.argv[1] &&
  (process.argv[1].endsWith('/omd.mjs') ||
    process.argv[1].endsWith('\\omd.mjs') ||
    process.argv[1].endsWith('/run.mjs') ||
    process.argv[1].endsWith('\\run.mjs'));

if (isDirect) {
  await main();
}
