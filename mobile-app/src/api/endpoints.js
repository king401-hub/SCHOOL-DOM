import { deleteJson, getJson, postJson } from "./client";

export function loadDashboard(role) {
  if (role === "student") return getJson("/api/app/student/dashboard/");
  if (role === "teacher") return getJson("/api/app/teacher/dashboard/");
  if (role === "staff") return getJson("/api/hr/me/");
  return getJson("/api/app/dashboard/");
}

export const loadMessages = () => getJson("/api/app/messages/");
export const sendMessage = (payload) => postJson("/api/app/messages/send/", payload, { queueWhenOffline: true });
export const loadExams = () => getJson("/api/app/exams/");
export const loadResults = () => getJson("/api/app/results/my/");
export const markAttendance = (payload) => postJson("/api/app/attendance/mark/", payload, { queueWhenOffline: true });
export const registerDevice = (payload) => postJson("/api/app/mobile/device/", payload);
export const loadExpenses = () => getJson("/api/finance/admin/expenses/");
export const createExpenseRecord = (payload) => postJson("/api/finance/admin/expenses/", payload, { queueWhenOffline: true });
export const deleteExpenseRecord = (recordId) => deleteJson(`/api/finance/admin/expenses/${recordId}/`, { queueWhenOffline: true });
