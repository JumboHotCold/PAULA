import { useState, useRef, useEffect } from 'react';
import { patchProfile } from '../api/chatApi';
import { backendUrl } from '../utils/backendUrl';

/**
 * EditProfileModal Component
 * =========================
 * Allows students to change their display nickname and profile photo.
 */
export default function EditProfileModal({ isOpen, onClose, user, onUpdate }) {
  const [nickname, setNickname] = useState('');
  const [avatarPreview, setAvatarPreview] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);
  const dialogRef = useRef(null);
  useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement;
    dialogRef.current?.querySelector('.close-btn')?.focus();
    const key = event => {
      if (event.key === 'Escape') onClose();
      if (event.key !== 'Tab') return;
      const items = [...dialogRef.current.querySelectorAll('button, input')].filter(el => !el.disabled && el.type !== 'file');
      if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items.at(-1)?.focus(); }
      if (!event.shiftKey && document.activeElement === items.at(-1)) { event.preventDefault(); items[0]?.focus(); }
    };
    document.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('keydown', key);
      const target = previous?.closest('[inert]') ? document.querySelector('.hamburger-btn') : previous;
      target?.focus();
    };
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen && user) {
      // Use nickname if available, else name
      setNickname(user.nickname || user.name || '');
      // avatar_url should be provided by backend or empty
      setAvatarPreview(user.avatar_url || '');
      setSelectedFile(null);
      setError('');
    }
  }, [isOpen, user]);

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.size > 2 * 1024 * 1024) {
        setError('Image too large (max 2MB)');
        return;
      }
      setSelectedFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setAvatarPreview(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    setError('');
    const formData = new FormData();
    formData.append('nickname', nickname);
    if (selectedFile) {
      formData.append('avatar', selectedFile);
    }

    try {
      const data = await patchProfile(formData);
      // Backend returns { nickname, avatar_url }
      onUpdate({ ...user, nickname: data.nickname, name: data.nickname, avatar_url: data.avatar_url });
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save changes');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div ref={dialogRef} className="modal-content glass-card animate-message-in" role="dialog" aria-modal="true" aria-labelledby="profile-dialog-title" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 id="profile-dialog-title">Edit Profile</h2>
          <button type="button" className="close-btn" aria-label="Close profile" onClick={onClose}>&times;</button>
        </div>
        
        <div className="modal-body">
          {error && <div className="error-message" style={{ marginBottom: '20px' }}>{error}</div>}
          
          <div className="profile-photo-section">
            <div className="avatar-preview-container" onClick={() => fileInputRef.current.click()}>
              {avatarPreview ? (
                <img 
                  src={backendUrl(avatarPreview)}
                  alt="Avatar Preview" 
                  className="avatar-preview-img" 
                  onError={(e) => { e.target.src = ''; setAvatarPreview(''); }}
                />
              ) : (
                <div className="avatar-placeholder">{(user.nickname || user.name)?.[0]?.toUpperCase() || 'U'}</div>
              )}
              <div className="avatar-overlay">
                <span>CHANGE</span>
              </div>
            </div>
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleFileChange} 
              style={{ display: 'none' }} 
              accept="image/*"
            />
            <p className="photo-hint">Click to change profile picture</p>
          </div>

          <div className="form-group" style={{ position: 'relative', marginTop: '10px' }}>
            <label className="modal-label">Display Nickname</label>
            <input 
              type="text" 
              className="form-input" 
              value={nickname} 
              onChange={(e) => setNickname(e.target.value)} 
              maxLength={30}
              placeholder="Enter your nickname..."
              style={{ padding: '12px 15px', background: 'rgba(255,255,255,0.05)', color: 'inherit' }}
            />
            <span className="char-count">{nickname.length}/30</span>
          </div>

          <div className="form-group" style={{ marginTop: '20px' }}>
            <label className="modal-label">Email Address (Read-only)</label>
            <input 
              type="text" 
              className="form-input" 
              value={user.email || 'N/A'} 
              readOnly 
              style={{ padding: '12px 15px', background: 'rgba(0,0,0,0.1)', opacity: 0.6, cursor: 'not-allowed' }}
            />
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-muted)' }} onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSave} disabled={loading}>
            {loading ? 'Saving Changes...' : 'Save Profile'}
          </button>
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .modal-overlay {
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0, 0, 0, 0.7);
          backdrop-filter: blur(8px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 2000;
          padding: 20px;
          overflow-y: auto;
        }
        .modal-content {
          width: 100%;
          max-width: 440px;
          border-radius: 20px;
          max-height: calc(var(--app-height, 100dvh) - 32px - env(safe-area-inset-top) - env(safe-area-inset-bottom));
          overflow-y: auto;
          padding: 32px;
          position: relative;
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }
        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 28px;
        }
        .modal-header h2 {
          font-family: var(--font-family-heading);
          font-weight: 700;
          letter-spacing: -0.015em;
          margin: 0;
          color: var(--color-primary);
          font-size: 1.6em;
        }
        .close-btn {
          background: none;
          border: none;
          font-size: 32px;
          cursor: pointer;
          color: var(--color-text-muted);
          line-height: 1;
          padding: 0;
          min-width: 44px;
          min-height: 44px;
        }
        .profile-photo-section {
          display: flex;
          flex-direction: column;
          align-items: center;
          margin-bottom: 30px;
        }
        .avatar-preview-container {
          width: 130px;
          height: 130px;
          border-radius: 50%;
          overflow: hidden;
          position: relative;
          cursor: pointer;
          border: 4px solid var(--color-primary);
          box-shadow: 0 8px 24px rgba(0,0,0,0.15);
          transition: transform 0.3s ease;
          background: var(--color-bg);
        }
        .avatar-preview-container:hover {
          transform: translateY(-4px);
        }
        .avatar-preview-img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }
        .avatar-placeholder {
          width: 100%;
          height: 100%;
          background: linear-gradient(135deg, var(--color-primary) 0%, var(--spus-green-dark) 100%);
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 48px;
          font-weight: 700;
        }
        .avatar-overlay {
          position: absolute;
          bottom: 0; left: 0; right: 0;
          background: rgba(0,0,0,0.6);
          color: white;
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 1px;
          text-align: center;
          padding: 6px 0;
          opacity: 0;
          transition: opacity 0.2s;
        }
        .avatar-preview-container:hover .avatar-overlay {
          opacity: 1;
        }
        .photo-hint {
          margin-top: 12px;
          font-size: 0.8em;
          color: var(--color-text-muted);
        }
        .modal-label {
          display: block;
          margin-bottom: 10px;
          font-weight: 600;
          font-size: 0.85em;
          color: var(--color-text);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .char-count {
          position: absolute;
          right: 12px;
          bottom: 10px;
          font-size: 0.75em;
          color: var(--color-text-muted);
        }
        .modal-footer {
          display: flex;
          gap: 15px;
          margin-top: 35px;
        }
        .modal-footer .btn {
          flex: 1;
          padding: 14px;
        }
        @media (max-width: 600px) {
          .modal-overlay { padding: 12px; }
          .modal-content { padding: 20px; }
          .modal-content input { font-size: 16px; }
          .modal-header { margin-bottom: 16px; }
          .profile-photo-section { margin-bottom: 18px; }
          .avatar-preview-container { width: 96px; height: 96px; }
          .modal-footer { margin-top: 20px; gap: 8px; }
        }
      `}} />
    </div>
  );
}
