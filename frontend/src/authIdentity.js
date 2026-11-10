// Server-confirmed identity mapping; guest-to-account transitions stay explicit.
export function userFromSession(session, stored = null) {
  if (!session?.authenticated || session.id == null || String(session.id).trim() === '') return null;
  const sameAccount = stored?.type !== 'GUEST' && stored?.id != null && String(stored.id) === String(session.id);
  const admin = session.is_superuser === true;
  return {
    ...(sameAccount ? stored : {}),
    id: session.id,
    name: session.name || (sameAccount && stored.name) || String(session.id),
    type: admin ? 'ADMIN' : 'STUDENT',
    is_superuser: admin,
  };
}

export function userFromLogin(data, fallbackId) {
  return userFromSession({ ...data, authenticated: true, id: data.account_id || data.student_id || fallbackId });
}

export function restoreIdentity(stored, session, adminRoute = false, restoreChat = true) {
  const account = userFromSession(session, stored);
  const availableAdmin = account?.is_superuser ? account : null;
  // Opening the administrative route is an explicit request to use that session.
  if (adminRoute && availableAdmin) return { user: availableAdmin, availableAdmin: null };
  // The public homepage requires an explicit Student or Visitor Access choice.
  if (!restoreChat) return { user: null, availableAdmin };
  if (adminRoute && stored?.type === 'GUEST') return { user: null, availableAdmin: null };
  if (stored?.type === 'GUEST') {
    return { user: { type: 'GUEST', id: null, name: 'Guest', is_superuser: false }, availableAdmin };
  }
  if (account && stored?.id != null && String(account.id) === String(stored.id)) {
    return { user: account, availableAdmin: null };
  }
  return { user: null, availableAdmin };
}
