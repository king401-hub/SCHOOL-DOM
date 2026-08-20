// Pointer recording which exam a user was last actively working on in the
// Exam Builder, so re-opening the builder after a refresh/navigation-away
// can resume that same server-side row instead of starting a blank one.
// Read once, at mount, by whichever screen decides what `initialExam` to
// pass TeacherExamBuilder.
//
// This used to sit alongside a periodic background auto-save (writing full
// builder state to localStorage and syncing it to the backend on an
// interval). That mechanism was removed - it created duplicate Exam rows in
// production (races between the periodic sync and a manual Save/Publish,
// and across multiple tabs open to the same new-exam screen at once). Exam
// creation now only ever happens via an explicit Save/Publish click.
function activeDraftPointerKey(userId) {
  return `examBuilderActiveDraft:${userId || "anon"}`;
}

export function getLastActiveExamId(userId) {
  try {
    const raw = window.localStorage.getItem(activeDraftPointerKey(userId));
    return raw ? JSON.parse(raw).id : null;
  } catch {
    return null;
  }
}

export function setLastActiveExamId(userId, examId) {
  try {
    window.localStorage.setItem(activeDraftPointerKey(userId), JSON.stringify({ id: examId, updatedAt: Date.now() }));
  } catch {
    // best-effort
  }
}

export function clearLastActiveExamId(userId) {
  try {
    window.localStorage.removeItem(activeDraftPointerKey(userId));
  } catch {
    // ignore
  }
}
