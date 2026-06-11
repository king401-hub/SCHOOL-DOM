import { useState } from "react";
import { SUPPORT_EMAIL, SUPPORT_MAILTO } from "./appConstants";

function Logo() {
  return (
    <svg className="logo" viewBox="0 0 40 40" aria-hidden="true">
      <path d="M8 20v12h8v-6h8v6h8V20L20 10 8 20Z" fill="currentColor" />
    </svg>
  );
}

function FAQPage({ onNavigate }) {
  const [theme, setTheme] = useState("light");
  const [expandedId, setExpandedId] = useState(null);

  const faqs = [
    {
      id: 1,
      category: "Getting Started",
      question: "What is SchoolDom?",
      answer: "SchoolDom is a next-generation Computer-Based Testing (CBT) platform designed for educational institutions. It enables educators to create, deploy, and manage assessments while providing students with a seamless testing experience with advanced proctoring and real-time analytics."
    },
    {
      id: 2,
      category: "Getting Started",
      question: "How do I create an account?",
      answer: "You can create an account by clicking 'Sign Up' on the login page. Choose your role (Student, Teacher, or School Administrator), fill in your information, and select or create a school code. Once verified, you'll have full access to the platform."
    },
    {
      id: 3,
      category: "Getting Started",
      question: "What are the different user roles?",
      answer: "SchoolDom supports three main roles: Students (take assessments and view results), Teachers (create assessments and grade submissions), and School Administrators (manage the entire school, users, and system settings)."
    },
    {
      id: 4,
      category: "Assessments",
      question: "How do I create an assessment?",
      answer: "Teachers can create assessments through the dashboard. Click 'Create Assessment', add a title and description, set a due date, specify the class, and add questions. You can customize difficulty levels, time limits, and whether it's an offline or online exam."
    },
    {
      id: 5,
      category: "Assessments",
      question: "Can I create assessments with different question types?",
      answer: "Yes! SchoolDom supports multiple question types including multiple choice, short answer, essay questions, and true/false. You can also add explanations for each answer to help students learn from their mistakes."
    },
    {
      id: 6,
      category: "Assessments",
      question: "How do I assign assessments to students?",
      answer: "Once you create an assessment, select the class(es) you want to assign it to. You can set specific due dates, time limits, and whether students can retry. You can also assign to individual students if needed."
    },
    {
      id: 7,
      category: "Proctoring & Integrity",
      question: "What proctoring features does SchoolDom offer?",
      answer: "SchoolDom includes advanced proctoring features such as webcam monitoring, screen recording, keyboard activity tracking, face detection, and AI-powered anomaly detection to ensure assessment integrity. These can be toggled based on institutional requirements."
    },
    {
      id: 8,
      category: "Proctoring & Integrity",
      question: "How does the integrity system work?",
      answer: "Our integrity system uses AI and machine learning to detect suspicious behavior such as unusual answer patterns, rapid responses, or multiple-choice clustering. It flags potential issues for manual review without making automatic decisions."
    },
    {
      id: 9,
      category: "Proctoring & Integrity",
      question: "Can students take offline exams?",
      answer: "Yes! SchoolDom supports offline assessments. Students can start exams while online, and if connectivity is lost, they can continue working. Their answers are synced once reconnected. This is particularly useful in areas with unstable internet."
    },
    {
      id: 10,
      category: "Grading & Analytics",
      question: "How do I grade student submissions?",
      answer: "Automatic grading is applied to objective questions instantly. For subjective questions, teachers receive a list of pending submissions and can grade them manually, add comments, and provide feedback directly to students."
    },
    {
      id: 11,
      category: "Grading & Analytics",
      question: "What analytics are available?",
      answer: "Teachers can access detailed analytics including class performance averages, individual student progress, question difficulty analysis, time-on-task metrics, and learning gap identification. Administrators get school-wide analytics and institutional reports."
    },
    {
      id: 12,
      category: "Grading & Analytics",
      question: "Can I export reports?",
      answer: "Yes! You can export student performance reports, class analytics, and institutional reports in multiple formats (PDF, Excel, CSV). This helps with record-keeping and data analysis."
    },
    {
      id: 13,
      category: "Student Features",
      question: "Can students see their results immediately?",
      answer: "Students can view their results after the teacher submits the result and the admin publishes it. Until then, the result stays hidden from the student portal."
    },
    {
      id: 14,
      category: "Student Features",
      question: "Can students practice with sample questions?",
      answer: "Absolutely! Students have access to a comprehensive resource library with practice materials, sample questions, tutorials, and study guides. Teachers can also assign specific practice sets to their classes."
    },
    {
      id: 15,
      category: "Student Features",
      question: "How can I track my academic progress?",
      answer: "Students can view their performance dashboard which shows all their assessments, scores, progress over time, areas for improvement, and personalized learning recommendations based on their performance."
    },
    {
      id: 16,
      category: "School Management",
      question: "How do administrators manage users?",
      answer: "School administrators can add/remove teachers and students, manage classes, set system-wide policies, configure proctoring settings, and view comprehensive institutional analytics."
    },
    {
      id: 17,
      category: "School Management",
      question: "Can multiple schools use the same platform?",
      answer: "Yes! SchoolDom is multi-tenant, meaning multiple schools can use the platform independently with completely separated data. Each school has its own administrator panel and user management system."
    },
    {
      id: 18,
      category: "School Management",
      question: "How is student data protected?",
      answer: "SchoolDom uses end-to-end encryption, secure authentication, regular security audits, and complies with GDPR and data protection regulations. All data is stored on secure servers with automatic backups."
    },
    {
      id: 19,
      category: "Technical Support",
      question: "What if I experience technical issues during an exam?",
      answer: "Our system has failsafe mechanisms. If connection is lost, you can reconnect and continue. If the issue persists, contact our support team immediately. We can provide technical evidence and extend deadlines if necessary."
    },
    {
      id: 20,
      category: "Technical Support",
      question: "Which browsers are supported?",
      answer: "SchoolDom works on Chrome, Firefox, Safari, and Edge browsers. We recommend updating to the latest version for the best experience. Mobile browsers are also supported for taking quizzes."
    },
    {
      id: 21,
      category: "Technical Support",
      question: "Can I use SchoolDom on mobile devices?",
      answer: "Yes! SchoolDom is fully responsive and works on smartphones and tablets. The experience is optimized for smaller screens, and all features are accessible on mobile devices."
    },
    {
      id: 22,
      category: "Fees & Billing",
      question: "What's the pricing model?",
      answer: "SchoolDom uses one simple token-based pricing model. K-12 student activation tokens cost N500 and last 3 months 15 days. Non K-12 activation tokens cost N200 and last 1 month. Transcript, testimonial, and ID card generation each cost 1 token."
    },
    {
      id: 23,
      category: "Fees & Billing",
      question: "Is there a free trial?",
      answer: "We offer a new-user bonus, and schools receive 10 free tokens for every 100 tokens purchased."
    },
    {
      id: 24,
      category: "Integration",
      question: "Can I integrate SchoolDom with other systems?",
      answer: "Yes! SchoolDom has APIs and supports integration with Learning Management Systems (LMS), Student Information Systems (SIS), and other educational tools. Check our API documentation or contact support for integration assistance."
    },
    {
      id: 25,
      category: "Integration",
      question: "Can I import questions from other platforms?",
      answer: "Yes! You can import questions in standard formats (CSV, QTI). We also provide templates to help you format your questions correctly. Our support team can assist with bulk imports."
    },
  ];

  const toggleExpand = (id) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const categories = [...new Set(faqs.map(faq => faq.category))];

  return (
    <div className={`faq-page ${theme === "light" ? "theme-light" : ""}`}>
      {/* Header */}
      <header className="faq-header">
        <div className="faq-header-content">
          <div className="faq-brand">
            <button 
              type="button"
              className="faq-back-button"
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

          <div className="faq-header-actions">
            <button
              type="button"
              className="faq-theme-button"
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
      <section className="faq-hero">
        <div className="faq-hero-content">
          <h1 className="faq-hero-title">Frequently Asked Questions</h1>
          <p className="faq-hero-subtitle">Find answers to common questions about SchoolDom</p>
        </div>
      </section>

      {/* FAQ Content */}
      <section className="faq-content">
        <div className="faq-container">
          {categories.map((category, catIndex) => (
            <div key={catIndex} className="faq-category-section">
              <h2 className="faq-category-title">{category}</h2>
              <div className="faq-items">
                {faqs.filter(faq => faq.category === category).map((faq) => (
                  <div key={faq.id} className="faq-item">
                    <button
                      type="button"
                      className="faq-question"
                      onClick={() => toggleExpand(faq.id)}
                      aria-expanded={expandedId === faq.id}
                    >
                      <span className="faq-question-text">{faq.question}</span>
                      <span className="faq-toggle-icon">
                        {expandedId === faq.id ? '−' : '+'}
                      </span>
                    </button>
                    {expandedId === faq.id && (
                      <div className="faq-answer">
                        <p>{faq.answer}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Help Section */}
      <section className="faq-help">
        <div className="faq-container">
          <h2>Didn't find your answer?</h2>
          <p>Our support team is here to help. Contact us at {SUPPORT_EMAIL} for personalized assistance.</p>
          <a href={SUPPORT_MAILTO} className="faq-contact-btn">
            Contact Support
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="faq-footer">
        <div className="faq-container">
          <div className="faq-footer-content">
            <div className="faq-footer-section">
              <h4>Help & Support</h4>
              <ul>
                <li><a href="#faq">FAQ</a></li>
                <li><a href="/privacy">Privacy Policy</a></li>
                <li><a href="#">Terms of Service</a></li>
              </ul>
            </div>
            <div className="faq-footer-section">
              <h4>Resources</h4>
              <ul>
                <li><a href="/resource">Resource Center</a></li>
                <li><a href="#">Documentation</a></li>
                <li><a href="#">Tutorials</a></li>
              </ul>
            </div>
            <div className="faq-footer-section">
              <h4>Company</h4>
              <ul>
                <li><a href="#">About</a></li>
                <li><a href="#">Contact</a></li>
                <li><a href="#">Blog</a></li>
              </ul>
            </div>
          </div>
          <div className="faq-footer-bottom">
            <p>&copy; 2026 SchoolDom. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default FAQPage;
