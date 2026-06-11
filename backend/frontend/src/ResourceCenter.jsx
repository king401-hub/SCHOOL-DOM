import { useState } from "react";
import { SUPPORT_EMAIL, SUPPORT_MAILTO } from "./appConstants";

function Logo() {
  return (
    <svg className="logo" viewBox="0 0 40 40" aria-hidden="true">
      <path d="M8 20v12h8v-6h8v6h8V20L20 10 8 20Z" fill="currentColor" />
    </svg>
  );
}

function ResourceCenter({ onNavigate }) {
  const [theme, setTheme] = useState("light");
  const [selectedCategory, setSelectedCategory] = useState("all");

  const resources = [
    {
      id: 1,
      title: "Getting Started with SchoolDom",
      description: "A comprehensive guide to set up your account and begin using the platform.",
      category: "guide",
      icon: "🚀",
      duration: "5 min read",
      type: "Article"
    },
    {
      id: 2,
      title: "Creating Your First Assessment",
      description: "Learn how to create, customize, and deploy assessments to your students.",
      category: "tutorial",
      icon: "📝",
      duration: "12 min video",
      type: "Video"
    },
    {
      id: 3,
      title: "Understanding Analytics Dashboard",
      description: "Explore real-time student performance metrics and detailed analytics.",
      category: "guide",
      icon: "📊",
      duration: "8 min read",
      type: "Article"
    },
    {
      id: 4,
      title: "Proctoring Features Explained",
      description: "Understand how our advanced proctoring system ensures assessment integrity.",
      category: "tutorial",
      icon: "🔐",
      duration: "10 min video",
      type: "Video"
    },
    {
      id: 5,
      title: "Student Practice Resources",
      description: "Access curated study materials, practice tests, and learning resources.",
      category: "resource",
      icon: "📚",
      duration: "100+ materials",
      type: "Library"
    },
    {
      id: 6,
      title: "API Integration Guide",
      description: "Technical documentation for integrating SchoolDom with your systems.",
      category: "technical",
      icon: "⚙️",
      duration: "Developer docs",
      type: "Documentation"
    },
    {
      id: 7,
      title: "Best Practices for Remote Testing",
      description: "Strategies and guidelines for conducting remote assessments effectively.",
      category: "guide",
      icon: "💻",
      duration: "15 min read",
      type: "Article"
    },
    {
      id: 8,
      title: "Video Tutorials Playlist",
      description: "Complete video series covering all features and functionalities.",
      category: "tutorial",
      icon: "🎬",
      duration: "2+ hours",
      type: "Playlist"
    },
    {
      id: 9,
      title: "FAQ & Support",
      description: "Frequently asked questions and troubleshooting common issues.",
      category: "support",
      icon: "❓",
      duration: "Always available",
      type: "Support"
    },
    {
      id: 10,
      title: "Personal Quiz Question Folder",
      description: "A dedicated question folder used only when students generate personal quizzes.",
      category: "personal-quiz",
      icon: "🗂️",
      duration: "Personal quizzes only",
      type: "Question Folder"
    },
  ];

  const categories = [
    { id: "all", label: "All Resources", count: resources.length },
    { id: "guide", label: "Guides", count: resources.filter(r => r.category === "guide").length },
    { id: "tutorial", label: "Tutorials", count: resources.filter(r => r.category === "tutorial").length },
    { id: "resource", label: "Study Materials", count: resources.filter(r => r.category === "resource").length },
    { id: "personal-quiz", label: "Personal Quiz Folder", count: resources.filter(r => r.category === "personal-quiz").length },
    { id: "technical", label: "Technical", count: resources.filter(r => r.category === "technical").length },
    { id: "support", label: "Support", count: resources.filter(r => r.category === "support").length },
  ];

  const filteredResources = selectedCategory === "all" 
    ? resources 
    : resources.filter(r => r.category === selectedCategory);

  return (
    <div className={`resource-center ${theme === "light" ? "theme-light" : ""}`}>
      {/* Header */}
      <header className="rc-header">
        <div className="rc-header-content">
          <div className="rc-brand">
            <button 
              type="button"
              className="rc-back-button"
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

          <div className="rc-header-actions">
            <button
              type="button"
              className="rc-theme-button"
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

      {/* Hero Banner */}
      <section className="rc-hero">
        <div className="rc-hero-content">
          <h1 className="rc-hero-title">Resource Center</h1>
          <p className="rc-hero-subtitle">Everything you need to master SchoolDom</p>
          <p className="rc-hero-description">Access tutorials, guides, documentation, and support materials to help you succeed.</p>
        </div>
      </section>

      {/* Category Filter */}
      <section className="rc-categories">
        <div className="rc-container">
          <div className="rc-category-filter">
            {categories.map((cat) => (
              <button
                key={cat.id}
                type="button"
                className={`rc-category-btn ${selectedCategory === cat.id ? "active" : ""}`}
                onClick={() => setSelectedCategory(cat.id)}
              >
                <span className="rc-cat-label">{cat.label}</span>
                <span className="rc-cat-count">{cat.count}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Search Bar */}
      <section className="rc-search-section">
        <div className="rc-container">
          <div className="rc-search-box">
            <svg viewBox="0 0 24 24" className="rc-search-icon" aria-hidden="true">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <input
              type="text"
              placeholder="Search resources..."
              className="rc-search-input"
            />
          </div>
        </div>
      </section>

      {/* Resources Grid */}
      <section className="rc-resources">
        <div className="rc-container">
          {filteredResources.length === 0 ? (
            <div className="rc-empty-state">
              <p>No resources found in this category.</p>
            </div>
          ) : (
            <div className="rc-grid">
              {filteredResources.map((resource) => (
                <article key={resource.id} className="rc-resource-card">
                  <div className="rc-card-header">
                    <div className="rc-card-icon">{resource.icon}</div>
                    <span className="rc-card-type">{resource.type}</span>
                  </div>
                  
                  <h3 className="rc-card-title">{resource.title}</h3>
                  
                  <p className="rc-card-description">{resource.description}</p>
                  
                  <div className="rc-card-footer">
                    <span className="rc-card-duration">{resource.duration}</span>
                    <button type="button" className="rc-card-link">
                      Learn More →
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Support Section */}
      <section className="rc-support">
        <div className="rc-container">
          <div className="rc-support-content">
            <h2>Need Additional Help?</h2>
            <p>Can't find what you're looking for? Our support team is here to help at {SUPPORT_EMAIL}.</p>
            <div className="rc-support-actions">
              <a href={SUPPORT_MAILTO} className="rc-support-btn rc-support-btn-primary">
                Contact Support
              </a>
              <a href={SUPPORT_MAILTO} className="rc-support-btn rc-support-btn-secondary">
                Send Feedback
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="rc-footer">
        <div className="rc-container">
          <div className="rc-footer-content">
            <div className="rc-footer-section">
              <h4>SchoolDom</h4>
              <p>Transforming education through technology.</p>
            </div>
            <div className="rc-footer-section">
              <h4>Resources</h4>
              <ul>
                <li><a href="#guides">Guides</a></li>
                <li><a href="#tutorials">Tutorials</a></li>
                <li><a href="#documentation">Documentation</a></li>
              </ul>
            </div>
            <div className="rc-footer-section">
              <h4>Support</h4>
              <ul>
                <li><a href="#help">Help Center</a></li>
                <li><a href="/faq">FAQ</a></li>
                <li><a href="/privacy">Privacy Policy</a></li>
              </ul>
            </div>
          </div>
          <div className="rc-footer-bottom">
            <p>&copy; 2026 SchoolDom. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default ResourceCenter;
