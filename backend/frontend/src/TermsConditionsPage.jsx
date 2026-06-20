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
            <button type="button" className="privacy-back-button" onClick={onOpenOnboarding} aria-label={fromSignup ? "Back to signup" : "Back to home"}>
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
          <h1 className="privacy-hero-title">Terms &amp; Conditions</h1>
          <p className="privacy-hero-subtitle">Effective Date: 2026</p>
        </div>
      </section>

      <section className="privacy-content">
        <div className="privacy-container">
          <div className="privacy-document">
            <section className="privacy-section">
              <h2>Introduction &amp; Agreement</h2>
              <p>
                These Terms &amp; Conditions ("Terms") govern your access to and use of the SchoolDom platform ("Platform"), including the website, web application, and mobile applications for school administrators, teachers, students, and parents (collectively, "Applications"). SchoolDom is provided by Xcel Technologies Ltd ("Xcel Technologies", "we", "us", or "our"). By creating an account or using the Platform, you confirm that you have read, understood, and agree to these Terms. If you do not agree, do not use the Platform.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Definitions</h2>
              <p>
                <strong>Platform:</strong> SchoolDom website, web app, and mobile apps.
              </p>
              <p>
                <strong>User:</strong> Any individual or entity authorized to use the Platform. Includes School Owner, School Administrator, Teacher, Parent/Guardian, and Student.
              </p>
              <p>
                <strong>Content:</strong> All data, files, results, documents, images, and information uploaded or stored on the Platform by Users.
              </p>
              <p>
                <strong>Account:</strong> The credentials and profile created for each User.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Accounts &amp; Eligibility</h2>
              <p>
                <strong>3.1 Eligibility</strong>
              </p>
              <ul>
                <li>School Owners must be legal representatives of the school with authority to contract.</li>
                <li>School Administrators, Teachers, and Parents must be 18+ years old.</li>
                <li>Students may use the Platform only under supervision of Teachers/Parents and with consent from the School Owner.</li>
              </ul>
              <p>
                <strong>3.2 Account Creation &amp; Security</strong>
              </p>
              <p>
                School Owners subscribe and create the main school account. School Administrators create accounts for Teachers, Parents, and Students. You must provide accurate, current information and keep it updated. You are responsible for all activities under your account. Keep passwords confidential. Notify us immediately at <a href="mailto:enquiry@schooldom.academy">enquiry@schooldom.academy</a> if you suspect unauthorized access. Xcel Technologies is not liable for losses due to your failure to protect account details.
              </p>
              <p>
                <strong>3.3 Acceptable Use</strong>
              </p>
              <p>
                You agree to use SchoolDom only for lawful school management purposes. You must not:
              </p>
              <ul>
                <li>Violate any Nigerian law, NDPR, or these Terms.</li>
                <li>Impersonate any person, school, or falsely claim affiliation.</li>
                <li>Upload malware, viruses, or disrupt servers/networks.</li>
                <li>Attempt unauthorized access, hacking, or data scraping.</li>
                <li>Use bots, spiders, or automated tools without written permission.</li>
                <li>Upload content that is defamatory, obscene, infringing, or harmful to minors.</li>
              </ul>
              <p>
                We may suspend or terminate accounts that violate this section.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Content &amp; Data Ownership</h2>
              <p>
                <strong>4.1 User Responsibility</strong>
              </p>
              <p>
                You own the Content you upload. You are solely responsible for it. You warrant that you have all rights and consents needed, especially for student/parent data.
              </p>
              <p>
                <strong>4.2 License to Xcel Technologies</strong>
              </p>
              <p>
                You grant Xcel Technologies a non-exclusive, worldwide, royalty-free license to host, process, display, and backup your Content solely to provide, maintain, and improve SchoolDom. We do not claim ownership of your data.
              </p>
              <p>
                <strong>4.3 School Data Controller</strong>
              </p>
              <p>
                For NDPR/GDPR purposes, the School Owner is the "Data Controller" for student/parent data. Xcel Technologies is the "Data Processor". We process data only on your instructions. See our Privacy Policy for details.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Intellectual Property</h2>
              <p>
                SchoolDom, including all code, design, logos, trademarks, and features, is owned by Xcel Technologies Ltd. All rights reserved. We grant you a limited, non-exclusive, non-transferable license to use the Platform for your school’s internal purposes only. You may not copy, modify, reverse engineer, resell, or create derivative works without written consent.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Fees, Payment &amp; Refunds</h2>
              <p>
                <strong>6.1 Subscription</strong>
              </p>
              <p>
                School Owners pay subscription fees based on the plan chosen. Fees are billed annually/termly in advance. Current pricing is shown on http://schooldom.academy/pricing.
              </p>
              <p>
                <strong>6.2 Payment Gateway Fees</strong>
              </p>
              <p>
                Parents paying school fees through SchoolDom pay gateway/transaction charges set by our payment partners. Xcel Technologies does not receive these charges.
              </p>
              <p>
                <strong>6.3 Free Trial &amp; Refunds</strong>
              </p>
              <p>
                We offer a free trial for new schools. After trial ends, all subscription fees are non-refundable. No refunds for partial months or unused features. Exception: If we fail to provide core services for 7+ consecutive days due to our fault, you may request a pro-rata refund.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Service Availability &amp; Support</h2>
              <p>
                We aim for 99.5% monthly uptime, excluding scheduled maintenance. We’ll notify School Administrators 48 hours before planned maintenance.
              </p>
              <p>
                Support is provided via email at <a href="mailto:enquiry@schooldom.academy">enquiry@schooldom.academy</a> during business hours, 9am-5pm WAT, Mon-Fri. Response time for critical issues: 4 business hours.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Suspension &amp; Termination</h2>
              <p>
                <strong>8.1 By You</strong>: School Owners may terminate by emailing <a href="mailto:enquiry@schooldom.academy">enquiry@schooldom.academy</a>. Access ends at the end of the paid period.
              </p>
              <p>
                <strong>8.2 By Us</strong>: We may suspend or terminate accounts for breach of Terms, non-payment, fraud, or illegal use. We’ll give notice where possible. On termination, you have 30 days to export your data. After 30 days, we may delete Content as per our Privacy Policy. Clauses on IP, liability, and payment survive termination.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Limitation of Liability</h2>
              <p>
                To the maximum extent allowed by Nigerian law: Xcel Technologies is not liable for indirect, incidental, special, or consequential damages, including loss of profits, data, or goodwill. Our total liability for any claim is limited to the amount you paid us in the 12 months before the claim. School Owners are liable for data they upload and for actions of their Users.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Disclaimer of Warranties</h2>
              <p>
                SchoolDom is provided “AS IS” and “AS AVAILABLE”. We do not guarantee the Platform will be error-free, uninterrupted, or meet all your requirements. We are not responsible for internet outages or third-party service failures.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Changes to Terms</h2>
              <p>
                We may update these Terms to reflect new features or legal changes. We’ll post the updated version with a new “Effective Date” and notify School Administrators by email for material changes. Continued use after changes means acceptance.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Governing Law &amp; Disputes</h2>
              <p>
                These Terms are governed by the laws of the Federal Republic of Nigeria. Any dispute will first attempt amicable resolution for 30 days. If unresolved, disputes will be settled by arbitration in Lagos under the Arbitration and Conciliation Act.
              </p>
            </section>

            <section className="privacy-section">
              <h2>Contact Us</h2>
              <p>
                Questions about these Terms? Contact: Xcel Technologies Ltd<br />
                Email: <a href="mailto:enquiry@schooldom.academy">enquiry@schooldom.academy</a><br />
                Address: 256 Ikotun road, Lagos.
              </p>
              <p>
                These Terms incorporate our Privacy Policy by reference.
              </p>
            </section>
          </div>
        </div>
      </section>
    </div>
  );
}

export default TermsConditionsPage;
