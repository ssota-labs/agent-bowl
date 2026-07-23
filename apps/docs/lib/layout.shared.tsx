import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';

export function baseOptions(): BaseLayoutProps {
  return {
    nav: {
      title: (
        <>
          <span className="font-semibold">agent-bowl</span>
          <span className="text-fd-muted-foreground ml-2 text-xs">에이전트 패키지 레지스트리</span>
        </>
      ),
    },
    githubUrl: 'https://github.com/ssota-labs/agent-bowl',
  };
}
