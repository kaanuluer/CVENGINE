import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/new", label: "Yeni başvuru" },
  { to: "/master", label: "Master CV" },
  { to: "/settings", label: "Ayarlar" },
];

export function TopBar() {
  return (
    <header className="sticky top-0 z-20 border-b border-line/80 bg-white/80 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
        <div className="flex items-center gap-8">
          <NavLink to="/" className="flex items-baseline gap-2 no-underline">
            <span className="text-[15px] font-semibold tracking-tight text-ink">CVENGINE</span>
            <span className="text-xs text-muted">lokal ATS motoru</span>
          </NavLink>
          <nav className="flex items-center gap-1" aria-label="Ana menü">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm transition ${
                    isActive ? "bg-ink text-white" : "text-muted hover:bg-canvas hover:text-ink"
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <span className="rounded-full bg-canvas px-2.5 py-1 text-[11px] font-medium text-muted">
          127.0.0.1 · veri dışarı çıkmaz
        </span>
      </div>
    </header>
  );
}
