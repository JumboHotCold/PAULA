export default function AdminSessionNotice({ onContinue }) {
  if (!onContinue) return null;
  return (
    <div className="admin-session-notice" role="status">
      <span>An administrator is signed in. Switch accounts to access admin tools; your guest chat will stay unsaved.</span>
      <button type="button" onClick={onContinue}>Switch to administrator</button>
    </div>
  );
}
