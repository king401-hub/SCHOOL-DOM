const { contextBridge, ipcRenderer } = require("electron");

const channels = {
  invoke: new Set([
    "app:bootstrap",
    "admin:syncFromCloud",
    "admin:pushResults",
    "admin:cleanupCache",
    "admin:getSnapshot",
    "admin:getLogs",
    "admin:saveOfflineSettings",
    "admin:importExamPackage",
    "admin:exportResultsPackage",
    "student:login",
    "student:getExam",
    "student:saveAnswers",
    "student:submit",
    "student:focusLoss",
    "window:enterFullscreen",
    "window:exitFullscreen",
  ]),
};

function invoke(channel, payload) {
  if (!channels.invoke.has(channel)) {
    throw new Error(`IPC channel is not allowed: ${channel}`);
  }
  return ipcRenderer.invoke(channel, payload);
}

contextBridge.exposeInMainWorld("schoolDomCbt", {
  bootstrap: () => invoke("app:bootstrap"),
  admin: {
    syncFromCloud: (payload) => invoke("admin:syncFromCloud", payload),
    pushResults: (payload) => invoke("admin:pushResults", payload),
    cleanupCache: () => invoke("admin:cleanupCache"),
    getSnapshot: () => invoke("admin:getSnapshot"),
    getLogs: () => invoke("admin:getLogs"),
    saveOfflineSettings: (payload) => invoke("admin:saveOfflineSettings", payload),
    importExamPackage: () => invoke("admin:importExamPackage"),
    exportResultsPackage: () => invoke("admin:exportResultsPackage"),
  },
  student: {
    login: (payload) => invoke("student:login", payload),
    getExam: (examId) => invoke("student:getExam", examId),
    saveAnswers: (payload) => invoke("student:saveAnswers", payload),
    submit: (payload) => invoke("student:submit", payload),
    focusLoss: (payload) => invoke("student:focusLoss", payload),
  },
  window: {
    enterFullscreen: () => invoke("window:enterFullscreen"),
    exitFullscreen: () => invoke("window:exitFullscreen"),
  },
});
