import React from "react";

export default function PrivacyPolicyPage({ onNavigate }) {
  const goBack = () => {
    if (typeof onNavigate === "function") {
      onNavigate("/");
      return;
    }
    window.location.href = "/";
  };

  return (
    <div className="privacy-page">
      <header style={{ padding: "16px 24px", borderBottom: "1px solid #e5e7eb" }}>
        <button type="button" onClick={goBack} style={{ marginRight: 12 }}>
          ← Back
        </button>
        <strong>SchoolDom</strong>
        <span style={{ marginLeft: 8, color: "#6b7280" }}>Privacy Policy</span>
      </header>

      <main style={{ padding: "24px" }}>
        <h1 style={{ margin: "0 0 8px" }}>Privacy Policy</h1>
        <p style={{ margin: "0 0 16px", color: "#6b7280" }}>Last updated: May 1, 2026</p>

        <div style={{ maxWidth: 900, lineHeight: 1.6, color: "#111827" }}>
          <p>
            This Privacy Policy describes how SchoolDom collects, uses, and protects personal data when
            you use the SchoolDom platform.
          </p>
          <p>
            For the full legal text, refer to your school onboarding documents or contact
            <a href="mailto:enquiry@schooldom.academy">enquiry@schooldom.academy</a>.
          </p>

          <section style={{ marginTop: 16 }}>
            <h2 style={{ fontSize: 16, margin: "0 0 8px" }}>Key points</h2>
            <ul style={{ paddingLeft: 18 }}>
              <li>We process data to provide the platform and its services.</li>
              <li>School administrators act as data controllers for their school’s data.</li>
              <li>We use appropriate safeguards to protect personal information.</li>
            </ul>
          </section>
        </div>
      </main>
    </div>
  );
}

