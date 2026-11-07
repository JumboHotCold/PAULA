// Bounded delivery with no automatic retry: a retry could duplicate a saved turn.
export async function postChat(payload, { credentials, csrfToken, timeoutMs = 30000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch('/api/chat', {
      method: 'POST', credentials, signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(csrfToken && { 'X-CSRFToken': csrfToken }) },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const error = new Error(response.status === 401 ? 'Your login session has ended. Please sign in again.' : 'Chat request failed.');
      error.status = response.status;
      error.code = data?.error_code || 'server_error';
      error.requestId = data?.request_id || response.headers?.get('X-Request-ID');
      throw error;
    }
    if (!data || typeof data.response !== 'string' || !data.response.trim()) {
      throw Object.assign(new Error('Invalid chat response.'), { code: 'invalid_response' });
    }
    return { response, data };
  } catch (error) {
    if (controller.signal.aborted) throw Object.assign(new Error('Chat request timed out.'), { code: 'timeout' });
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export function chatErrorMessage(error) {
  if (error.code === 'timeout') return 'PAULA is taking longer than expected. Please check your conversation before sending again.';
  if (error.code === 'invalid_response') return 'PAULA could not read the server response. Please try again shortly.';
  if (error.status === 409) return 'Your chat session changed. Please reopen your conversation or start a new chat.';
  if (error.status === 400) return 'Please enter a question of up to 2,000 characters and try again.';
  if (error.status === 403) return 'Your session could not be verified. Please refresh the page and try again.';
  if (error.status === 503) return 'PAULA is temporarily unavailable. Please try again shortly.';
  if (error.status) return 'PAULA could not complete this request. Please try again shortly.';
  return 'Unable to reach PAULA. Please check your connection and try again.';
}
