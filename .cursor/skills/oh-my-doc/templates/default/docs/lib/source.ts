import { docs } from 'collections/server';
import { loader } from 'fumadocs-core/source';
import { createCatalogNavigation, indexOnlyPageTree } from '@oh-my-docs/ui/navigation';

const CATALOGS = [
  { prefix: ['planning', 'prds'], indexUrl: '/docs/planning/prds', label: 'PRD' },
  { prefix: ['planning', 'stories'], indexUrl: '/docs/planning/stories', label: 'User stories' },
  {
    prefix: ['development', 'plans'],
    indexUrl: '/docs/development/plans',
    label: 'Implementation plans',
  },
  { prefix: ['development', 'adr'], indexUrl: '/docs/development/adr', label: 'ADR' },
] as const;

export const source = loader({
  baseUrl: '/docs',
  source: docs.toFumadocsSource(),
  pageTree: indexOnlyPageTree(CATALOGS.map((catalog) => catalog.indexUrl)),
});

const catalogNavigation = createCatalogNavigation(source, CATALOGS);

export const catalogIndexLink = catalogNavigation.indexLink;
export const catalogFooterItems = catalogNavigation.footerItems;
