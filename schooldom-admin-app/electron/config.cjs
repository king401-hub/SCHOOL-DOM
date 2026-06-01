const path = require("path");
const { app } = require("electron");

const APP_NAME = "SchoolDom Admin";
const DEFAULT_SERVER_URL = process.env.SCHOOLDOM_SERVER_URL || "https://schooldom.academy";

function dataPath(...segments) {
  const basePath = app?.getPath ? app.getPath("userData") : path.join(process.cwd(), ".schooldom-admin-data");
  return path.join(basePath, ...segments);
}

module.exports = {
  APP_NAME,
  DEFAULT_SERVER_URL,
  dataPath,
};
