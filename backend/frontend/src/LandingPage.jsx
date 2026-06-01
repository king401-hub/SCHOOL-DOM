import { useEffect, useState } from "react";
import { SUPPORT_EMAIL, SUPPORT_MAILTO } from "./appConstants";

function Logo() {
  return (
    <svg className="logo" viewBox="0 0 40 40" aria-hidden="true">
      <path d="M8 20v12h8v-6h8v6h8V20L20 10 8 20Z" fill="currentColor" />
    </svg>
  );
}

function LandingPage({ onGetStarted }) {
  const [theme, setTheme] = useState("dark");
  const [pwaStatus, setPwaStatus] = useState(() =>
    typeof window !== "undefined" && window.schoolDomPWA
      ? window.schoolDomPWA.getStatus()
      : {
          canInstall: false,
          isInstalled: false,
          notificationPermission: "default",
          serviceWorkerSupported: false,
          updateAvailable: false,
        }
  );
  const [installMessage, setInstallMessage] = useState("");
  const [notificationMessage, setNotificationMessage] = useState("");

  const handleGetStarted = () => {
    if (typeof onGetStarted === "function") {
      onGetStarted();
    }
  };

  useEffect(() => {
    const syncStatus = (event) => {
      setPwaStatus((previous) => ({
        ...previous,
        ...(window.schoolDomPWA?.getStatus?.() || {}),
        ...(event?.detail || {}),
      }));
    };

    syncStatus();
    window.addEventListener("schooldom-pwa-install-status", syncStatus);
    return () => window.removeEventListener("schooldom-pwa-install-status", syncStatus);
  }, []);

  const handleInstallApp = async () => {
    setInstallMessage("");
    if (!window.schoolDomPWA) {
      setInstallMessage("Open this site in Chrome, Edge, or Safari to install the app.");
      return;
    }

    const result = await window.schoolDomPWA.install();
    if (result?.outcome === "accepted" || result?.outcome === "installed") {
      setInstallMessage("SchoolDom is ready as an installed app.");
    } else if (result?.outcome === "dismissed") {
      setInstallMessage("Install was cancelled. You can try again anytime.");
    } else {
      setInstallMessage("On iPhone or iPad, use Share, then Add to Home Screen.");
    }

    setPwaStatus(window.schoolDomPWA.getStatus());
  };

  const handleEnableNotifications = async () => {
    setNotificationMessage("");
    if (!window.schoolDomPWA) {
      setNotificationMessage("Notifications are not available in this browser.");
      return;
    }

    const permission = await window.schoolDomPWA.requestNotifications();
    if (permission === "granted") {
      setNotificationMessage("Notifications are enabled for this device.");
    } else if (permission === "denied") {
      setNotificationMessage("Notifications are blocked in this browser.");
    } else {
      setNotificationMessage("Notifications are not supported on this device.");
    }

    setPwaStatus(window.schoolDomPWA.getStatus());
  };

  const handleUpdateApp = async () => {
    setInstallMessage("Updating SchoolDom...");
    if (!window.schoolDomPWA?.updateApp) {
      setInstallMessage("Close and reopen the app to finish updating.");
      return;
    }
    const result = await window.schoolDomPWA.updateApp();
    if (!result?.updated) {
      setInstallMessage("Checking for the latest version. The app will reload if an update is ready.");
    }
  };

  const installButtonText = pwaStatus.isInstalled
    ? "App Installed"
    : pwaStatus.canInstall
      ? "Install App"
      : "Install on Device";

  return (
    <div className={`landing-page ${theme === "light" ? "theme-light" : ""}`}>
      {/* Header */}
      <header className="landing-header">
        <div className="header-content">
          <div className="logo-brand">
            <Logo />
            <span>SchoolDom</span>
          </div>

          <nav className="header-nav">
            <a href="/pricing" className="nav-link">Pricing</a>
            <a href="#about" className="nav-link">About</a>
          </nav>

          <button
            type="button"
            className="theme-button-landing"
            onClick={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
            aria-label="Toggle theme"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              {theme === "light" ? (
                <circle cx="12" cy="12" r="4.5" />
              ) : (
                <path d="M20.4 15.4A8.5 8.5 0 0 1 8.6 3.6a8.5 8.5 0 1 0 11.8 11.8Z" />
              )}
            </svg>
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-content">
          <h1 className="hero-title">
            The Future of Assessments
            <br />
            Empowered by <span className="highlight">SchoolDom</span>
          </h1>

          <p className="hero-subtitle">
            A next-generation CBT platform designed for integrity, scaled with intelligence, and built to empower educators and students worldwide.
          </p>

          <div className="hero-actions">
            <button type="button" className="btn btn-primary" onClick={handleGetStarted}>
              Get Started for Free
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 12h14M12 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleInstallApp}
              disabled={pwaStatus.isInstalled}
            >
              {installButtonText}
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 3v12m0 0 5-5m-5 5-5-5M5 21h14" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            {pwaStatus.updateAvailable ? (
              <button type="button" className="btn btn-secondary" onClick={handleUpdateApp}>
                Update App
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M4 12a8 8 0 0 1 13.7-5.7M20 12a8 8 0 0 1-13.7 5.7M17 3v4h-4M7 21v-4h4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            ) : null}
          </div>

          <div className="mobile-app-panel" aria-live="polite">
            <div>
              <p className="mobile-app-kicker">SchoolDom Mobile App</p>
              <p>
                Install SchoolDom for a focused student CBT experience. Students can open assigned exams, answer questions, and submit securely from their device.
              </p>
              <ul className="mobile-app-feature-list">
                <li>Install SchoolDom directly on student devices</li>
                <li>Open assigned CBT exams with secure student login</li>
                <li>Answer objective and theory questions in the exam app</li>
                <li>Submit attempts securely when the exam is complete</li>
                <li>Use the school name and logo when installed from the school admin page</li>
                <li>Designed for Android and supported desktop browsers</li>
              </ul>
            </div>
            {installMessage ? <p className="mobile-app-message">{installMessage}</p> : null}
            {notificationMessage ? <p className="mobile-app-message">{notificationMessage}</p> : null}
          </div>

          <div className="hero-stats">
            <div className="stat">
              <span className="stat-icon"></span>
              <span className="stat-text">INTEGRITY SECURED</span>
            </div>
          </div>
        </div>

        {/* Decorative elements */}
        <div className="hero-decoration">
          <div className="decoration-blob blob-1" />
          <div className="decoration-blob blob-2" />
          <div className="decoration-blob blob-3" />
        </div>
      </section>
      
      {/* About Section */}
      <section id="about" className="about-section">
        <div className="section-container">
          <h2 className="section-title">About SchoolDom</h2>
          
          <div className="about-content">
            <div className="about-text">
              <h3>Transforming Education Through Technology</h3>
              <p>
                SchoolDom is a next-generation Computer-Based Testing (CBT) platform designed to revolutionize how educational institutions assess student performance. We believe in integrity, transparency, and the power of data-driven education.
              </p>
            </div>

            <div className="benefits-grid">
              <div className="benefit-item">
                <div className="benefit-icon">👨‍🎓</div>
                <h4>For Students</h4>
                <p>Practice anywhere, anytime. Get instant feedback, detailed analytics, and personalized learning paths to improve performance.</p>
              </div>
              <div className="benefit-item">
                <div className="benefit-icon">👨‍🏫</div>
                <h4>For Teachers</h4>
                <p>Create assessments effortlessly. Track student progress in real-time and identify learning gaps to provide targeted support.</p>
              </div>
              <div className="benefit-item">
                <div className="benefit-icon">🏫</div>
                <h4>For Schools</h4>
                <p>Manage entire testing operations seamlessly. Generate reports, monitor system integrity, and scale with millions of students.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-content">
          <div className="footer-section">
            <h4>SchoolDom</h4>
            <p>The future of educational assessments.</p>
          </div>
          <div className="footer-section">
            <h4>Quick Links</h4>
            <ul>
              <li><a href="/pricing">Pricing</a></li>
              <li><a href="#about">About</a></li>
              <li><a href="#">Features</a></li>
            </ul>
          </div>
          <div className="footer-section">
            <h4>Support</h4>
            <ul>
              <li><a href={SUPPORT_MAILTO}>{SUPPORT_EMAIL}</a></li>
              <li><a href="/privacy">Privacy Policy</a></li>
              <li><a href="/faq">Help & FAQ</a></li>
            </ul>
          </div>
        </div>
        <div className="footer-bottom">
          <p>&copy; 2026 SchoolDom. The Future of Assessments.</p>
        </div>
      </footer>
    </div>
  );
}

export default LandingPage;
