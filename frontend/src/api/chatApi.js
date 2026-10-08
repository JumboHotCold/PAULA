/**
 * PauliBot Chat API Layer
 * =======================
 * Handles all communication with the Django REST Framework backend.
 * Uses fetch with credentials for session-based auth + CSRF protection.
 */

/**
 * Extract a cookie value by name from document.cookie.
 */
export function getCookie(name) {
  const cookies = document.cookie.split(';');
  for (let cookie of cookies) {
    cookie = cookie.trim();
    if (cookie.startsWith(name + '=')) {
      return decodeURIComponent(cookie.substring(name.length + 1));
    }
  }
  return null;
}

/**
 * Ensure we have a CSRF token by hitting a Django endpoint that sets the cookie.
 * The Vite proxy forwards /api/* to Django, which returns the csrftoken cookie.
 */
export async function ensureCsrfToken() {
  if (!getCookie('csrftoken')) {
    try {
      // Hit any GET endpoint to receive the CSRF cookie
      await fetch('/api/conversations', {
        credentials: 'include',
      });
    } catch (e) {
      console.warn('Could not fetch CSRF token:', e);
    }
  }
}

/**
 * Send a message to PauliBot and receive the AI response.
 * 
 * @param {string} message - The user's message text
 * @param {number|null} conversationId - Optional conversation ID for history tracking
 * @returns {Promise<Object>} - { response, saved, user, conversation_id, conversation_title, chat_history_id }
 */
export async function sendMessage(message, conversationId = null) {
  const csrfToken = getCookie('csrftoken');

  const res = await fetch('/api/chat', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

/**
 * Fetch chat history for the logged-in user.
 */
export async function fetchConversations() {
  const res = await fetch('/api/conversations', {
    credentials: 'include',
  });
  if (!res.ok) throw new Error('Failed to fetch conversations');
  return res.json();
}

/**
 * Fetch messages for a specific conversation.
 */
export async function fetchConversationDetails(id) {
  const res = await fetch(`/api/conversations/${id}`, {
    credentials: 'include',
  });
  if (!res.ok) throw new Error('Failed to fetch conversation details');
  return res.json();
}

/**
 * Delete a specific conversation.
 */
export async function deleteConversation(id) {
  const csrfToken = getCookie('csrftoken');
  const res = await fetch(`/api/conversations/${id}`, {
    method: 'DELETE',
    credentials: 'include',
    headers: {
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
    },
  });
  if (!res.ok) throw new Error('Failed to delete conversation');
  return res.json();
}

/**
 * Create a new conversation explicitly.
 */
export async function createConversation() {
  const csrfToken = getCookie('csrftoken');
  const res = await fetch('/api/conversations', {
    method: 'POST',
    credentials: 'include',
    headers: {
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
    },
  });
  if (!res.ok) throw new Error('Failed to create conversation');
  return res.json();
}


// =============================================================================
// ADMIN DASHBOARD API
// =============================================================================

export async function fetchAdminMetrics() {
  const res = await fetch('/api/admin/metrics/', { credentials: 'include' });
  if (!res.ok) throw new Error('Failed to fetch admin metrics');
  return res.json();
}

export async function fetchCampusPulse() {
  const res = await fetch('/api/admin/campus-pulse/', { credentials: 'include' });
  if (!res.ok) throw new Error('Failed to fetch campus pulse');
  return res.json();
}

export async function fetchTrendingConfusion() {
  const res = await fetch('/api/admin/trending-confusion/', { credentials: 'include' });
  if (!res.ok) throw new Error('Failed to fetch trending confusion');
  return res.json();
}

export async function fetchStudentNeeds(params = {}) {
  const query = new URLSearchParams();
  if (params.page) query.set('page', params.page);
  if (params.urgency) query.set('urgency', params.urgency);
  if (params.need_type) query.set('need_type', params.need_type);
  if (params.status) query.set('status', params.status);
  if (params.search) query.set('search', params.search);

  const res = await fetch(`/api/admin/student-needs/?${query.toString()}`, {
    credentials: 'include',
  });
  if (!res.ok) throw new Error('Failed to fetch student needs');
  return res.json();
}

export async function patchStudentNeed(id, data) {
  const csrfToken = getCookie('csrftoken');
  const res = await fetch(`/api/admin/student-needs/${id}/`, {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update student need');
  return res.json();
}

export async function fetchAdminReportsData() {
  const res = await fetch('/api/admin/reports/data/', { credentials: 'include' });
  if (!res.ok) throw new Error('Failed to fetch admin reports data');
  return res.json();
}

export function getPrintReportUrl(type = 'summary') {
  return `/api/admin/reports/print/?type=${encodeURIComponent(type)}`;
}

export function getExportCsvUrl(type = 'summary') {
  return `/api/admin/reports/export/csv/?type=${encodeURIComponent(type)}`;
}

export function getExportPdfUrl(type = 'summary') {
  return `/api/admin/reports/export/pdf/?type=${encodeURIComponent(type)}`;
}

// =============================================================================
// PUBLIC API
// =============================================================================

export async function fetchAnnouncements() {
  const res = await fetch('/api/announcements');
  if (!res.ok) throw new Error('Failed to fetch announcements');
  return res.json();
}

/**
 * Updates the student's profile (nickname and/or avatar).
 */
export async function patchProfile(formData) {
  const csrfToken = getCookie('csrftoken');
  const res = await fetch('/api/profile', {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      // NOTE: FormData header 'Content-Type' is set automatically with boundary by the browser
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
    },
    body: formData,
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error || 'Failed to update profile');
  }
  return res.json();
}

/**
 * Fetch campus navigation route using Python backend A*
 */
export async function fetchCampusRoute(start_x, start_y, end_x, end_y) {
  const res = await fetch('/api/navigation/route/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
    body: JSON.stringify({ start_x, start_y, end_x, end_y }),
  });
  
  if (!res.ok) throw new Error('Failed to fetch campus route');
  return res.json();
}
