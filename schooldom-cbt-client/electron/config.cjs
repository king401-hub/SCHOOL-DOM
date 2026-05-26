const path = require("path");
const { app } = require("electron");

const APP_NAME = "SchoolDom CBT Client";
const DEFAULT_CLOUD_URL = process.env.SCHOOLDOM_CLOUD_URL || "https://schooldom.academy";

function dataPath(...segments) {
  const basePath = app?.getPath ? app.getPath("userData") : path.join(process.cwd(), ".schooldom-cbt-data");
  return path.join(basePath, ...segments);
}

module.exports = {
  APP_NAME,
  DEFAULT_CLOUD_URL,
  dataPath,
};
