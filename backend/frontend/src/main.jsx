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
import "./teacher/teacher-overlays.css";
import "./pwa";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element not found.");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
