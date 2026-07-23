import Link from 'next/link';

export default function Home() {
  return (
    <main className="mx-auto flex max-w-2xl flex-1 flex-col justify-center gap-5 px-6">
      <p className="text-fd-muted-foreground text-sm font-medium">Docs-first by design</p>
      <h1 className="text-4xl font-semibold tracking-tight">Product handbook</h1>
      <p className="text-fd-muted-foreground text-lg">
        Intent, decisions, contracts, and plans live here before code.
      </p>
      <Link className="text-fd-primary w-fit underline underline-offset-4" href="/docs">
        Open the handbook →
      </Link>
    </main>
  );
}
