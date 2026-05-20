const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("schoolDomDesktop", {
  client: "student-cbt",
  desktopOnly: true,
});
