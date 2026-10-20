/// <reference types="vite/client" />
declare const __APP_TARGET__: "public" | "admin";
declare module "virtual:pwa-register/react" {
  export function useRegisterSW(options?: any): {
    needRefresh: [boolean, (v: boolean) => void];
    offlineReady: [boolean, (v: boolean) => void];
    updateServiceWorker: (reloadPage?: boolean) => Promise<void>;
  };
}
