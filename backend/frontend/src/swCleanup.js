if ("serviceWorker" in navigator) {
  window.addEventListener("load", async () => {
    try {
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.all(registrations.map((registration) => registration.unregister()));

      if ("caches" in window) {
        const keys = await caches.keys();
        await Promise.all(
          keys
            .filter((key) => key.startsWith("schooldom-pwa-"))
            .map((key) => caches.delete(key))
        );
      }

      console.info("Old SchoolDom service workers cleared.");
    } catch (error) {
      console.warn("Service worker cleanup failed.", error);
    }
  });
}
