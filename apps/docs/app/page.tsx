import Link from 'next/link';

export default function Home() {
  return (
    <main className="mx-auto flex max-w-2xl flex-1 flex-col justify-center gap-4 px-6">
      <h1 className="text-3xl font-semibold">agent-bowl</h1>
      <p className="text-fd-muted-foreground">
        독립 에이전트 패키지를 발견하고 App으로 조합하는 레지스트리·플랫폼.
      </p>
      <Link className="text-fd-primary underline underline-offset-4" href="/docs">
        문서 읽기 →
      </Link>
    </main>
  );
}
