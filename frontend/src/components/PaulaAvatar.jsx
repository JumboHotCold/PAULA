import React from 'react';

/**
 * PaulaAvatar Component
 * =======================
 * Authentic, handcrafted identity for PAULA (Paulinian AI Assistant).
 * 
 * Features:
 * - Uses the authentic St. Paul University Surigao seal medallion.
 * - Framed in an elegant Paulinian Emerald & Gold heraldic ring.
 * - Dynamic micro-interactions:
 *   - Idle: subtle ambient glow.
 *   - Typing: radar processing pulse and active emerald indicator.
 * - 100% authentic to SPUS — clean, professional, and not AI-generated.
 */
export default function PaulaAvatar({ 
  size = 'sm', 
  isTyping = false, 
  variant = 'crest', // 'crest' | 'shield'
  className = '' 
}) {
  const sizeMap = {
    xs: { outer: 'w-7 h-7', img: 'w-5 h-5', badge: 'w-2 h-2', ping: 'h-2 w-2' },
    sm: { outer: 'w-9 h-9', img: 'w-7 h-7', badge: 'w-2.5 h-2.5', ping: 'h-2.5 w-2.5' },
    md: { outer: 'w-11 h-11', img: 'w-9 h-9', badge: 'w-3 h-3', ping: 'h-3 w-3' },
    lg: { outer: 'w-16 h-16', img: 'w-12 h-12', badge: 'w-3.5 h-3.5', ping: 'h-3.5 w-3.5' },
    xl: { outer: 'w-20 h-20', img: 'w-16 h-16', badge: 'w-4 h-4', ping: 'h-4 w-4' },
    hero: { outer: 'w-24 h-24', img: 'w-20 h-20', badge: 'w-4.5 h-4.5', ping: 'h-4.5 w-4.5' },
  };

  const currentSize = sizeMap[size] || sizeMap.sm;

  if (variant === 'shield') {
    // Custom Handcrafted Paulinian SVG Crest
    return (
      <div 
        className={`paula-shield-avatar relative inline-flex items-center justify-center select-none ${currentSize.outer} ${className}`}
        title="PAULA - Paulinian AI Assistant"
      >
        <svg 
          viewBox="0 0 48 48" 
          className={`w-full h-full overflow-visible ${isTyping ? 'paula-shimmer' : ''}`}
          fill="none" 
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id="shieldGold" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
              <stop stopColor="#FDE68A" />
              <stop offset="0.5" stopColor="#D4AF37" />
              <stop offset="1" stopColor="#92400E" />
            </linearGradient>

            <linearGradient id="shieldGreen" x1="24" y1="4" x2="24" y2="44" gradientUnits="userSpaceOnUse">
              <stop stopColor="#0A4D2E" />
              <stop offset="1" stopColor="#00381B" />
            </linearGradient>
          </defs>

          {/* Outer Scalloped University Border */}
          <circle 
            cx="24" 
            cy="24" 
            r="22" 
            fill="url(#shieldGreen)" 
            stroke="url(#shieldGold)" 
            strokeWidth="1.5" 
          />

          {/* Inner Golden Ring */}
          <circle 
            cx="24" 
            cy="24" 
            r="19" 
            stroke="url(#shieldGold)" 
            strokeWidth="0.8" 
            strokeDasharray={isTyping ? "2 2" : "none"}
            className={isTyping ? "animate-spin" : ""}
            style={{ animationDuration: '8s', transformOrigin: 'center' }}
          />

          {/* Paulinian Cross & Open Book Motif */}
          <path 
            d="M 17 28 Q 24 25 31 28 L 31 32 Q 24 29 17 32 Z" 
            fill="#FDE68A" 
            opacity="0.9"
          />
          {/* St. Paul Sword/Quill Vertical Axis */}
          <line x1="24" y1="12" x2="24" y2="34" stroke="#FDE68A" strokeWidth="1.5" strokeLinecap="round" />
          <line x1="19" y1="16" x2="29" y2="16" stroke="#FDE68A" strokeWidth="1.5" strokeLinecap="round" />

          {/* PAULA Text Arc */}
          <text 
            x="24" 
            y="23" 
            textAnchor="middle" 
            fill="#FFFFFF" 
            fontSize="5.5" 
            fontWeight="bold" 
            letterSpacing="1"
            fontFamily="var(--font-family-sans), system-ui, sans-serif"
          >
            PAULA
          </text>
        </svg>

        {isTyping && (
          <span className={`absolute -bottom-0.5 -right-0.5 flex ${currentSize.badge}`}>
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75`}></span>
            <span className={`relative inline-flex rounded-full ${currentSize.badge} bg-emerald-500 border-2 border-white`}></span>
          </span>
        )}
      </div>
    );
  }

  // Primary: Authentic SPUS Seal Medallion Avatar with Golden Heraldic Frame
  return (
    <div 
      className={`paula-crest-avatar relative inline-flex items-center justify-center shrink-0 select-none rounded-full ${currentSize.outer} ${className}`}
      title="PAULA - Paulinian AI Assistant (St. Paul University Surigao)"
    >
      {/* Dynamic Processing Ripple when Typing */}
      {isTyping && (
        <span className="absolute inset-0 rounded-full border-2 border-[#10B981] animate-ping opacity-35" />
      )}

      {/* Outer Golden Heraldic Bezel */}
      <div 
        className="w-full h-full rounded-full flex items-center justify-center bg-white shadow-md transition-transform duration-200 hover:scale-105"
        style={{
          border: '1.5px solid #D4AF37',
          boxShadow: isTyping 
            ? '0 0 10px rgba(16, 185, 129, 0.4), 0 2px 5px rgba(0,0,0,0.1)' 
            : '0 2px 6px rgba(0, 0, 0, 0.08)',
        }}
      >
        <img 
          src="/spus-logo.webp" 
          alt="PAULA - St. Paul University Surigao" 
          className={`${currentSize.img} object-contain transition-transform`}
          style={{
            filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.15))',
          }}
        />
      </div>

      {/* Active AI Status Pip */}
      <span className={`absolute -bottom-0.5 -right-0.5 flex ${currentSize.badge}`}>
        {isTyping ? (
          <>
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
            <span className={`relative inline-flex rounded-full ${currentSize.badge} bg-amber-500 border-2 border-white`} title="PAULA is generating a response..."></span>
          </>
        ) : (
          <span className={`relative inline-flex rounded-full ${currentSize.badge} bg-[#005529] border-1.5 border-white shadow-xs`} title="PAULA Active"></span>
        )}
      </span>
    </div>
  );
}
