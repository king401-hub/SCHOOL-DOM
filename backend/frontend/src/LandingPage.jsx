import { useState } from "react";
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
  const [activeFeature, setActiveFeature] = useState("students");

  const featureTabs = [
    {
      id: "students",
      icon: "SM",
      title: "Student Management",
      tag: "Core Engine",
      text: "Unified bio-data, academic histories, health notes, and parent communication logs in one click.",
      metric: "420,000+",
    },
    {
      id: "cbt",
      icon: "CBT",
      title: "CBT Examinations",
      tag: "Popular",
      text: "Uncompromised, anti-cheat, high-capacity Computer Based Testing engine with robust reporting.",
      metric: "99.9%",
    },
    {
      id: "attendance",
      icon: "AT",
      title: "Attendance Tracking",
      tag: "Real-Time",
      text: "Automated biometric, card-tap, QR, and mobile sheet attendance with instant alerts.",
      metric: "Live",
    },
    {
      id: "finance",
      icon: "NGN",
      title: "Finance & Fees",
      tag: "Financials",
      text: "Flexible customizable payment items, invoice dispatch, and graphical ledger dashboards.",
      metric: "Auto",
    },
    {
      id: "results",
      icon: "RS",
      title: "Result Management",
      tag: "Insights",
      text: "Grade books, automated report cards, performance diagnostics, and parent-ready summaries.",
      metric: "360",
    },
  ];
  const selectedFeature = featureTabs.find((item) => item.id === activeFeature) || featureTabs[0];

  const handleGetStarted = () => {
    if (typeof onGetStarted === "function") {
      onGetStarted();
    }
  };

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
            <a href="#features" className="nav-link">Features</a>
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

          <div className="landing-hero-actions">
            <button type="button" className="landing-cta" onClick={handleGetStarted}>
              Get Started for Free
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 12h14M12 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
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

      <section id="features" className="landing-sandbox-section">
        <div className="landing-sandbox-shell">
          <div className="landing-feature-list">
            {featureTabs.map((feature) => (
              <button
                key={feature.id}
                type="button"
                className={`landing-feature-tab ${activeFeature === feature.id ? "active" : ""}`}
                onClick={() => setActiveFeature(feature.id)}
              >
                <span className="landing-feature-icon">{feature.icon}</span>
                <span className="landing-feature-copy">
                  <strong>
                    {feature.title}
                    <small>{feature.tag}</small>
                  </strong>
                  <em>{feature.text}</em>
                </span>
                <span className="landing-feature-arrow">&gt;</span>
              </button>
            ))}
          </div>
          <div className="landing-sandbox-preview">
            <div className="landing-sandbox-head">
              <div>
                <h2>{selectedFeature.title} Sandbox</h2>
                <p>
                  SchoolDom gives each school a cohesive operating system for records, CBT, finance,
                  attendance, messages, and performance visibility.
                </p>
              </div>
              <span>{selectedFeature.metric}</span>
            </div>
            <div className="landing-student-preview">
              <div className="landing-preview-search">Type name, class, ID, or parent contact...</div>
              <div className="landing-preview-list">
                {["Fatima Yusuf Ahmed", "Aisha Al-Maktoum", "Zainab Danladi"].map((name, index) => (
                  <button key={name} type="button" className={index === 2 ? "selected" : ""}>
                    <span>{name}</span>
                    <strong>Active</strong>
                  </button>
                ))}
              </div>
              <article className="landing-id-card">
                <div className="landing-id-avatar">IMG</div>
                <div>
                  <h3>Zainab Danladi</h3>
                  <p>JSS1-Gold</p>
                </div>
                <small>Admission standard token</small>
                <strong>#SD-28-1110</strong>
                <div className="landing-barcode" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                </div>
              </article>
            </div>
            <div className="landing-preview-checks">
              {[
                "Comprehensive digital registration and profile timelines",
                "Barcode and QR active standard student IDs",
                "One-tap parent and emergency contact records",
                "Unified disciplinary logs and health emergency notes",
              ].map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          </div>
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
                <div className="benefit-icon">ST</div>
                <h4>For Students</h4>
                <p>Practice anywhere, anytime. Get instant feedback, detailed analytics, and personalized learning paths to improve performance.</p>
              </div>
              <div className="benefit-item">
                <div className="benefit-icon">TC</div>
                <h4>For Teachers</h4>
                <p>Create assessments effortlessly. Track student progress in real-time and identify learning gaps to provide targeted support.</p>
              </div>
              <div className="benefit-item">
                <div className="benefit-icon">SC</div>
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
