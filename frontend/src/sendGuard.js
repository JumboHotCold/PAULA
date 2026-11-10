// Acquire before changing UI state; React state updates are not a synchronous lock.
export function createSendGuard() {
  let active = null;
  return {
    acquire(epoch) {
      if (active?.epoch === epoch) return null;
      active = { epoch };
      return active;
    },
    release(ticket) {
      // An old request must never unlock a newer account/thread's request.
      if (active === ticket) active = null;
    },
  };
}
