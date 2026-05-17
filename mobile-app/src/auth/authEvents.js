const listeners = new Set();

export function subscribeToAuthEvents(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function notifySessionExpired() {
  listeners.forEach((listener) => {
    try {
      listener({ type: "sessionExpired" });
    } catch {
      // Auth event listeners should not break the API error flow.
    }
  });
}
