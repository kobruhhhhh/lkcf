import { RefreshCw } from "lucide-react";

export function LoadingScreen() {
  return (
    <div className="mx-auto w-full max-w-[1200px] px-4 py-12 sm:px-6 lg:px-8">
      <p className="text-sm text-body">Loading live Elexon data…</p>
      <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="card h-[104px] p-4">
            <div className="h-2.5 w-16 rounded bg-muted" />
            <div className="mt-4 h-6 w-24 rounded bg-muted" />
            <div className="mt-3 h-2 w-28 rounded bg-muted" />
          </div>
        ))}
      </div>
      <div className="card mt-4 h-[360px] p-4">
        <div className="h-2.5 w-32 rounded bg-muted" />
        <div className="mt-8 h-[280px] rounded bg-subtle" />
      </div>
    </div>
  );
}

interface ErrorScreenProps {
  message: string;
  apiBase: string;
  busy?: boolean;
  onRetry: () => void;
}

export function ErrorScreen({ message, apiBase, busy = false, onRetry }: ErrorScreenProps) {
  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-12 sm:px-6">
      <div className="card p-5 sm:p-6">
        <h1 className="text-xl font-semibold tracking-tight text-ink">
          Could not load the dashboard
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-body">{message}</p>
        <p className="mt-3 break-all rounded-md border border-line bg-subtle px-3 py-2 font-mono text-[11px] text-body">
          API base: {apiBase}
        </p>
        <button
          type="button"
          onClick={onRetry}
          disabled={busy}
          className="btn btn-primary mt-4"
        >
          <RefreshCw size={13} className={busy ? "animate-spin" : undefined} />
          {busy ? "Retrying live data…" : "Retry live data"}
        </button>

        <div className="mt-5 border-t border-line pt-4">
          <h2 className="text-xs font-semibold text-ink">Local runbook</h2>
          <pre className="mt-2 overflow-x-auto rounded-md border border-line bg-subtle p-3 font-mono text-[11px] leading-relaxed text-body">
            {`cd backend
.\\.venv\\Scripts\\python -m uvicorn app.main:app --reload --port 8000

cd frontend
npm run dev`}
          </pre>
          <p className="mt-2 text-[11px] leading-relaxed text-body">
            For a deployed frontend, set <span className="font-mono">VITE_API_BASE_URL</span>{" "}
            to the public API origin and allow that origin in the backend CORS settings.
            The backend fetches live Elexon data server-side; no API key is needed.
          </p>
        </div>
      </div>
    </main>
  );
}
