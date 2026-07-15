/** Minimal logger (workspace rule: no raw console.* scattered in components). */
const isDev = process.env.NODE_ENV !== "production";

export const logger = {
  info: (...args: unknown[]) => {
    if (isDev) console.info("[reglens]", ...args);
  },
  error: (...args: unknown[]) => {
    console.error("[reglens]", ...args);
  },
};
