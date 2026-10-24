import { Moon, Sun, Wind } from "lucide-react";

interface HeaderProps {
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

const nav = [
  { href: "#overview", label: "Overview" },
  { href: "#accuracy", label: "Accuracy" },
  { href: "#settlements", label: "Settlements" },
  { href: "#history", label: "History" },
  { href: "#methodology", label: "Method" },
];

export function Header({ theme, onToggleTheme }: HeaderProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-canvas">
      <div className="mx-auto w-full max-w-[1200px] px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between gap-4">
          <a href="#overview" className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-md border border-line bg-accent-soft text-accent-text">
              <Wind size={16} strokeWidth={2} />
            </span>
            <span className="text-[15px] font-semibold tracking-tight text-ink">
              WindTrace
            </span>
          </a>

          <nav className="hidden items-center gap-0.5 md:flex" aria-label="Primary">
            {nav.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="rounded-md px-2.5 py-1.5 text-xs font-medium text-body hover:bg-subtle hover:text-ink"
              >
                {item.label}
              </a>
            ))}
          </nav>

          <button
            type="button"
            onClick={onToggleTheme}
            className="icon-btn"
            aria-label={theme === "dark" ? "Use light theme" : "Use dark theme"}
            title={theme === "dark" ? "Use light theme" : "Use dark theme"}
          >
            {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        </div>

        <nav
          className="-mx-1 flex items-center gap-0.5 overflow-x-auto border-t border-line py-1 md:hidden"
          aria-label="Primary"
        >
          {nav.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="whitespace-nowrap rounded-md px-2 py-1 text-[11px] font-medium text-body hover:bg-subtle hover:text-ink"
            >
              {item.label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}
