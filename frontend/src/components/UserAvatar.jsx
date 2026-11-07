import React from 'react';
import { backendUrl } from '../utils/backendUrl';

/**
 * UserAvatar Component
 * =====================
 * Replaces the raw "G" initial for guest mode with a sleek visitor avatar,
 * and renders verified student avatar or initials with a Paulinian emerald ring.
 */
export default function UserAvatar({ user, size = 'sm', className = '' }) {
  const isGuest = !user || user.type === 'GUEST';
  
  const sizeMap = {
    xs: 'w-7 h-7 text-xs',
    sm: 'w-9 h-9 text-sm',
    md: 'w-10 h-10 text-base',
    lg: 'w-12 h-12 text-lg',
  };

  const currentSizeClass = sizeMap[size] || sizeMap.sm;

  if (isGuest) {
    return (
      <div 
        className={`relative inline-flex items-center justify-center rounded-full shrink-0 select-none shadow-sm transition-transform hover:scale-105 ${currentSizeClass} ${className}`}
        style={{
          background: 'linear-gradient(135deg, #F1F5F9 0%, #E2E8F0 100%)',
          border: '1.5px solid #CBD5E1',
        }}
        title="Guest Visitor"
      >
        {/* Modern Visitor Silhouette with ID badge icon */}
        <svg 
          viewBox="0 0 24 24" 
          className="w-[60%] h-[60%] text-[#005529]" 
          fill="currentColor"
        >
          {/* Head */}
          <path d="M12 2C9.24 2 7 4.24 7 7C7 9.76 9.24 12 12 12C14.76 12 17 9.76 17 7C17 4.24 14.76 2 12 2ZM12 10C10.35 10 9 8.65 9 7C9 5.35 10.35 4 12 4C13.65 4 15 5.35 15 7C15 8.65 13.65 10 12 10Z" />
          {/* Body */}
          <path d="M12 14C7.58 14 4 16.24 4 19V21C4 21.55 4.45 22 5 22H19C19.55 22 20 21.55 20 21V19C20 16.24 16.42 14 12 14ZM6.2 20C6.91 18.25 9.24 16 12 16C14.76 16 17.09 18.25 17.8 20H6.2Z" />
        </svg>

        {/* Guest Pin/Tag Badge */}
        <span 
          className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-[#D4AF37] border-2 border-white flex items-center justify-center"
          title="Guest Mode"
        >
          <span className="w-1 h-1 rounded-full bg-[#005529]"></span>
        </span>
      </div>
    );
  }

  // Registered Student / Admin
  const displayName = user.nickname || user.name || 'User';
  const initial = displayName.charAt(0).toUpperCase();

  if (user.avatar_url) {
    const avatarSrc = user.avatar_url.startsWith('http') 
      ? user.avatar_url 
      : backendUrl(user.avatar_url);

    return (
      <div 
        className={`relative inline-flex items-center justify-center rounded-full shrink-0 overflow-hidden shadow-sm border border-emerald-600/40 ${currentSizeClass} ${className}`}
        title={displayName}
      >
        <img 
          src={avatarSrc} 
          alt={displayName} 
          className="w-full h-full object-cover" 
          onError={(e) => {
            // fallback to initial on error
            e.target.style.display = 'none';
          }}
        />
      </div>
    );
  }

  return (
    <div 
      className={`relative inline-flex items-center justify-center rounded-full shrink-0 font-bold text-white shadow-sm border border-[#D4AF37]/60 select-none ${currentSizeClass} ${className}`}
      style={{
        background: 'linear-gradient(135deg, #005529 0%, #0A4D2E 100%)',
      }}
      title={displayName}
    >
      {initial}
    </div>
  );
}
