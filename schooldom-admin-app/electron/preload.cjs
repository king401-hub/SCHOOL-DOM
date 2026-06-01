const { contextBridge, ipcRenderer } = require("electron");

const allowedInvokeChannels = new Set([
  "app:bootstrap",
  "app:settings",
  "app:saveSettings",
  "app:openCbtInstaller",
]);

function invoke(channel, payload) {
  if (!allowedInvokeChannels.has(channel)) {
    throw new Error(`IPC channel is not allowed: ${channel}`);
  }
  return ipcRenderer.invoke(channel, payload);
}

contextBridge.exposeInMainWorld("schoolDomAdmin", {
  bootstrap: (payload) => invoke("app:bootstrap", payload),
  settings: () => invoke("app:settings"),
  saveSettings: (payload) => invoke("app:saveSettings", payload),
  openCbtInstaller: (payload) => invoke("app:openCbtInstaller", payload),
});
