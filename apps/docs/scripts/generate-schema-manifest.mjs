#!/usr/bin/env node
/**
 * Placeholder. holiday generates this from store-sqlite migrations.
 * agent-bowl keeps an empty generated/schema-manifest.json until a schema exists.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const out = join(root, 'generated', 'schema-manifest.json');
mkdirSync(dirname(out), { recursive: true });
writeFileSync(
  out,
  `${JSON.stringify(
    {
      metadata: {
        latestMigration: null,
        snapshotPath: null,
        schemaSourcePath: null,
        generatorPath: 'apps/docs/scripts/generate-schema-manifest.mjs',
      },
      tables: [],
      foreignKeys: [],
    },
    null,
    2,
  )}\n`,
);
console.log(`wrote ${out}`);
