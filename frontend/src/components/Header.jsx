/**
 * Header Component — SPUS Brand Header
 * =======================================
 * Shows PauliBot logo, title (serif heading), online status, and user badge.
 */

export default function Header({ user, onLogout }) {
  return (
    <header className="flex items-center justify-between px-5 py-4 glass-card border-t-0 border-x-0 z-10 shrink-0">
      {/* Logo & Title */}
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-xl flex items-center justify-center overflow-hidden shadow-lg shadow-spus-green/20 border border-spus-green/20">
          <img
            src="/spus-logo.webp"
            alt="SPUS Logo"
            className="w-11 h-11 object-contain"
          />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight" style={{ fontFamily: 'var(--font-family-heading)' }}>
            PAULA
          </h1>
          <p className="text-xs text-text-secondary font-light">
            Paulinian Artificial User Support and Learning Assistant
          </p>
        </div>
      </div>

      {/* Right section: status + user */}
      <div className="flex items-center gap-4">
        {/* Online Status */}
        <div className="flex items-center gap-2 text-xs text-spus-green font-medium">
          <span className="w-2 h-2 rounded-full bg-spus-green pulse-dot" />
          Online
        </div>

        {/* User Badge */}
        {user && (
          <div className="flex items-center gap-2">
            <span className={`text-[0.65rem] font-medium uppercase tracking-wider px-2.5 py-1 rounded-full border ${
              user.type === 'STUDENT'
                ? 'text-spus-green border-spus-green/30 bg-spus-green/10'
                : 'text-spus-gold border-spus-gold/30 bg-spus-gold/10'
            }`}>
              {user.type === 'STUDENT' ? user.id : 'Guest'}
            </span>
            <button
              onClick={onLogout}
              className="text-text-muted hover:text-text-secondary transition-colors cursor-pointer p-1"
              title="Logout"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
              </svg>
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
