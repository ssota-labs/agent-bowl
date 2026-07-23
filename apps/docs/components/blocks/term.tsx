import { z } from 'zod';

/**
 * A Ubiquitous Language entry.
 *
 * Domain glossary cards lead with the business meaning anyone on the team can
 * read. The optional `tech` slot pins where the same word lives in code/CLI so
 * the two vocabularies cannot drift apart.
 */
export const termSchema = z.object({
  term: z.string().min(1),
  /** The Korean the user actually says — shown as the card title when present. */
  ko: z.string().optional(),
  /** Where it lives in the code: a type, function, or column name. */
  code: z.string().optional(),
  /** Terms this is easily confused with. Usually the most useful line. */
  notTo: z.string().optional(),
});

export type TermProps = z.infer<typeof termSchema> & {
  children?: React.ReactNode;
  /** Implementation / CLI detail — shown under a 개발 section. */
  tech?: React.ReactNode;
};

export function Term(props: TermProps) {
  const { term, ko, code, notTo, children, tech } = props;
  const id = term.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  const title = ko ?? term;
  const english = ko ? term : undefined;

  return (
    <div id={id} className="not-prose bg-fd-card rounded-lg border">
      <div className="flex flex-wrap items-baseline gap-2 border-b px-4 py-3">
        <h4 className="font-semibold">{title}</h4>
        {english ? (
          <span className="text-fd-muted-foreground font-mono text-sm">{english}</span>
        ) : null}
        {code ? (
          <code className="bg-fd-muted rounded px-1.5 py-0.5 font-mono text-xs">{code}</code>
        ) : null}
      </div>

      {children ? (
        <div className="px-4 py-3">
          <p className="text-fd-muted-foreground mb-1.5 text-[11px] font-semibold tracking-wide uppercase">
            의미
          </p>
          <div className="prose-sm text-fd-foreground [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
            {children}
          </div>
        </div>
      ) : null}

      {tech ? (
        <div className="border-t px-4 py-3">
          <p className="text-fd-muted-foreground mb-1.5 text-[11px] font-semibold tracking-wide uppercase">
            개발
          </p>
          <div className="prose-sm text-fd-muted-foreground [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
            {tech}
          </div>
        </div>
      ) : null}

      {notTo ? (
        <p className="text-fd-muted-foreground border-t px-4 py-3 text-sm">
          <span className="text-fd-foreground font-medium">혼동 주의:</span> {notTo}
        </p>
      ) : null}
    </div>
  );
}

export function Glossary({ children }: { children?: React.ReactNode }) {
  return <div className="not-prose my-6 flex flex-col gap-3">{children}</div>;
}
