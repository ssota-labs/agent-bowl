export const DOC_KINDS = ['PRD', 'US', 'PLAN', 'SPEC', 'ADR'] as const;

export type DocKindName = (typeof DOC_KINDS)[number];

/** Infer a document kind from the conventional Oh My Docs catalog path. */
export function docKindFromSlug(slug: readonly string[] | undefined): DocKindName | null {
  if (!slug?.length) return null;

  const [section, catalog] = slug;
  if (section === 'planning' && catalog === 'prds' && slug.length > 2) return 'PRD';
  if (section === 'planning' && catalog === 'stories' && slug.length > 2) return 'US';
  if (section === 'development' && catalog === 'plans' && slug.length > 2) return 'PLAN';
  if (section === 'development' && catalog === 'adr' && slug.length > 2) return 'ADR';
  if (section === 'spec' && slug.length >= 2) return 'SPEC';
  return null;
}
