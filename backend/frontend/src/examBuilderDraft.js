import { useCallback, useEffect, useRef, useState } from "react";
import { requestJson } from "./AppShared";

// Local (localStorage) save runs fast and unconditionally - it is the actual
// "never lose content" guarantee and never depends on the network.
const LOCAL_SAVE_DEBOUNCE_MS = 800;
// Backend sync is checked on this interval; it only actually does anything if
// something has changed since the last successful/attempted sync, so an idle
// builder never generates background traffic.
const BACKEND_SYNC_INTERVAL_MS = 15000;

export function localDraftKey(kind, id) {
  return `examBuilderDraft:${kind}:${id}`;
}

// Separate from the draft *content* cache above: a small pointer recording
// which exam a user was last actively drafting, so re-opening the builder
// after a refresh/navigation-away can resume that same server-side row
// instead of the builder mounting blank and auto-save creating a second
// exam. Only ever meant to be read once, at mount, by whichever screen
// decides what `initialExam` to pass TeacherExamBuilder - it does not
// participate in the auto-save mechanics themselves.
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
    // best-effort, same as the draft-content cache above
  }
}

export function clearLastActiveExamId(userId) {
  try {
    window.localStorage.removeItem(activeDraftPointerKey(userId));
  } catch {
    // ignore
  }
}

export function loadLocalDraft(key) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveLocalDraft(key, snapshot) {
  try {
    window.localStorage.setItem(key, JSON.stringify({ ...snapshot, lastModified: Date.now() }));
  } catch {
    // localStorage can throw (quota exceeded, private browsing) - it's a
    // best-effort local safety net layered on top of the backend sync, not
    // the only one, so a write failure here is not fatal.
  }
}

export function clearLocalDraft(key) {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignore
  }
}

// Question objects hold raw File/Blob values (questionImageFile,
// questionAttachmentFile, group.imageFile) while a file is selected but not
// yet uploaded - these can't survive JSON.stringify, so they're stripped
// before writing to localStorage. The preview URL/text is kept, so a refresh
// still shows "you had an image attached here", just not a re-uploadable
// file - an accepted, narrow gap documented in the plan.
function stripFilesForLocalStorage(question) {
  const { questionImageFile, questionAttachmentFile, group, ...rest } = question;
  return {
    ...rest,
    group: group ? (({ imageFile, ...groupRest }) => groupRest)(group) : group,
  };
}

/**
 * Local-first auto-save for the Exam Builder. Writes the full builder state to
 * localStorage on every change (fast, offline-safe), and separately, opportunistically
 * syncs to the backend - creating the draft exam on the server the first time there's
 * meaningful content, then keeping it updated via idempotent, upsert-by-id PATCH calls
 * that are safe to retry after a dropped connection.
 *
 * `buildAutosavePayload` is supplied by the caller (TeacherExamPanels.jsx) since only it
 * knows the exam-specific payload shape (question field names, FormData-vs-JSON, etc.) -
 * this hook only owns the persistence/timing/retry mechanics, not exam domain logic.
 */
export function useExamAutosave({ session, userId, initialExamId, form, sections, questions, buildAutosavePayload, enabled = true }) {
  const [status, setStatus] = useState("idle");
  const [examId, setExamId] = useState(initialExamId || null);
  const [restoredNotice, setRestoredNotice] = useState("");

  const localKeyRef = useRef(examId ? localDraftKey("edit", examId) : localDraftKey("new", userId));
  const latestRef = useRef({ form, sections, questions });
  const dirtyRef = useRef(false);
  const syncingRef = useRef(false);
  const localTimerRef = useRef(null);
  // The builder starts with a placeholder title and one blank question already
  // in state (existing behavior, unrelated to auto-save) - a fresh draft should
  // only reach the server once the user has actually changed something, not the
  // instant the builder mounts. Captured once; only matters pre-create.
  const pristineSnapshotRef = useRef(JSON.stringify({ form, questions }));

  latestRef.current = { form, sections, questions };

  useEffect(() => {
    if (examId) localKeyRef.current = localDraftKey("edit", examId);
  }, [examId]);

  useEffect(() => {
    dirtyRef.current = true;
    if (!enabled) return undefined;
    if (localTimerRef.current) window.clearTimeout(localTimerRef.current);
    localTimerRef.current = window.setTimeout(() => {
      const { form: f, sections: s, questions: q } = latestRef.current;
      saveLocalDraft(localKeyRef.current, { form: f, sections: s, questions: q.map(stripFilesForLocalStorage) });
    }, LOCAL_SAVE_DEBOUNCE_MS);
    return () => window.clearTimeout(localTimerRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, form, sections, questions]);

  const runSync = useCallback(async () => {
    if (!enabled || syncingRef.current || !dirtyRef.current) return;
    const { form: currentForm, questions: currentQuestions } = latestRef.current;
    // Once the exam already exists server-side, every dirty tick is worth
    // syncing; before that, wait for a real change from the pristine defaults
    // so opening the builder and immediately leaving doesn't create a draft.
    const hasContent = Boolean(examId) || JSON.stringify({ form: currentForm, questions: currentQuestions }) !== pristineSnapshotRef.current;
    if (!hasContent) return;

    syncingRef.current = true;
    setStatus((prev) => (prev === "offline" ? "syncing" : "saving"));
    try {
      const { requestPayload } = buildAutosavePayload({ form: currentForm, questions: currentQuestions });
      const result = examId
        ? await requestJson(session, "PATCH", `/api/app/exams/${examId}/`, requestPayload)
        : await requestJson(session, "POST", "/api/app/exams/autosave/", requestPayload);

      const newId = result?.exam?.id;
      if (newId && !examId) {
        const oldKey = localKeyRef.current;
        const newKey = localDraftKey("edit", newId);
        const existing = loadLocalDraft(oldKey);
        if (existing) saveLocalDraft(newKey, existing);
        clearLocalDraft(oldKey);
        localKeyRef.current = newKey;
        setExamId(newId);
      }
      dirtyRef.current = false;
      setStatus("saved");
    } catch (err) {
      if (err?.isDuplicate) {
        // A concurrent save (e.g. the manual Save button) already hit this
        // endpoint - leave the status as-is, the next tick retries.
      } else if (err?.message === "Network error. Please check your connection." || (typeof navigator !== "undefined" && navigator.onLine === false)) {
        setStatus("offline");
      } else {
        setStatus("error");
      }
    } finally {
      syncingRef.current = false;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, session, examId, buildAutosavePayload]);

  useEffect(() => {
    if (!enabled) return undefined;
    const interval = window.setInterval(runSync, BACKEND_SYNC_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [enabled, runSync]);

  useEffect(() => {
    if (!enabled) return undefined;
    const handleOnline = () => runSync();
    const handleVisibility = () => {
      if (document.visibilityState === "hidden") runSync();
    };
    window.addEventListener("online", handleOnline);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("online", handleOnline);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [enabled, runSync]);

  useEffect(() => {
    return () => {
      // Best-effort sync on unmount (tab switch away from the builder, etc.) -
      // fire and forget, the local draft already has everything either way.
      runSync();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const clearDraft = useCallback(() => clearLocalDraft(localKeyRef.current), []);

  return { status, examId, setExamId, restoredNotice, setRestoredNotice, clearDraft, localKeyRef };
}
