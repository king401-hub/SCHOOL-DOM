const PWA_STATUS_EVENT = "schooldom-pwa-install-status";
let deferredInstallPrompt = null;

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
        ...extra,
      },
    })
  );
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
    emitInstallStatus({ serviceWorkerReady: true, registration });

    registration.addEventListener("updatefound", () => {
      const installingWorker = registration.installing;
      installingWorker?.addEventListener("statechange", () => {
        if (installingWorker.state === "installed" && navigator.serviceWorker.controller) {
          emitInstallStatus({ updateAvailable: true });
        }
      });
    });
  } catch (error) {
    console.warn("SchoolDom PWA service worker registration failed.", error);
    emitInstallStatus({ serviceWorkerReady: false, error });
  }
}

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
  getStatus() {
    return {
      canInstall: Boolean(deferredInstallPrompt),
      isInstalled: isStandaloneMode(),
      notificationPermission: "Notification" in window ? Notification.permission : "unsupported",
      serviceWorkerSupported: "serviceWorker" in navigator,
    };
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

if (document.readyState === "complete") {
  registerServiceWorker();
} else {
  window.addEventListener("load", registerServiceWorker, { once: true });
}

emitInstallStatus();
