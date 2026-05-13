import { useState } from "react";

function Logo() {
  return (
    <svg className="logo" viewBox="0 0 40 40" aria-hidden="true">
      <path d="M8 20v12h8v-6h8v6h8V20L20 10 8 20Z" fill="currentColor" />
    </svg>
  );
}

function PricingPage({ onNavigate }) {
  const [theme, setTheme] = useState("dark");
  const goToSignup = () => onNavigate?.("/signin");
  const features = [
    "School admin dashboard",
    "Teacher and student portals",
    "CBT exams and class tests",
    "Daily student personal quizzes",
    "Global quiz question pools",
    "Result entry, approval, and report cards",
    "Transcript and testimonial generation",
    "Student and staff ID cards with QR verification",
    "Finance, wallet, fee, bill, receipt, and expense records",
    "Expense tracker for school spending",
    "Attendance for students and staff",
    "Messaging, announcements, and notifications",
    "Class, subject, teacher, staff, and enrollment management",
  ];

  return (
    <div className={`landing-page pricing-page ${theme === "light" ? "theme-light" : ""}`}>
      <header className="landing-header">
        <div className="header-content">
          <a href="/" className="logo-brand">
            <Logo />
            <span>SchoolDom</span>
          </a>

          <nav className="header-nav">
            <a href="/resource" className="nav-link">Resource Center</a>
            <a href="/pricing" className="nav-link">Pricing</a>
            <a href="/#about" className="nav-link">About</a>
          </nav>

          <button
            type="button"
            className="theme-button-landing"
            onClick={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
            aria-label="Toggle theme"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              {theme === "light" ? <circle cx="12" cy="12" r="4.5" /> : <path d="M20.4 15.4A8.5 8.5 0 0 1 8.6 3.6a8.5 8.5 0 1 0 11.8 11.8Z" />}
            </svg>
          </button>
        </div>
      </header>

      <main className="pricing-page-main">
        <section className="pricing-showcase-section">
          <div className="pricing-showcase-container">
            <div className="pricing-showcase-copy">
              <span className="pricing-eyebrow">SchoolDom plan</span>
              <h1>Pricing Plans For Everyone</h1>
              <p>
                SchoolDom uses one simple token-based pricing model for student access and document generation.
              </p>
            </div>

            <article className="single-pricing-card">
              <div className="single-pricing-head">
                <div>
                  <span className="pricing-label">School Plan</span>
                  <h2>Complete Platform</h2>
                  <small>For schools running CBT, results, records, finance, attendance, and documents.</small>
                </div>
                <div className="pricing-card-glyph" aria-hidden="true">◇</div>
              </div>

              <div className="token-price-block">
                <span>Activation token</span>
                <strong>₦200</strong>
                <small>per student access token</small>
              </div>

              <p className="pricing-charge-title">Additional document charges</p>
              <div className="pricing-charge-grid">
                <div>
                  <span>Transcript</span>
                  <strong>1 token</strong>
                </div>
                <div>
                  <span>Testimonial</span>
                  <strong>1 token</strong>
                </div>
                <div>
                  <span>ID Card</span>
                  <strong>1 token</strong>
                </div>
              </div>

              <ul className="pricing-features single-pricing-features">
                {features.map((feature) => (
                  <li key={feature}>{feature}</li>
                ))}
              </ul>

              <button type="button" className="pricing-action" onClick={goToSignup}>
                Get Started
              </button>
              <p className="pricing-footnote">New schools receive free starter activation tokens during setup.</p>
            </article>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="footer-content">
          <div className="footer-section">
            <h4>SchoolDom</h4>
            <p>The future of educational assessments.</p>
          </div>
          <div className="footer-section">
            <h4>Quick Links</h4>
            <ul>
              <li><a href="/resource">Resources</a></li>
              <li><a href="/pricing">Pricing</a></li>
              <li><a href="/#about">About</a></li>
            </ul>
          </div>
          <div className="footer-section">
            <h4>Support</h4>
            <ul>
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

export default PricingPage;
