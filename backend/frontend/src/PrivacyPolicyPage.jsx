import { useState } from "react";
import { SUPPORT_EMAIL, SUPPORT_MAILTO } from "./appConstants";

function Logo() {
  return (
    <svg className="logo" viewBox="0 0 40 40" aria-hidden="true">
      <path d="M8 20v12h8v-6h8v6h8V20L20 10 8 20Z" fill="currentColor" />
    </svg>
  );
}

function PrivacyPolicyPage({ onNavigate }) {
  const [theme, setTheme] = useState("light");

  return (
    <div className={`privacy-page ${theme === "light" ? "theme-light" : ""}`}>
      {/* Header */}
      <header className="privacy-header">
        <div className="privacy-header-content">
          <div className="privacy-brand">
            <button 
              type="button"
              className="privacy-back-button"
              onClick={() => {
                if (typeof onNavigate === "function") {
                  onNavigate("/");
                } else {
                  window.location.href = "/";
                }
              }}
              aria-label="Back to home"
            >
              ←
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
                {theme === "light" ? (
                  <circle cx="12" cy="12" r="4.5" />
                ) : (
                  <path d="M20.4 15.4A8.5 8.5 0 0 1 8.6 3.6a8.5 8.5 0 1 0 11.8 11.8Z" />
                )}
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="privacy-hero">
        <div className="privacy-hero-content">
          <h1 className="privacy-hero-title">Privacy Policy</h1>
          <p className="privacy-hero-subtitle">Last updated: May 1, 2026</p>
        </div>
      </section>

      {/* Content */}
      <section className="privacy-content">
        <div className="privacy-container">
          <div className="privacy-document">
            <section className="privacy-section">
              <h2>1. Introduction</h2>
              <p>
                SchoolDom ("Company", "we", "us", or "our") operates the SchoolDom platform (the "Service"). This page informs you of our policies regarding the collection, use, and disclosure of personal data when you use our Service and the choices you have associated with that data.
              </p>
              <p>
                We are committed to protecting your privacy and ensuring you have a positive experience on our platform. This Privacy Policy explains our data practices and your privacy rights.
              </p>
            </section>

            <section className="privacy-section">
              <h2>2. Information Collection and Use</h2>
              
              <h3>2.1 Types of Data Collected</h3>
              <p><strong>Personal Data:</strong></p>
              <ul>
                <li>Name, email address, and phone number</li>
                <li>User account information and profile details</li>
                <li>School/institution affiliation and role</li>
                <li>Device information (browser type, IP address, device identifiers)</li>
                <li>Usage data and activity logs</li>
                <li>Assessment performance and grades (for students)</li>
                <li>Webcam and screen recording data (only during proctored exams, if enabled)</li>
              </ul>

              <p><strong>Sensitive Data (for proctoring purposes):</strong></p>
              <ul>
                <li>Biometric data (facial recognition for verification only)</li>
                <li>Screen recording and keyboard activity logs (only during assessments)</li>
                <li>Webcam feed (temporarily stored, then deleted after exam)</li>
              </ul>

              <h3>2.2 Purpose of Collection</h3>
              <p>We collect and use data for the following purposes:</p>
              <ul>
                <li>To provide and maintain the Service</li>
                <li>To create and authenticate user accounts</li>
                <li>To facilitate assessment creation, deployment, and grading</li>
                <li>To maintain assessment integrity through proctoring</li>
                <li>To generate performance analytics and reports</li>
                <li>To improve and optimize the platform</li>
                <li>To communicate with users regarding service updates</li>
                <li>To comply with legal and regulatory requirements</li>
              </ul>
            </section>

            <section className="privacy-section">
              <h2>3. Data Retention</h2>
              <p>
                SchoolDom retains personal data for as long as necessary to provide our Services and fulfill the purposes outlined in this policy. Retention periods vary based on data type:
              </p>
              <ul>
                <li><strong>User Account Data:</strong> Retained during active account status. Can be deleted upon request.</li>
                <li><strong>Assessment Data:</strong> Retained for institutional records (typically 7 years for compliance).</li>
                <li><strong>Webcam/Screen Recordings:</strong> Deleted 30 days after assessment completion unless flagged for integrity review.</li>
                <li><strong>Activity Logs:</strong> Retained for 2 years for security and audit purposes.</li>
              </ul>
              <p>
                Users can request data deletion at any time. We will comply within 30 days, except where retention is required by law.
              </p>
            </section>

            <section className="privacy-section">
              <h2>4. Data Security</h2>
              <p>
                The security of your data is important to us, but remember that no method of transmission over the Internet or electronic storage is 100% secure. While we strive to use commercially acceptable means to protect your Personal Data, we cannot guarantee its absolute security.
              </p>
              <p><strong>Security Measures We Implement:</strong></p>
              <ul>
                <li>End-to-end encryption for data transmission (SSL/TLS)</li>
                <li>Encrypted storage of sensitive data at rest</li>
                <li>Regular security audits and penetration testing</li>
                <li>Multi-factor authentication options</li>
                <li>Role-based access control</li>
                <li>Automatic backups with disaster recovery protocols</li>
                <li>Compliance with OWASP security standards</li>
              </ul>
            </section>

            <section className="privacy-section">
              <h2>5. Data Sharing and Disclosure</h2>
              <p>
                We do not sell, trade, or rent your personal data to third parties. However, we may share data in the following circumstances:
              </p>
              <ul>
                <li><strong>School Administration:</strong> School administrators can access student performance data for institutional purposes.</li>
                <li><strong>Service Providers:</strong> We may share data with third-party service providers (hosting, analytics) under strict confidentiality agreements.</li>
                <li><strong>Legal Requirements:</strong> We may disclose data if required by law or to protect our legal rights.</li>
                <li><strong>School Officials:</strong> For authorized educational purposes (grades, disciplinary action, etc.)</li>
              </ul>
            </section>

            <section className="privacy-section">
              <h2>6. User Rights (GDPR & CCPA Compliance)</h2>
              <p>
                Depending on your location, you may have the following rights regarding your personal data:
              </p>
              <ul>
                <li><strong>Right to Access:</strong> You can request a copy of all personal data we hold about you.</li>
                <li><strong>Right to Rectification:</strong> You can correct inaccurate or incomplete data.</li>
                <li><strong>Right to Erasure:</strong> You can request deletion of your data (subject to legal requirements).</li>
                <li><strong>Right to Data Portability:</strong> You can request your data in a structured, machine-readable format.</li>
                <li><strong>Right to Opt-Out:</strong> You can opt out of marketing communications and certain data processing activities.</li>
                <li><strong>Right to Withdraw Consent:</strong> You can withdraw consent for data processing at any time.</li>
              </ul>
              <p>
                To exercise any of these rights, please contact us at <a href={SUPPORT_MAILTO}>{SUPPORT_EMAIL}</a> with proof of identity.
              </p>
            </section>

            <section className="privacy-section">
              <h2>7. Proctoring and Surveillance</h2>
              <p>
                SchoolDom uses advanced proctoring features to maintain assessment integrity. The following practices apply:
              </p>
              <ul>
                <li><strong>Webcam Monitoring:</strong> Optional webcam monitoring to verify student identity and detect suspicious activity.</li>
                <li><strong>Screen Recording:</strong> Optional screen recording to monitor what appears on the student's screen during exams.</li>
                <li><strong>Keyboard Activity:</strong> Tracking typing speed and patterns (not recording actual keystrokes).</li>
                <li><strong>AI Detection:</strong> Automated systems flag suspicious patterns for manual review.</li>
                <li><strong>Consent Required:</strong> Students must consent before any proctoring features are enabled.</li>
                <li><strong>Data Retention:</strong> Proctoring data is retained only as long as necessary and deleted after specified periods.</li>
              </ul>
              <p>
                Students are informed about active proctoring features before starting an assessment.
              </p>
            </section>

            <section className="privacy-section">
              <h2>8. Children's Privacy</h2>
              <p>
                SchoolDom does not knowingly collect personal information from children under 13 years of age. If we become aware that a child under 13 has provided us with personal information, we will take steps to delete such information and terminate the child's account.
              </p>
              <p>
                For users 13-18 years old, parental consent may be required as per applicable laws (FERPA, COPPA, etc.). Schools should ensure compliance with these regulations.
              </p>
            </section>

            <section className="privacy-section">
              <h2>9. Cookies and Tracking Technologies</h2>
              <p>
                We use cookies and similar tracking technologies to enhance your experience on SchoolDom:
              </p>
              <ul>
                <li><strong>Session Cookies:</strong> To maintain your login session and security.</li>
                <li><strong>Preference Cookies:</strong> To remember your theme selection and display preferences.</li>
                <li><strong>Analytics Cookies:</strong> To understand how users interact with the platform (non-identifying).</li>
              </ul>
              <p>
                You can control cookie preferences through your browser settings. Disabling cookies may affect platform functionality.
              </p>
            </section>

            <section className="privacy-section">
              <h2>10. Third-Party Links</h2>
              <p>
                The Service may contain links to external websites not operated by SchoolDom. This Privacy Policy does not apply to third-party websites, and we are not responsible for their privacy practices. We encourage you to review the privacy policies of any external sites before providing personal information.
              </p>
            </section>

            <section className="privacy-section">
              <h2>11. International Data Transfers</h2>
              <p>
                Your data may be processed in countries other than where you reside. These countries may have data protection laws different from your home country. When we transfer data internationally, we implement appropriate safeguards such as Standard Contractual Clauses (SCCs) to ensure adequate protection.
              </p>
            </section>

            <section className="privacy-section">
              <h2>12. Changes to This Privacy Policy</h2>
              <p>
                We may update this Privacy Policy from time to time to reflect changes in our practices or legal requirements. We will notify you of significant changes by email or by posting the updated policy on our website. Your continued use of the Service following the posting of revised Privacy Policy means that you accept and agree to the changes.
              </p>
            </section>

            <section className="privacy-section">
              <h2>13. Contact Us</h2>
              <p>
                If you have questions about this Privacy Policy or our privacy practices, please contact us at:
              </p>
              <ul>
                <li><strong>Email:</strong> <a href={SUPPORT_MAILTO}>{SUPPORT_EMAIL}</a></li>
                <li><strong>Mailing Address:</strong> SchoolDom Support, 123 Education Drive, Tech City, TC 12345</li>
                <li><strong>Data Protection Officer:</strong> <a href={SUPPORT_MAILTO}>{SUPPORT_EMAIL}</a></li>
              </ul>
              <p>
                We will respond to your inquiry within 14 business days.
              </p>
            </section>

            <section className="privacy-section">
              <h2>14. Your Consent</h2>
              <p>
                By using SchoolDom, you consent to our Privacy Policy and our collection, use, and sharing of personal information as described herein.
              </p>
            </section>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="privacy-footer">
        <div className="privacy-container">
          <div className="privacy-footer-content">
            <div className="privacy-footer-section">
              <h4>Help & Support</h4>
              <ul>
                <li><a href="/faq">FAQ</a></li>
                <li><a href="/privacy">Privacy Policy</a></li>
                <li><a href="#">Terms of Service</a></li>
              </ul>
            </div>
            <div className="privacy-footer-section">
              <h4>Resources</h4>
              <ul>
                <li><a href="/resource">Resource Center</a></li>
                <li><a href="#">Documentation</a></li>
                <li><a href="#">Tutorials</a></li>
              </ul>
            </div>
            <div className="privacy-footer-section">
              <h4>Company</h4>
              <ul>
                <li><a href="#">About</a></li>
                <li><a href="#">Contact</a></li>
                <li><a href="#">Blog</a></li>
              </ul>
            </div>
          </div>
          <div className="privacy-footer-bottom">
            <p>&copy; 2026 SchoolDom. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default PrivacyPolicyPage;
