import { ChatKit, useChatKit, type UseChatKitOptions } from "@openai/chatkit-react";
import type { ColorScheme } from "../hooks/useColorScheme";
import {
  SUPPORT_CHATKIT_API_DOMAIN_KEY,
  SUPPORT_CHATKIT_API_URL,
  SUPPORT_GREETING,
  SUPPORT_STARTER_PROMPTS,
} from "../lib/config";

type ChatKitPanelProps = {
  theme: ColorScheme;
  onThreadChange: (threadId: string | null) => void;
  onResponseCompleted: () => void;
};

export function ChatKitPanel({
  theme,
  onThreadChange,
  onResponseCompleted,
}: ChatKitPanelProps) {

  const options: UseChatKitOptions = {
    api: {
      url: SUPPORT_CHATKIT_API_URL,
      domainKey: SUPPORT_CHATKIT_API_DOMAIN_KEY,
      uploadStrategy: { type: 'two_phase' },
    },
    theme: {
      colorScheme: theme,
      radius: "soft",
      density: "spacious",
      color: {
        grayscale: {
          hue: 0,
          tint: 0,
          shade: theme === "dark" ? -1 : -4,
        },
        accent: {
          primary: theme === "dark" ? "#ffffff" : "#0f172a",
          level: 1,
        },
        ...(theme === "dark" && {
          surface: {
            background: "#212121",
            foreground: "#303030",
          },
        }),
      },
      // typography: {
      //   baseSize: 16,
      //   fontFamily: "'JetBrains Mono', monospace",
      //   fontFamilyMono: "'JetBrains Mono', monospace",
      //   fontSources: [
      //     {
      //       family: 'JetBrains Mono',
      //       style: 'normal',
      //       weight: 300,
      //       display: 'swap',
      //       src: 'https://fonts.gstatic.com/s/jetbrainsmono/v23/tDbV2o-flEEny0FZhsfKu5WU4xD1OwGtT0rU3BE.woff2',
      //       unicodeRange: 'U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF',
      //     },
      //   ],
      // },
    },
    history: {
      enabled: true,
    },
    startScreen: {
      greeting: SUPPORT_GREETING,
      prompts: SUPPORT_STARTER_PROMPTS,
    },
    composer: {
      placeholder: "Ask the concierge a question",
      attachments: {
        enabled: true,
        maxCount: 5,
        maxSize: 10485760, // 10MB
      },
      models: [
        {
          id: 'gpt-5',
          label: 'GPT-5',
          description: 'Balanced intelligence',
          default: true,
        },
        {
          id: 'gpt-4o',
          label: 'GPT-4o',
          description: 'GPT-4 Optimized',
        }
      ],
    },
    threadItemActions: {
      feedback: false,
    },
    onResponseEnd: () => {
      onResponseCompleted();
    },
    onThreadChange: ({ threadId }) => {
      onThreadChange(threadId ?? null);
    },
    onError: ({ error }) => {
      // ChatKit displays surfaced errors; we keep logging for debugging.
      console.error("ChatKit error", error);
    },
  };

  const chatkit = useChatKit(options);

  return (
    <div className="relative h-full w-full min-w-full overflow-hidden bg-white dark:bg-slate-900">
      <ChatKit control={chatkit.control} className="block h-full w-full" />
    </div>
  );
}
