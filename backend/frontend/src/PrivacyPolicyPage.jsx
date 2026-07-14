import { useState } from "react";

function Logo() {
  return (
    <svg className="logo" viewBox="0 0 40 40" aria-hidden="true">
      <path d="M8 20v12h8v-6h8v6h8V20L20 10 8 20Z" fill="currentColor" />
    </svg>
  );
}

function PrivacyPolicyPage({ onNavigate }) {
  const [theme, setTheme] = useState("light");
  const fromSignup = new URLSearchParams(window.location.search).get("from") === "signup";

  const goBack = () => {
    if (fromSignup) {
      window.location.href = "/signin?mode=signup";
      return;
    }
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
            <button type="button" className="privacy-back-button" onClick={goBack} aria-label={fromSignup ? "Back to signup" : "Back to home"}>
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
          <h1 className="privacy-hero-title">Privacy Policy</h1>
          <p className="privacy-hero-subtitle">Last Updated: July 2026</p>
        </div>
      </section>

      <section className="privacy-content">
        <div className="privacy-container">
          <div className="privacy-document">
            <section className="privacy-section">
              <p>
                This Privacy Policy ("Policy") explains how we collect, use, disclose, and protect information in connection with the SchoolDom platform ("Platform"), including the website, web application, and mobile applications for school administrators, teachers, students, and parents (collectively, "Applications").
              </p>
              <p>By accessing or using the Platform, you agree to this Policy.</p>
            </section>

            <section className="privacy-section">
              <h2>Who We Are &amp; Contact</h2>
              <p>
                <strong>Data Controller:</strong> Xcel Technologies Ltd
                <br />
                <strong>Address:</strong> 256, Ikotun road, Lagos.
                <br />
                <strong>Data Protection Officer/Contact:</strong> <a href="mailto:enquiry@schooldom.academy">enquiry@schooldom.academy</a>
              </p>
              <p>
                For any privacy questions, requests, or complaints, contact us at <a href="mailto:enquiry@schooldom.academy">enquiry@schooldom.academy</a>.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Information We Collect</h2>
              <p>
                We collect only data necessary to provide SchoolDom services. Data is provided by School Owners/Administrators, Users, or collected automatically:
              </p>
              <ul>
                <li>
                  <strong>School Information:</strong> School name, address, RC number, contact details, and subscription details provided by the School Owner during onboarding.
                </li>
                <li>
                  <strong>User Account Information:</strong> Name, email address, phone number, role, password, and profile details provided during account creation or by the School Administrator.
                </li>
                <li>
                  <strong>Student Information:</strong> Name, admission ID, date of birth, grade/class, gender, parent/guardian details, academic performance data, attendance records, and disciplinary reports. This is provided by the School Administrator and processed on their behalf.
                </li>
                <li>
                  <strong>Usage &amp; Device Data:</strong> IP address, device type, browser/OS, log data, pages viewed, features used, and access times. Collected automatically to improve performance and security.
                </li>
                <li>
                  <strong>Communications:</strong> Messages, support tickets, and feedback you send us.
                </li>
                <li>
                  <strong>Cookies &amp; Similar Tech:</strong> We use cookies for authentication, preferences, and analytics. See the Cookies &amp; Tracking section below.
                </li>
              </ul>
            </section>

            <section className="privacy-section">
              <h2>Lawful Basis &amp; How We Use Your Information</h2>
              <p>Under GDPR/NDPR, we process data based on: contract, legitimate interest, consent, and legal obligation.</p>
              <p>We use your information to:</p>
              <ul>
                <li><strong>Provide the Platform:</strong> Create accounts, enable features like CBT, fees, attendance, and reporting.</li>
                <li><strong>Communicate:</strong> Send account updates, security alerts, and platform announcements. Marketing only with consent.</li>
                <li><strong>Personalize Experience:</strong> Show relevant dashboards, content, and recommendations based on role and activity.</li>
                <li><strong>Support Schools:</strong> Generate reports, enable parent-teacher communication, and fulfill requests from School Administrators.</li>
                <li><strong>Improve &amp; Secure:</strong> Analyze usage, fix bugs, prevent fraud, and develop new features.</li>
                <li><strong>Comply with Law:</strong> Respond to legal requests and meet NDPR/GDPR obligations.</li>
              </ul>
              <p>
                School Administrators are the "Data Controllers" for student/parent data. Xcel Technologies acts as "Data Processor" for that data.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Sharing &amp; Disclosure</h2>
              <p>We do not sell personal data. We share data only as follows:</p>
              <ul>
                <li><strong>School Administrators:</strong> School Owners/Admins can access User and Student data for their school only, as authorized by them.</li>
                <li><strong>Service Providers:</strong> Trusted third parties who host data, send emails/SMS, process payments, or provide analytics. All are bound by Data Processing Agreements to protect data and only use it for our purposes.</li>
                <li><strong>Legal Compliance:</strong> If required by Nigerian law, court order, or regulatory authority.</li>
                <li><strong>Business Transfer:</strong> If Xcel Technologies is merged or acquired, data may transfer subject to this Policy.</li>
              </ul>
            </section>

            <section className="privacy-section">
              <h2>Data Retention</h2>
              <p>We keep data only as long as needed for the purposes above, or as required by law.</p>
              <ul>
                <li>School account data: Retained while account is active + 2 years after closure for legal/audit needs.</li>
                <li>Student academic records: Retained per instructions from the School Administrator, in line with school policy and education laws.</li>
                <li>Logs &amp; analytics: Retained for 12 months, then anonymized.</li>
              </ul>
              <p>You can request deletion anytime. We will delete or anonymize data unless law requires retention.</p>
            </section>

            <section className="privacy-section">
              <h2>Your Rights &amp; Choices</h2>
              <p>Under NDPR and GDPR, you have the right to:</p>
              <ul>
                <li><strong>Access:</strong> Request a copy of your personal data.</li>
                <li><strong>Correction:</strong> Ask us to correct inaccurate or incomplete data.</li>
                <li><strong>Deletion:</strong> Ask us to delete your data, subject to legal exceptions.</li>
                <li><strong>Object/Restrict:</strong> Object to processing or request limits on how we use data.</li>
                <li><strong>Portability:</strong> Receive your data in a structured, machine-readable format.</li>
                <li><strong>Withdraw Consent:</strong> Where we rely on consent, you can withdraw it anytime.</li>
              </ul>
              <p>
                To exercise rights, email <a href="mailto:enquiry@schooldom.academy">enquiry@schooldom.academy</a>. We will respond within 30 days as required by NDPR.
              </p>
              <p>School Administrators should contact their school to access or delete student data, since schools control that data.</p>
            </section>

            <section className="privacy-section">
              <h2>Security</h2>
              <p>
                We use encryption, access controls, firewalls, and regular audits to protect data. All data is stored on servers with SOC 2 compliant providers.
              </p>
              <p>No system is 100% secure. You're also responsible for keeping your password safe and not sharing login details.</p>
            </section>

            <section className="privacy-section">
              <h2>Children's Privacy</h2>
              <p>
                SchoolDom is designed for schools and will process personal data of children under 13 as provided by Schools. We process this data only on instruction from the School, which acts as Data Controller. Schools must ensure they have parental consent as required by law. We do not knowingly collect data directly from children.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Cookies &amp; Tracking</h2>
              <p>
                We use essential cookies for login/security and optional cookies for analytics/performance. You can manage cookie preferences in your browser. Blocking essential cookies may break login.
              </p>
            </section>

            <section className="privacy-section">
              <h2>International Data Transfers</h2>
              <p>
                If data is transferred outside Nigeria/EU, we ensure adequate protection via Standard Contractual Clauses or other NDPR/GDPR-approved mechanisms.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Changes to This Policy</h2>
              <p>
                We may update this Policy to reflect changes in law or features. We'll post the new version here with a "Last Updated" date and notify School Administrators by email for material changes. Continued use means acceptance.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Complaints</h2>
              <p>
                If you're unsatisfied with our response, you can lodge a complaint with the Nigeria Data Protection Commission at{" "}
                <a href="http://ndpc.gov.ng" target="_blank" rel="noreferrer">ndpc.gov.ng</a> or your local EU data authority.
              </p>
            </section>
          </div>
        </div>
      </section>
    </div>
  );
}

export default PrivacyPolicyPage;
