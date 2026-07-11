export async function loadSessions() {
  const resp = await fetch('/api/sessions');
  const data = await resp.json();
  return data.sessions || [];
}

export async function createSession() {
  const resp = await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}'
  });
  const data = await resp.json();
  return data.id;
}

export async function deleteSession(sessionId) {
  await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' });
}

export async function loadHistory(sessionId) {
  const resp = await fetch(`/api/history/${encodeURIComponent(sessionId)}`);
  const data = await resp.json();
  return data.history || [];
}

export async function sendChat(message, sessionId) {
  const resp = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId })
  });
  return resp.json();
}

export async function loadPreferences() {
  try {
    const resp = await fetch('/api/preferences');
    return await resp.json();
  } catch {
    return {};
  }
}

export function ttsUrl(text, lang) {
  return `/api/tts?text=${encodeURIComponent(text)}&lang=${encodeURIComponent(lang)}`;
}
