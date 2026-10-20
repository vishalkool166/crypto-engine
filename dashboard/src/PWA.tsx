import { useEffect, useState } from "react";
import { useRegisterSW } from "virtual:pwa-register/react";
import { Button } from "./components/ui/button";
export default function PWA() {
  const {
    needRefresh: [refresh, setRefresh],
    updateServiceWorker,
  } = useRegisterSW();
  const [prompt, setPrompt] = useState<any>(null),
    [dismissed, setDismissed] = useState(false);
  useEffect(() => {
    const listener = (event: Event) => {
      event.preventDefault();
      setPrompt(event);
    };
    window.addEventListener("beforeinstallprompt", listener);
    return () => window.removeEventListener("beforeinstallprompt", listener);
  }, []);
  if (dismissed || (!refresh && !prompt)) return null;
  return (
    <aside className="pwa-banner" aria-label="App installation and updates">
      <div>
        <strong>
          {refresh ? "A new version is ready" : "Keep the workspace close"}
        </strong>
        <p>
          {refresh
            ? "Reload to use the latest application."
            : "Install Signal Engine on this device."}
        </p>
      </div>
      <Button
        size="sm"
        onClick={async () => {
          if (refresh) {
            await updateServiceWorker(true);
            setRefresh(false);
          } else {
            await prompt.prompt();
            setPrompt(null);
          }
        }}
      >
        {refresh ? "Update" : "Install"}
      </Button>
      <Button variant="ghost" size="sm" onClick={() => setDismissed(true)}>
        Later
      </Button>
    </aside>
  );
}
