const BASE = '/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  getUsers: () => request('/users'),
  getItems: () => request('/items'),
  createItem: (name, category, description) =>
    request('/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, category, description }),
    }),
  getRecsV1: (userId, count = 8) =>
    request(`/recommendations/v1?user_id=${userId}&count=${count}`),
  getRecsV2: (userId, count = 8) =>
    request(`/recommendations/v2?user_id=${userId}&count=${count}`),
  getUserInteractions: (userId) => request(`/users/${userId}/interactions`),
  logInteraction: (userId, itemId, action) =>
    request('/interactions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, item_id: itemId, action }),
    }),
  listABTests: () => request('/ab_tests'),
  createABTest: (name) =>
    request('/ab_tests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, control: 'v1', treatment: 'v2' }),
    }),
  getTestResults: (testId) => request(`/ab_tests/${testId}/results`),
  getTestAnalysis: (testId) => request(`/ab_tests/${testId}/analysis`),
  getMetricsOverTime: (testId, period = 'day') =>
    request(`/ab_tests/${testId}/metrics_over_time?period=${period}`),
  simulateTestData: (testId) =>
    request(`/ab_tests/${testId}/simulate`, { method: 'POST' }),
  logTestEvent: (testId, userId, itemId, eventType) =>
    request(`/ab_tests/${testId}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, item_id: itemId, event_type: eventType }),
    }),
};
