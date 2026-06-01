const PWA_STATUS_EVENT = "schooldom-pwa-install-status";
const PWA_BRAND_KEY = "schooldom.pwa_brand";
let deferredInstallPrompt = null;
let currentManifestUrl = "";
let serviceWorkerRegistration = null;
let updateAvailable = false;
let applyingUpdate = false;

const defaultBrand = {
  name: "SchoolDom",
  shortName: "SchoolDom",
  description: "SchoolDom exam app.",
  icon: "/schooldom-favicon.jpeg",
};

function isStandaloneMode() {
  return (
    window.matchMedia?.("(display-mode: standalone)")?.matches ||
    window.matchMedia?.("(display-mode: fullscreen)")?.matches ||
    window.navigator.standalone === true
  );
}

function emitInstallStatus(extra = {}) {
  window.dispatchEvent(
    new CustomEvent(PWA_STATUS_EVENT, {
      detail: {
        canInstall: Boolean(deferredInstallPrompt),
        isInstalled: isStandaloneMode(),
        supportsInstallPrompt: "BeforeInstallPromptEvent" in window || Boolean(deferredInstallPrompt),
        updateAvailable,
        ...extra,
      },
    })
  );
}

function toAbsoluteUrl(value) {
  if (!value) return "";
  try {
    return new URL(value, window.location.origin).href;
  } catch {
    return "";
  }
}

function normalizeBrand(brand = {}) {
  const name = String(brand.name || brand.school_name || brand.schoolName || defaultBrand.name).trim() || defaultBrand.name;
  const icon = toAbsoluteUrl(brand.logo || brand.logo_url || brand.logoUrl || brand.icon || defaultBrand.icon) || defaultBrand.icon;
  return {
    name,
    shortName: String(brand.shortName || brand.short_name || name).trim().slice(0, 24) || name.slice(0, 24),
    description: `${name} exam app.`,
    icon,
  };
}

function buildManifest(brand) {
  const appOrigin = window.location.origin;
  return {
    name: brand.name,
    short_name: brand.shortName,
    description: brand.description,
    id: `${appOrigin}/`,
    start_url: `${appOrigin}/?source=pwa`,
    scope: `${appOrigin}/`,
    display: "standalone",
    display_override: ["window-controls-overlay", "standalone", "fullscreen"],
    orientation: "portrait-primary",
    background_color: "#0f172a",
    theme_color: "#2563eb",
    categories: ["education", "productivity"],
    lang: "en",
    dir: "ltr",
    icons: [
      { src: brand.icon, sizes: "192x192", type: brand.icon.endsWith(".png") ? "image/png" : brand.icon.endsWith(".svg") ? "image/svg+xml" : "image/jpeg", purpose: "any" },
      { src: brand.icon, sizes: "512x512", type: brand.icon.endsWith(".png") ? "image/png" : brand.icon.endsWith(".svg") ? "image/svg+xml" : "image/jpeg", purpose: "any maskable" },
    ],
    shortcuts: [
      {
        name: "Student Exams",
        short_name: "Exams",
        url: "/exams",
        icons: [{ src: brand.icon, sizes: "192x192" }],
      },
    ],
  };
}

function updateDocumentBrand(brand) {
  document.title = brand.name;
  document.querySelector('meta[name="apple-mobile-web-app-title"]')?.setAttribute("content", brand.shortName);
  document.querySelector('link[rel="icon"]')?.setAttribute("href", brand.icon);
  document.querySelector('link[rel="shortcut icon"]')?.setAttribute("href", brand.icon);
  document.querySelector('link[rel="apple-touch-icon"]')?.setAttribute("href", brand.icon);
}

function updateManifest(brandInput = {}) {
  const brand = normalizeBrand(brandInput);
  const manifestLink = document.querySelector('link[rel="manifest"]');
  if (!manifestLink) return brand;

  const manifestBlob = new Blob([JSON.stringify(buildManifest(brand))], { type: "application/manifest+json" });
  const nextManifestUrl = URL.createObjectURL(manifestBlob);
  manifestLink.setAttribute("href", nextManifestUrl);
  if (currentManifestUrl) {
    URL.revokeObjectURL(currentManifestUrl);
  }
  currentManifestUrl = nextManifestUrl;
  updateDocumentBrand(brand);
  return brand;
}

function readStoredBrand() {
  try {
    return JSON.parse(window.localStorage.getItem(PWA_BRAND_KEY) || "null");
  } catch {
    window.localStorage.removeItem(PWA_BRAND_KEY);
    return null;
  }
}

async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    emitInstallStatus({ serviceWorkerReady: false });
    return;
  }

  try {
    const registration = await navigator.serviceWorker.register("/service-worker.js", {
      scope: "/",
    });
    serviceWorkerRegistration = registration;
    emitInstallStatus({ serviceWorkerReady: true, registration });

    registration.addEventListener("updatefound", () => {
      const installingWorker = registration.installing;
      installingWorker?.addEventListener("statechange", () => {
        if (installingWorker.state === "installed" && navigator.serviceWorker.controller) {
          updateAvailable = true;
          emitInstallStatus({ updateAvailable: true });
        }
      });
    });

    if (registration.waiting && navigator.serviceWorker.controller) {
      updateAvailable = true;
      emitInstallStatus({ updateAvailable: true });
    }
  } catch (error) {
    console.warn("SchoolDom PWA service worker registration failed.", error);
    emitInstallStatus({ serviceWorkerReady: false, error });
  }
}

navigator.serviceWorker?.addEventListener?.("controllerchange", () => {
  if (applyingUpdate) {
    window.location.reload();
  }
});

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
  emitInstallStatus();
});

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null;
  emitInstallStatus({ isInstalled: true });
});

window.schoolDomPWA = {
  PWA_STATUS_EVENT,
  setBrand(brandInput = {}) {
    const brand = updateManifest(brandInput);
    window.localStorage.setItem(PWA_BRAND_KEY, JSON.stringify(brand));
    emitInstallStatus({ brand });
    return brand;
  },
  getStatus() {
    return {
      canInstall: Boolean(deferredInstallPrompt),
      isInstalled: isStandaloneMode(),
      notificationPermission: "Notification" in window ? Notification.permission : "unsupported",
      serviceWorkerSupported: "serviceWorker" in navigator,
      updateAvailable,
      brand: readStoredBrand() || defaultBrand,
    };
  },
  async updateApp() {
    if (!("serviceWorker" in navigator)) {
      return { updated: false, reason: "unsupported" };
    }

    const registration = serviceWorkerRegistration || (await navigator.serviceWorker.ready);
    serviceWorkerRegistration = registration;
    applyingUpdate = true;

    if (registration.waiting) {
      registration.waiting.postMessage({ type: "SKIP_WAITING" });
      return { updated: true };
    }

    const nextRegistration = await registration.update();
    serviceWorkerRegistration = nextRegistration || registration;
    const waitingWorker = serviceWorkerRegistration.waiting;
    if (waitingWorker) {
      waitingWorker.postMessage({ type: "SKIP_WAITING" });
      return { updated: true };
    }

    window.location.reload();
    return { updated: false, reason: "reloaded" };
  },
  async install() {
    if (isStandaloneMode()) {
      return { outcome: "installed" };
    }
    if (!deferredInstallPrompt) {
      return { outcome: "unavailable" };
    }

    const promptEvent = deferredInstallPrompt;
    deferredInstallPrompt = null;
    promptEvent.prompt();
    const choice = await promptEvent.userChoice;
    emitInstallStatus();
    return choice;
  },
  async requestNotifications() {
    if (!("Notification" in window)) {
      return "unsupported";
    }
    if (!("serviceWorker" in navigator)) {
      return "unsupported";
    }

    const permission =
      Notification.permission === "default"
        ? await Notification.requestPermission()
        : Notification.permission;

    if (permission === "granted") {
      const registration = await navigator.serviceWorker.ready;
      try {
        await registration.showNotification("SchoolDom notifications are ready", {
          body: "You can receive school updates from the installed app.",
          icon: "/schooldom-favicon.jpeg",
          badge: "/schooldom-favicon.jpeg",
          tag: "schooldom-notifications-ready",
        });
      } catch (error) {
        console.warn("SchoolDom notification preview could not be shown.", error);
      }
    }

    emitInstallStatus({ notificationPermission: permission });
    return permission;
  },
  async getCurrentPosition(options = {}) {
    if (!("geolocation" in navigator)) {
      throw new Error("GPS is not supported on this device.");
    }
    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true,
        timeout: 12000,
        maximumAge: 30000,
        ...options,
      });
    });
  },
};

updateManifest(readStoredBrand() || defaultBrand);

if (document.readyState === "complete") {
  registerServiceWorker();
} else {
  window.addEventListener("load", registerServiceWorker, { once: true });
}

emitInstallStatus();
