export const SESSION_KEY = "schooldom.session";
export const LEGACY_SESSION_KEY = "educonnect.session";
export const UI_THEME_KEY = "schooldom.ui_theme";
export const PENDING_AUTH_REDIRECT_KEY = "schooldom.pending_auth_redirect";
export const SUPPORT_EMAIL = "support@schooldom.academy";
export const SUPPORT_MAILTO = `mailto:${SUPPORT_EMAIL}`;
export const API_BASE_URL = (() => {
  const raw = import.meta.env.VITE_API_BASE_URL ?? "";
  if (!raw) return ""; // use relative calls like /api/...
  const trimmed = raw.replace(/\/+$/, "");
  const withoutApi = trimmed.endsWith("/api") ? trimmed.slice(0, -4) : trimmed;
  if (withoutApi.startsWith("http://") || withoutApi.startsWith("https://")) {
    return withoutApi;
  }
  return `${window.location.protocol}//${window.location.host}${withoutApi.startsWith("/") ? withoutApi : `/${withoutApi}`}`;
})();
export const ID_CARD_VERIFY_PATH = "/id-cards/verify";
export const PUBLIC_ROUTES = new Set(["/", "/signin", "/login", "/forgot-password", "/reset-password", "/resource", "/pricing", "/faq", "/privacy", "/terms", ID_CARD_VERIFY_PATH]);
export const AUTH_ROUTES = new Set(["/signin", "/login", "/forgot-password", "/reset-password"]);
export const STUDENT_POLL_INTERVAL_MS = 60 * 1000;
export const TEACHER_POLL_INTERVAL_MS = 30 * 1000;
export const DEFAULT_POLL_INTERVAL_MS = 20 * 1000;
export const MESSAGE_POLL_INTERVAL_MS = 10 * 1000;
export const TEACHER_ATTENDANCE_PREFIX = "/attendance/scan/";
export const ADMIN_ROUTES = [
  { path: "/dashboard", label: "Dashboard" },
  { path: "/performance-heatmap", label: "Performance Analytics" },
  { path: "/finance", label: "Finance" },
  { path: "/expenses", label: "Expenses" },
  { path: "/attendance", label: "Attendance" },
  { path: "/hr/activity", label: "HR Management" },
  { path: "/students", label: "Students" },
  { path: "/parents", label: "Parent Directory" },
  { path: "/id-cards", label: "ID Cards" },
  { path: "/documents", label: "Transcripts & Testimonials" },
  {
    path: "/teachers",
    label: "Staffs",
    children: [
      { path: "/teachers", label: "Teachers" },
      { path: "/non-teaching-staff", label: "Non-Teaching Staff" },
    ]
  },
  { path: "/classes", label: "Classes" },
  { path: "/exams", label: "Exams" },
  { path: "/results", label: "Results" },
  { path: "/database-import", label: "Database Import" },
  { path: "/messages", label: "Messages" },
  { path: "/loan-application", label: "Loan Application" },
  { path: "/settings", label: "Settings" },
];
export const ACCOUNTANT_ROUTES = [
  { path: "/finance", label: "Finance" },
  { path: "/expenses", label: "Expenses" },
  { path: "/hr-self-service", label: "Payroll & Leave" },
  { path: "/messages", label: "Messages" },
];
export const ADMIN_ROUTE_SET = new Set([
  ...ADMIN_ROUTES.map((item) => item.path),
  ...ADMIN_ROUTES.filter((item) => item.children).flatMap((item) => item.children.map((child) => child.path)),
  ...ACCOUNTANT_ROUTES.map((item) => item.path)
]);
export const ADMIN_ROUTE_REDIRECTS = {
  "/hr": "/hr/activity",
};
export const ADMIN_ENDPOINTS = {
  "/dashboard": "/api/app/dashboard/",
  "/performance-heatmap": "/api/app/performance-heatmap/",
  "/finance": "/api/finance/admin/overview/",
  "/expenses": "/api/finance/admin/expenses/",
  "/hr-self-service": "/api/hr/self-service/",
  "/hr/activity": "/api/hr/overview/",
  "/non-teaching-staff": "/api/hr/overview/",
  "/students": "/api/app/students/",
  "/parents": "/api/app/parents/",
  "/id-cards": "/api/app/id-cards/",
  "/documents": "/api/app/documents/",
  "/teachers": "/api/app/teachers/",
  "/classes": "/api/app/classes/",
  "/subjects": "/api/app/classes/", // subjects included in classes snapshot
  "/exams": "/api/app/exams/",
  "/results": "/api/app/results/",
  "/database-import": "/api/app/database-imports/",
  "/messages": "/api/app/messages/",
  "/loan-application": "/api/app/loan-applications/",
  "/settings": "/api/app/school/settings/",
};
export const STUDENT_ROUTES = [
  { path: "/dashboard", label: "Dashboard" },
  { path: "/attendance", label: "Attendance" },
  { path: "/id-card", label: "ID Card" },
  { path: "/fees", label: "School Fees" },
  { path: "/exams", label: "Exams" },
  { path: "/quizzes", label: "Quizzes" },
  { path: "/academic-planning", label: "Academic Planning" },
  { path: "/messages", label: "Messages" },
  { path: "/results", label: "Results" },
];
export const STUDENT_ROUTE_SET = new Set(STUDENT_ROUTES.map((item) => item.path));
export const PARENT_ROUTES = [
  { path: "/dashboard", label: "Dashboard" },
  { path: "/fees", label: "School Fees" },
  { path: "/payments", label: "Payment History" },
];
export const PARENT_ROUTE_SET = new Set(PARENT_ROUTES.map((item) => item.path));
export const RECOMMENDED_SUBJECT_GROUPS = [
  {
    stream: "Science",
    subjects: [
      ["English Language", "ENG"],
      ["General Mathematics", "MATH"],
      ["Physics", "PHY"],
      ["Chemistry", "CHEM"],
      ["Biology", "BIO"],
      ["Further Mathematics", "FMATH"],
      ["Agricultural Science", "AGRIC"],
      ["Computer Studies", "COMP"],
      ["Geography", "GEO"],
      ["Civic Education", "CIV"],
    ],
  },
  {
    stream: "Art",
    subjects: [
      ["English Language", "ENG"],
      ["General Mathematics", "MATH"],
      ["Literature in English", "LIT"],
      ["Government", "GOV"],
      ["Christian Religious Studies", "CRS"],
      ["Islamic Religious Studies", "IRS"],
      ["History", "HIST"],
      ["Civic Education", "CIV"],
      ["Fine Arts", "ART"],
      ["Music", "MUS"],
    ],
  },
  {
    stream: "Commercial",
    subjects: [
      ["English Language", "ENG"],
      ["General Mathematics", "MATH"],
      ["Economics", "ECO"],
      ["Commerce", "COM"],
      ["Financial Accounting", "ACC"],
      ["Business Studies", "BUS"],
      ["Office Practice", "OFF"],
      ["Computer Studies", "COMP"],
      ["Government", "GOV"],
      ["Civic Education", "CIV"],
    ],
  },
];
