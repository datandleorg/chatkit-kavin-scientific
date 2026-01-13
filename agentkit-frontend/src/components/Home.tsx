import { useCallback, useState } from "react";
import clsx from "clsx";

import { ChatKitPanel } from "./ChatKitPanel";
import { ThemeToggle } from "./ThemeToggle";
import { useCustomerContext } from "../hooks/useCustomerContext";
import type { ColorScheme } from "../hooks/useColorScheme";

type HomeProps = {
  scheme: ColorScheme;
  onThemeChange: (scheme: ColorScheme) => void;
};

export default function Home({ scheme, onThemeChange }: HomeProps) {
  const [threadId, setThreadId] = useState<string | null>(null);
  const {  refresh } = useCustomerContext(threadId);

  const containerClass = clsx(
    "h-screen w-full bg-gradient-to-br transition-colors duration-300 overflow-hidden",
    scheme === "dark"
      ? "from-slate-950 via-slate-950 to-slate-900 text-slate-100"
      : "from-slate-100 via-white to-slate-200 text-slate-900",
  );

  const handleThreadChange = useCallback((nextThreadId: string | null) => {
    setThreadId(nextThreadId);
  }, []);

  const handleResponseCompleted = useCallback(() => {
    void refresh();
  }, [refresh]);

  return (
    <div 
      className={containerClass}
      style={{
        height: '100vh',
        minHeight: '-webkit-fill-available',
      }}
    >
      <div className="mx-auto flex h-full w-full max-w-full flex-col gap-0 px-0 py-0 sm:gap-2 sm:px-2 sm:py-2 lg:gap-4 lg:px-4 lg:py-4">
        <div className="flex flex-1 flex-col gap-0 min-h-0 sm:gap-2 lg:gap-4 overflow-hidden" style={{ height: '100%', minHeight: 0 }}>
          <section 
            className="flex flex-1 flex-col overflow-hidden min-h-0 rounded-none sm:rounded-xl lg:rounded-3xl bg-white/80 shadow-none sm:shadow-[0_45px_90px_-45px_rgba(15,23,42,0.6)] ring-0 sm:ring-1 ring-slate-200/60 backdrop-blur dark:bg-slate-900/70 dark:shadow-none sm:dark:shadow-[0_45px_90px_-45px_rgba(15,23,42,0.85)] dark:ring-0 sm:dark:ring-slate-800/60"
            style={{ height: '100%', minHeight: 0 }}
          >
            <div className="flex flex-1 min-w-0 min-h-0 overflow-hidden" style={{ height: '100%', minHeight: 0 }}>
              <ChatKitPanel
                theme={scheme}
                onThreadChange={handleThreadChange}
                onResponseCompleted={handleResponseCompleted}
              />
            </div>
          </section>

        </div>
      </div>
    </div>
  );
}
