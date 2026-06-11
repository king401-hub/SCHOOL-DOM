import { useState } from "react";
import { SUPPORT_EMAIL, SUPPORT_MAILTO } from "./appConstants";

function Logo() {
  return (
    <svg className="logo" viewBox="0 0 40 40" aria-hidden="true">
      <path d="M8 20v12h8v-6h8v6h8V20L20 10 8 20Z" fill="currentColor" />
    </svg>
  );
}

function TermsConditionsPage({ onNavigate }) {
  const [theme, setTheme] = useState("light");

  const goHome = () => {
    if (typeof onNavigate === "function") {
      onNavigate("/");
      return;
    }
    window.location.href = "/";
  };

  return (
    <div className={`privacy-page ${theme === "light" ? "theme-light" : ""}`}>
      <header className="privacy-header">
        <div className="privacy-header-content">
          <div className="privacy-brand">
            <button type="button" className="privacy-back-button" onClick={goHome} aria-label="Back to home">
              Back
            </button>
            <Logo />
            <span>SchoolDom</span>
          </div>
          <div className="privacy-header-actions">
            <button
              type="button"
              className="privacy-theme-button"
              onClick={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
              aria-label="Toggle theme"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                {theme === "light" ? <circle cx="12" cy="12" r="4.5" /> : <path d="M20.4 15.4A8.5 8.5 0 0 1 8.6 3.6a8.5 8.5 0 1 0 11.8 11.8Z" />}
              </svg>
            </button>
          </div>
        </div>
      </header>

      <section className="privacy-hero">
        <div className="privacy-hero-content">
          <h1 className="privacy-hero-title">Terms and Conditions</h1>
          <p className="privacy-hero-subtitle">Last updated: June 11, 2026</p>
        </div>
      </section>

      <section className="privacy-content">
        <div className="privacy-container">
          <div className="privacy-document">
            <section className="privacy-section">
              <h2>1. Acceptance of Terms</h2>
              <p>
                By creating an account or using SchoolDom, you agree to follow these Terms and Conditions. If you do not agree, you should not create an account or use the service.
              </p>
            </section>

            <section className="privacy-section">
              <h2>2. Account Responsibility</h2>
              <p>
                Users are responsible for keeping account details safe and for all activity performed through their accounts. Schools are responsible for approving, managing, and disabling staff or student accounts when needed.
              </p>
            </section>

            <section className="privacy-section">
              <h2>3. School Data</h2>
              <p>
                Schools remain responsible for the accuracy of student records, attendance, results, fees, exams, and other data entered into SchoolDom. SchoolDom provides tools to manage this information but does not replace the school&apos;s administrative responsibility.
              </p>
            </section>

            <section className="privacy-section">
              <h2>4. Acceptable Use</h2>
              <ul>
                <li>Do not use SchoolDom for fraud, impersonation, harassment, or unauthorized access.</li>
                <li>Do not upload illegal, harmful, or abusive content.</li>
                <li>Do not attempt to bypass exam security, attendance controls, or account activation rules.</li>
                <li>Do not interfere with the platform, servers, or other users.</li>
              </ul>
            </section>

            <section className="privacy-section">
              <h2>5. CBT and Exam Integrity</h2>
              <p>
                Students must follow exam rules set by their school. Attempting to cheat, leave a secured exam page, manipulate exam data, or bypass security checks may lead to auto-submission or disciplinary action by the school.
              </p>
            </section>

            <section className="privacy-section">
              <h2>6. Payments and Tokens</h2>
              <p>
                Schools are responsible for reviewing purchases, activation tokens, fees, and student payment records. Payment availability and pricing may vary by school type and active platform settings.
              </p>
            </section>

            <section className="privacy-section">
              <h2>7. Changes to Terms</h2>
              <p>
                We may update these Terms and Conditions when the platform, law, or school requirements change. Continued use of SchoolDom after updates means you accept the revised terms.
              </p>
            </section>

            <section className="privacy-section">
              <h2>8. Contact</h2>
              <p>
                For questions about these Terms and Conditions, contact us at{" "}
                <a href={SUPPORT_MAILTO}>{SUPPORT_EMAIL}</a>.
              </p>
            </section>
          </div>
        </div>
      </section>
    </div>
  );
}

export default TermsConditionsPage;
