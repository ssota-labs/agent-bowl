import assert from 'node:assert/strict';
import test from 'node:test';

import { docKindFromSlug } from './doc-kinds.ts';

test('infers kinds only for catalog detail pages', () => {
  assert.equal(docKindFromSlug(['planning', 'prds', 'prd-editor']), 'PRD');
  assert.equal(docKindFromSlug(['planning', 'stories', 'us-editor']), 'US');
  assert.equal(docKindFromSlug(['development', 'plans', 'plan-editor']), 'PLAN');
  assert.equal(docKindFromSlug(['development', 'adr', 'adr-001']), 'ADR');
  assert.equal(docKindFromSlug(['spec', 'editor']), 'SPEC');
  assert.equal(docKindFromSlug(['planning', 'prds']), null);
  assert.equal(docKindFromSlug(undefined), null);
});
