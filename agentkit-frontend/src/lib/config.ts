import { StartScreenPrompt } from "@openai/chatkit";

export const THEME_STORAGE_KEY = "customer-support-theme";

const SUPPORT_API_BASE =
  import.meta.env.VITE_SUPPORT_API_BASE ?? "/support";

/**
 * ChatKit still expects a domain key at runtime. Use any placeholder locally,
 * but register your production domain at
 * https://platform.openai.com/settings/organization/security/domain-allowlist
 * and deploy the real key.
 */
export const SUPPORT_CHATKIT_API_DOMAIN_KEY =
  import.meta.env.VITE_SUPPORT_CHATKIT_API_DOMAIN_KEY ?? "domain_pk_693816277b0881958fdd07afc2089e6609e53a3e6ed4c451";

export const SUPPORT_CHATKIT_API_URL =
  import.meta.env.VITE_SUPPORT_CHATKIT_API_URL ??
  `${SUPPORT_API_BASE}/chatkit`;

export const SUPPORT_CUSTOMER_URL =
  import.meta.env.VITE_SUPPORT_CUSTOMER_URL ??
  `${SUPPORT_API_BASE}/customer`;

export const SUPPORT_GREETING =
  import.meta.env.VITE_SUPPORT_GREETING ??
  "Search for products for quote ...";

export const SUPPORT_STARTER_PROMPTS: StartScreenPrompt[] = [
  {
    label: "Find some formic acid for my lab",
    prompt: "Find some formic acid for my lab",
    icon: "sparkle",
  }
];
