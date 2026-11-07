// Browser-facing links/media need the backend origin, not the phone's localhost.
// API requests continue to use the existing same-origin Vite proxy.
export function backendUrl(path, explicitOrigin) {
  let origin = explicitOrigin || import.meta.env?.VITE_BACKEND_ORIGIN;
  if (!origin) {
    const current = new URL(window.location.origin);
    if (import.meta.env?.DEV) current.port = '8080';
    origin = current.origin;
  }
  return new URL(path, `${origin.replace(/\/$/, '')}/`).href;
}
