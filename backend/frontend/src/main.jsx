import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";
import "./teacher/teacher-studio.css";
import "./teacher/teacher-shell.css";
import "./teacher/teacher-home.css";
import "./teacher/teacher-pages.css";
import "./teacher/teacher-timetable.css";
import "./teacher/teacher-attendance.css";
import "./teacher/teacher-exams.css";
import "./teacher/teacher-results.css";
import "./teacher/teacher-inbox.css";
import "./teacher/teacher-planning.css";
import "./teacher/teacher-builder.css";
import "./teacher/teacher-quizzes.css";
import "./teacher/teacher-overlays.css";
import "./teacher/teacher-studio-admin.css";
import "./pwa";

// A lazy-loaded chunk (e.g. jszip/jsPDF/html2canvas in AdminScreens' bulk ID
// card export) is requested by the exact asset hash baked into whichever
// build this tab first loaded. A deploy since then replaces the whole
// dist/assets/ folder with new hashes, so a tab left open across a deploy
// can ask the server for a chunk that no longer exists there - Vite fires
// this event specifically for that failure ("Failed to fetch dynamically
// imported module"). Reloading fetches a fresh index.html pointing at the
// CURRENT hashes, which resolves it. The sessionStorage flag stops a
// genuinely broken deploy from trapping the tab in a reload loop; it's
// cleared a few seconds after a clean load so a stale-chunk error from a
// LATER deploy, in the same long-lived tab, can still self-heal.
const STALE_CHUNK_RELOAD_KEY = "schooldom.reloaded_after_stale_chunk";
window.addEventListener("vite:preloadError", () => {
  if (window.sessionStorage.getItem(STALE_CHUNK_RELOAD_KEY)) return;
  window.sessionStorage.setItem(STALE_CHUNK_RELOAD_KEY, "1");
  window.location.reload();
});
window.setTimeout(() => {
  try {
    window.sessionStorage.removeItem(STALE_CHUNK_RELOAD_KEY);
  } catch {
    // Private-browsing/sessionStorage-disabled - nothing to clean up.
  }
}, 10000);

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element not found.");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
