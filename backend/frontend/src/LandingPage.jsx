import { useState, useEffect } from "react";

// ============================================
// CONSTANTS & DATA
// ============================================

const SUPPORT_EMAIL = "support@schooldom.com";
const SUPPORT_MAILTO = "mailto:support@schooldom.com";

const PHRASES = [
  { text: 'Elevate Education.', font: 'serif', color: '#6C4DF6' },
  { text: 'Empower Teachers.', font: 'mono', color: '#ec4899' },
  { text: 'Scale Operations.', font: 'serif', color: '#10b981' },
  { text: 'Unify School Data.', font: 'sans', color: '#6366f1' },
  { text: 'Secure Portfolios.', font: 'mono', color: '#f59e0b' },
];

const FEATURE_LIST = [
  {
    id: 'sis',
    title: 'Student Information System',
    category: 'admin',
    description: 'The core engine holding deep biological data, sibling directories, parent links, medical emergency records, and full cumulative performance cards.',
    benefit: 'Saves 240+ hours of paper record indexing annually.',
    icon: '👥',
    color: '#6C4DF6',
    bulletPoints: ['Secure Cloud Vault Storage', 'Comprehensive Family Linkage Maps', 'Instant Bio data export']
  },
  {
    id: 'attendance',
    title: 'RFID Attendance Tracking',
    category: 'admin',
    description: 'Advanced real-time sync with RFID gate sensors or physical QR-code badges. When the pupil scans in, parents are instantly pacified with push alerts.',
    benefit: 'Reduces student unexcused absconding by 92%.',
    icon: '📅',
    color: '#10b981',
    bulletPoints: ['IoT Hardware Gateway Sync', 'Absorbs zero manual rollcall time', 'Parental SMS Auto Triggering']
  },
  {
    id: 'results',
    title: 'Online Result Management',
    category: 'academic',
    description: 'Dynamic reporting sheets calculation. Automatic class averaging, standard deviations, GPA allocations, and customized report cards generation.',
    benefit: 'Generates 5,000 progress sheets in 4.5 seconds.',
    icon: '📄',
    color: '#8b5cf6',
    bulletPoints: ['Formulaic Custom Grading Scales', 'Cumulative Weighted Averaging', 'Parental Signature Tracking']
  },
  {
    id: 'school-fees',
    title: 'School Fees Collection',
    category: 'finance',
    description: 'Say goodbye to physical cash. Streamlined automated family ledger showing full active invoicing, instalment structures, and direct digital card channels.',
    benefit: 'Reconciles 100% of school outstanding bills.',
    icon: '🏦',
    color: '#a78bfa',
    bulletPoints: ['Direct Ledger Invoicing', 'Instalment Payment Monitors', 'Secured Card Gateways']
  },
  {
    id: 'virtual-accounts',
    title: 'Virtual Student Accounts',
    category: 'finance',
    description: 'Unique automated financial clearing proxies. Dynamic digital bank accounts assigned to parents. Any deposit clears specific fees instantly.',
    benefit: 'Eliminates bank deposit slips verification.',
    icon: '💳',
    color: '#6366f1',
    bulletPoints: ['Escrow Ledger Sync', 'Individual Parent IBAN proxy', 'Immediate Deposit Notification']
  },
  {
    id: 'parent-portal',
    title: 'Bespoke Parent Portal',
    category: 'academic',
    description: 'A custom, clean mobile dashboard for guardians. View fee accounts, resultsheets, homework lists, live school calendars, and directly text instructors.',
    benefit: '98% parental engagement index.',
    icon: '🏠',
    color: '#ec4899',
    bulletPoints: ['Instant messaging interface', 'Fee invoices tracker', 'Report card downloads']
  },
  {
    id: 'teacher-portal',
    title: 'Premium Teacher Portal',
    category: 'academic',
    description: 'Lightweight lesson planning workspace. Assign grades, coordinate classes, record notes and directly publish syllabus materials inside the LMS.',
    benefit: 'Increases classroom teaching efficacy by 30%.',
    icon: '📋',
    color: '#8b5cf6',
    bulletPoints: ['Dynamic Lesson Planners', 'Fast gradebook inputs', 'Collaborative Syllabus tools']
  },
  {
    id: 'notifications',
    title: 'SMS & Email Announcements',
    category: 'admin',
    description: 'Mass automated alert hub. Alert parents during unexpected weather event emergencies, PTA activities, or outstanding fee reminders.',
    benefit: 'Deliver messages to 10,000+ parents under 3 seconds.',
    icon: '💬',
    color: '#6C4DF6',
    bulletPoints: ['Emergency Weather broadcasts', 'PTA Reminder campaigns', 'Variable merge tag logs']
  },
  {
    id: 'lms',
    title: 'Learning Management System',
    category: 'academic',
    description: 'Comprehensive virtual classrooms hub. High-density video uploads, PDF textbook uploads, diagnostic assessments, and randomized quizzes.',
    benefit: 'Assures education continuity 24/7.',
    icon: '📚',
    color: '#06b6d4',
    bulletPoints: ['Homework assignment vaults', 'Dynamic slide libraries', 'Online exams with timers']
  },
  {
    id: 'accounting-finance',
    title: 'Full School Accounting Suite',
    category: 'finance',
    description: 'Reconcile payroll, coordinate teachers bonuses, track expenditures, compile trial balances, and export audited tax charts for directors.',
    benefit: 'Agrades full compliance audit reviews.',
    icon: '📈',
    color: '#10b981',
    bulletPoints: ['Trial Balances & General Ledger', 'Academic Payroll & Bonuses', 'Expenditure Tax Exports']
  }
];

const TESTIMONIALS_LIST = [
  {
    id: 't1',
    quote: 'Transitioning our entire ledger to SchoolDom virtual student accounts completely cleared all outstanding bills. Invoices auto-notify sponsors, and escrow releases correspond instantly without ledger errors. This tool paid for itself in 10 days.',
    author: 'Dr. Mary-Anne Sterling',
    role: 'Principal & Proprietor',
    schoolName: 'Sterling Academy Group (K-12)',
    metric: '99.4% Tuition Collection Rate',
    avatar: ''
  },
  {
    id: 't2',
    quote: 'Our teachers used to waste up to an hour daily on roll call registry & Excel report card templates. Now, RFID gate bands log students instantly, and report card GPAs calculate automatically. Teachers are strictly focused on coaching core curricula.',
    author: 'Prof. Marcus Alao',
    role: 'Registrar & Chancellor',
    schoolName: 'Heritage Science Collegiate',
    metric: '420 Hours Saved/Semester',
    avatar: ''
  },
  {
    id: 't3',
    quote: 'The Parent portal holds amazing cohesion. No more tedious paper alerts or parent-teacher friction. Parents view account lists, attendance reports, homework cards, and GPA stats of pupils. It completely built trust with our community.',
    author: 'Mrs. Catherine Osei-Tutu',
    role: 'Chief Academic Officer',
    schoolName: 'Lighthouse International Academy',
    metric: '98% Positive Parent Reviews',
    avatar: ''
  }
];

const FAQ_ITEMS = [
  {
    id: 'faq-1',
    question: 'What represents SchoolDom Tokens, and how does active token billing operate?',
    answer: 'SchoolDom uses a flexible token model. Instead of paying rigid annual user license fees, schools select specified modules (e.g. smart attendance or fees collections) and load tokens based on active enrollment size. Custom sliders like student count and teacher counts calculate your exact monthly or quarterly token depletion rate. This allows K-12 and collegiate schools under expansion to adjust services anytime with zero contractual penalties.'
  },
  {
    id: 'faq-2',
    question: 'Can we transition our historical student spreadsheets without losing reports?',
    answer: 'Absolutely. SchoolDom features an automated onboarding migrator engine. You can upload any existing Student bio CSV, parent contact lists, or academic grading history files. Our automated format parser processes your spreadsheets and hooks student records securely under 10 minutes. Our database support team also provides hands-on diagnostic transfers for customized historical data.'
  },
  {
    id: 'faq-3',
    question: 'How do Parent virtual bank accounts and fee escrow clearing operate?',
    answer: 'Every family/student portfolio inside SchoolDom is allocated a custom digital clearing proxy IBAN or bank clearing channel. Parents receive direct invoices on their customized application dashboard. Any deposit made into their allocated proxy bank account automatically resolves their school ledger balances instantly, generating a secure digital receipt. Outstanding fees are reduced instantly, avoiding manual ledger validation.'
  },
  {
    id: 'faq-4',
    question: 'Is SchoolDom compliant with Student Privacy Protection acts (like COPPA/FERPA / Data Security)?',
    answer: 'Data security is our paramount blueprint. All school records, biological files, and resultsheets are encrypted in transit via TLS 1.3 and at rest using AES-256 secure standards. In addition, the platforms database triggers strict FERPA & COPPA privacy policies, restricting unauthorized teacher/staff credentials from accessing sensitive client folders without administrative proxy permission locks.'
  },
  {
    id: 'faq-5',
    question: 'Do you offer custom training or onboarding support for non-technical teachers?',
    answer: 'We provide comprehensive training tools to guarantee full compliance and zero friction. SchoolDom comes integrated with localized virtual video simulations and text guides. Furthermore, every registered institution is assigned a dedicated Customer Success Architect to direct live training seminars over Zoom/Google Meet. We also maintain a fast-rebuttal 24/7 web chat desk.'
  }
];

// ============================================
// TYPING ANIMATOR COMPONENT
// ============================================

function TypingAnimator() {
  const [currentPhraseIdx, setCurrentPhraseIdx] = useState(0);
  const [displayedText, setDisplayedText] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [speed, setSpeed] = useState(100);

  const currentPhrase = PHRASES[currentPhraseIdx];

  useEffect(() => {
    let timer;

    const handleTyping = () => {
      const fullText = currentPhrase.text;
      
      if (!isDeleting) {
        setDisplayedText(fullText.slice(0, displayedText.length + 1));
        setSpeed(80 + Math.random() * 40);

        if (displayedText === fullText) {
          setSpeed(2000);
          setIsDeleting(true);
        }
      } else {
        setDisplayedText(fullText.slice(0, displayedText.length - 1));
        setSpeed(40);

        if (displayedText === '') {
          setIsDeleting(false);
          setCurrentPhraseIdx((prev) => (prev + 1) % PHRASES.length);
          setSpeed(500);
        }
      }
    };

    timer = setTimeout(handleTyping, speed);
    return () => clearTimeout(timer);
  }, [displayedText, isDeleting, speed, currentPhraseIdx, currentPhrase.text]);

  return (
    <span className={`typing-text ${currentPhrase.font}`} style={{ color: currentPhrase.color }}>
      {displayedText}
      <span className="cursor-blink">|</span>
    </span>
  );
}

// ============================================
// LOGO COMPONENT
// ============================================

function Logo() {
  return (
    <svg className="logo-svg" viewBox="0 0 40 40" aria-hidden="true">
      <path d="M8 20v12h8v-6h8v6h8V20L20 10 8 20Z" fill="#6C4DF6" />
      <path d="M12 20v6h4v-3h8v3h4v-6L20 13l-8 7Z" fill="rgba(108,77,246,0.3)" />
    </svg>
  );
}

// ============================================
// MAIN LANDING PAGE COMPONENT
// ============================================

export default function LandingPage({ onGetStarted }) {
  const [theme, setTheme] = useState("dark");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeCategory, setActiveCategory] = useState('all');
  const [hoveredFeature, setHoveredFeature] = useState(null);
  const [openFAQ, setOpenFAQ] = useState('faq-1');
  const [email, setEmail] = useState("");
  const [isSubscribed, setIsSubscribed] = useState(false);

  // Pricing state
  const [studentCount, setStudentCount] = useState(750);
  const [teacherCount, setTeacherCount] = useState(45);
  const [pricingType, setPricingType] = useState("non-k12");
  const [tokenMonths, setTokenMonths] = useState(1);

  const calculatePrice = () => {
    if (pricingType === "non-k12") {
      return 200 * tokenMonths;
    } else {
      return 500 * Math.ceil(tokenMonths / 3.5);
    }
  };

  const estimatedPrice = calculatePrice();

  const filteredFeatures = FEATURE_LIST.filter(item => 
    activeCategory === 'all' ? true : item.category === activeCategory
  );

  const toggleTheme = () => {
    setTheme(prev => prev === "dark" ? "light" : "dark");
  };

  const toggleFAQ = (id) => {
    setOpenFAQ(openFAQ === id ? null : id);
  };

  const handleSubscribe = (e) => {
    e.preventDefault();
    if (email) {
      setIsSubscribed(true);
      setEmail("");
      setTimeout(() => setIsSubscribed(false), 3000);
    }
  };

  const handleGetStarted = () => {
    if (typeof onGetStarted === "function") {
      onGetStarted();
    }
  };

  const scrollToSection = (id) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
    setMobileMenuOpen(false);
  };

  return (
    <div className={`landing-page ${theme === "light" ? "theme-light" : "theme-dark"}`}>
      
      {/* ===== NAVBAR ===== */}
      <nav className={`navbar ${mobileMenuOpen ? 'mobile-open' : ''}`}>
        <div className="nav-container">
          <div className="nav-brand" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <Logo />
            <span className="brand-text">School<span className="brand-highlight">Dom</span></span>
          </div>

          <div className={`nav-links ${mobileMenuOpen ? 'open' : ''}`}>
            <button onClick={() => scrollToSection('features')}>Features</button>
            <button onClick={() => scrollToSection('pricing')}>Pricing</button>
            <button onClick={() => scrollToSection('testimonials')}>Testimonials</button>
            <button onClick={() => scrollToSection('faq')}>FAQ</button>
            <button className="nav-login">Log In</button>
            <button className="nav-cta" onClick={() => scrollToSection('pricing')}>
              Get Started
            </button>
          </div>

          <div className="nav-actions">
            <button className="theme-toggle" onClick={toggleTheme}>
              {theme === "dark" ? "🌙" : "☀️"}
            </button>
            <button className="mobile-toggle" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
              <span></span><span></span><span></span>
            </button>
          </div>
        </div>
      </nav>

      {/* ===== HERO SECTION ===== */}
      <header className="hero-section">
        <div className="hero-container">
          <div className="hero-badge">🚀 Next-Gen Platform</div>
          
          <h1 className="hero-title">
            Simplify School Management. <br />
            <TypingAnimator />
          </h1>

          <p className="hero-subtitle">
            SchoolDom is the unified central cloud hub designed to simplify academic records administration, 
            automate RFID attendance logging, facilitate secure parent fees clearing, and host immersive 
            online learning spaces.
          </p>

          <div className="hero-actions">
            <button className="btn-primary" onClick={handleGetStarted}>
              Get Started Free →
            </button>
            <button className="btn-secondary" onClick={() => scrollToSection('pricing')}>
              Book a Demo
            </button>
          </div>

          <div className="hero-stats">
            <div className="stat-item">
              <span className="stat-number">1,200+</span>
              <span className="stat-label">Schools</span>
            </div>
            <div className="stat-item">
              <span className="stat-number">500K+</span>
              <span className="stat-label">Students</span>
            </div>
            <div className="stat-item">
              <span className="stat-number">50K+</span>
              <span className="stat-label">Teachers</span>
            </div>
            <div className="stat-item">
              <span className="stat-number">98%</span>
              <span className="stat-label">Satisfaction</span>
            </div>
          </div>
        </div>
      </header>

      {/* ===== VALUE STRIP ===== */}
      <section className="value-strip">
        <div className="value-strip-container">
          <div className="value-item">
            <span className="value-icon">🛡️</span>
            <div>
              <h4>State Department Compliant</h4>
              <p>Full automated coordination with regional student licensing portals</p>
            </div>
          </div>
          <div className="value-item">
            <span className="value-icon">⚡</span>
            <div>
              <h4>Low-latency Node Sizing</h4>
              <p>Fast queries and 99.9% database availability on scalable cloud servers</p>
            </div>
          </div>
          <div className="value-item">
            <span className="value-icon">💻</span>
            <div>
              <h4>Extensive Cross Platform</h4>
              <p>Fully responsive for tablets, computers, and parent mobile devices</p>
            </div>
          </div>
        </div>
      </section>

      {/* ===== FEATURES SECTION ===== */}
      <section id="features" className="features-section">
        <div className="section-container">
          <div className="section-header">
            <span className="section-badge">🏫 Core Architecture Suites</span>
            <h2>All-In-One Unified School Stack</h2>
            <p>Ten meticulously synchronized modular products working inside a single, high-frequency dashboard.</p>
          </div>

          <div className="category-tabs">
            <button className={activeCategory === 'all' ? 'active' : ''} onClick={() => setActiveCategory('all')}>
              All Modules
            </button>
            <button className={activeCategory === 'admin' ? 'active' : ''} onClick={() => setActiveCategory('admin')}>
              Administration
            </button>
            <button className={activeCategory === 'academic' ? 'active' : ''} onClick={() => setActiveCategory('academic')}>
              Academic
            </button>
            <button className={activeCategory === 'finance' ? 'active' : ''} onClick={() => setActiveCategory('finance')}>
              Finance
            </button>
          </div>

          <div className="features-grid">
            {filteredFeatures.map((feat) => (
              <div 
                key={feat.id}
                className="feature-card"
                onMouseEnter={() => setHoveredFeature(feat.id)}
                onMouseLeave={() => setHoveredFeature(null)}
                style={{ '--feature-color': feat.color }}
              >
                <div className="feature-icon" style={{ background: feat.color }}>
                  {feat.icon}
                </div>
                <h3>{feat.title}</h3>
                <p>{feat.description}</p>
                <div className="feature-benefit">
                  <span>Impact:</span>
                  <strong>{feat.benefit}</strong>
                </div>
                <ul className="feature-bullets">
                  {feat.bulletPoints.map((bp, i) => (
                    <li key={i}>✓ {bp}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== PRICING CALCULATOR ===== */}
      <section id="pricing" className="pricing-section">
        <div className="section-container">
          <div className="section-header">
            <span className="section-badge">💰 Pricing Calculator</span>
            <h2>Get an Instant Estimate</h2>
            <p>Calculate your school's monthly cost based on enrollment and modules</p>
          </div>

          <div className="pricing-calculator">
            <div className="pricing-grid">
              <div className="pricing-inputs">
                <div className="input-group">
                  <label>Number of Students</label>
                  <div className="input-controls">
                    <button onClick={() => setStudentCount(Math.max(1, studentCount - 25))}>−</button>
                    <input type="number" value={studentCount} onChange={(e) => setStudentCount(Math.max(1, parseInt(e.target.value) || 0))} />
                    <button onClick={() => setStudentCount(studentCount + 25)}>+</button>
                  </div>
                </div>

                <div className="input-group">
                  <label>Number of Teachers</label>
                  <div className="input-controls">
                    <button onClick={() => setTeacherCount(Math.max(1, teacherCount - 5))}>−</button>
                    <input type="number" value={teacherCount} onChange={(e) => setTeacherCount(Math.max(1, parseInt(e.target.value) || 0))} />
                    <button onClick={() => setTeacherCount(teacherCount + 5)}>+</button>
                  </div>
                </div>

                <div className="input-group">
                  <label>School Type</label>
                  <div className="toggle-group">
                    <button className={pricingType === "non-k12" ? 'active' : ''} onClick={() => setPricingType("non-k12")}>
                      Non K-12
                    </button>
                    <button className={pricingType === "k12" ? 'active' : ''} onClick={() => setPricingType("k12")}>
                      K-12
                    </button>
                  </div>
                </div>

                <div className="input-group">
                  <label>Token Duration</label>
                  <div className="toggle-group">
                    <button className={tokenMonths === 1 ? 'active' : ''} onClick={() => setTokenMonths(1)}>1M</button>
                    <button className={tokenMonths === 3 ? 'active' : ''} onClick={() => setTokenMonths(3)}>3M</button>
                    <button className={tokenMonths === 6 ? 'active' : ''} onClick={() => setTokenMonths(6)}>6M</button>
                    <button className={tokenMonths === 12 ? 'active' : ''} onClick={() => setTokenMonths(12)}>12M</button>
                  </div>
                </div>
              </div>

              <div className="pricing-result">
                <div className="result-card">
                  <div className="result-header">
                    <h3>Estimated Price</h3>
                    <span className="result-badge">Save 20%</span>
                  </div>
                  <div className="result-price">
                    <span className="currency">$</span>
                    <span className="amount">{estimatedPrice}</span>
                    <span className="period">/mo</span>
                  </div>
                  <div className="result-details">
                    <div><span>School Type:</span> <strong>{pricingType === "non-k12" ? "Non K-12" : "K-12"}</strong></div>
                    <div><span>Students:</span> <strong>{studentCount}</strong></div>
                    <div><span>Teachers:</span> <strong>{teacherCount}</strong></div>
                    <div><span>Duration:</span> <strong>{tokenMonths} month{tokenMonths > 1 ? 's' : ''}</strong></div>
                  </div>
                  <button className="result-cta" onClick={handleGetStarted}>
                    Get Started Now →
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== TESTIMONIALS ===== */}
      <section id="testimonials" className="testimonials-section">
        <div className="section-container">
          <div className="section-header">
            <span className="section-badge">⭐ Success Stories</span>
            <h2>Trusted by Leaders in Education</h2>
            <p>Discover how administrators nationwide consolidated into an all-in-one SaaS workflow</p>
          </div>

          <div className="testimonials-grid">
            {TESTIMONIALS_LIST.map((t) => (
              <div key={t.id} className="testimonial-card">
                <div className="testimonial-stars">⭐⭐⭐⭐⭐</div>
                <p className="testimonial-quote">"{t.quote}"</p>
                <div className="testimonial-author">
                  <div className="author-avatar">{t.author.charAt(0)}</div>
                  <div>
                    <h4>{t.author}</h4>
                    <span>{t.role}</span>
                    <small>{t.schoolName}</small>
                  </div>
                  <div className="author-metric">
                    <span>{t.metric}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== FAQ ===== */}
      <section id="faq" className="faq-section">
        <div className="section-container">
          <div className="section-header">
            <span className="section-badge">❓ Frictionless QA</span>
            <h2>Administrative FAQ Desk</h2>
            <p>Find answers regarding security compliance, billing tokens, and custom training</p>
          </div>

          <div className="faq-list">
            {FAQ_ITEMS.map((faq) => (
              <div key={faq.id} className={`faq-item ${openFAQ === faq.id ? 'open' : ''}`}>
                <button onClick={() => toggleFAQ(faq.id)}>
                  <span>{faq.question}</span>
                  <span className="faq-arrow">{openFAQ === faq.id ? '−' : '+'}</span>
                </button>
                <div className="faq-answer">
                  <p>{faq.answer}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="faq-cta">
            <span>Still need assistance?</span>
            <a href={SUPPORT_MAILTO}>Contact our success team →</a>
          </div>
        </div>
      </section>

      {/* ===== NEWSLETTER ===== */}
      <section className="newsletter-section">
        <div className="section-container">
          <div className="newsletter-wrapper">
            <div className="newsletter-icon">📬</div>
            <h2>Stay Updated</h2>
            <p>Subscribe to our newsletter for the latest updates, features, and educational insights.</p>
            
            <form className="newsletter-form" onSubmit={handleSubscribe}>
              <input
                type="email"
                placeholder="Enter your email address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <button type="submit" className="newsletter-btn">
                {isSubscribed ? "✓ Subscribed!" : "Subscribe"}
              </button>
            </form>
            
            <p className="newsletter-note">No spam. Unsubscribe anytime.</p>
          </div>
        </div>
      </section>

      {/* ===== CTA SECTION ===== */}
      <section className="cta-section">
        <div className="section-container">
          <div className="cta-wrapper">
            <span className="cta-badge">🚀 Scale and Transform Today</span>
            <h2>Ready to Revolutionize Your Academic Administration?</h2>
            <p>Join 1,200+ schools who trust SchoolDom to organize student registries, streamline parent collections, and simplify gradebooks.</p>
            <div className="cta-actions">
              <button className="btn-primary" onClick={handleGetStarted}>
                Provision My School Now →
              </button>
              <button className="btn-secondary" onClick={() => scrollToSection('pricing')}>
                Consult Pricing Guides
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ===== FOOTER ===== */}
      <footer className="footer">
        <div className="footer-container">
          <div className="footer-grid">
            <div className="footer-brand">
              <div className="footer-logo">
                <Logo />
                <span>School<span>Dom</span></span>
              </div>
              <p>The next-generation educational administration operating system.</p>
              <div className="footer-status">
                <span className="status-dot"></span>
                All SaaS Nodes Operational
              </div>
            </div>

            <div className="footer-links">
              <h4>Products</h4>
              <ul>
                <li><a href="#features">Core SIS Database</a></li>
                <li><a href="#features">Smart Attendance</a></li>
                <li><a href="#features">Digital Ledger</a></li>
                <li><a href="#features">Virtual Accounts</a></li>
              </ul>
            </div>

            <div className="footer-links">
              <h4>Solutions</h4>
              <ul>
                <li><a href="#pricing">K-12 Schools</a></li>
                <li><a href="#pricing">Charter Academies</a></li>
                <li><a href="#pricing">Non K-12 Colleges</a></li>
                <li><a href="#pricing">Multi-campus Districts</a></li>
              </ul>
            </div>

            <div className="footer-links">
              <h4>Support</h4>
              <ul>
                <li><a href={SUPPORT_MAILTO}>{SUPPORT_EMAIL}</a></li>
                <li><a href="#faq">Help Documentation</a></li>
                <li><a href="#faq">Privacy Policy</a></li>
                <li><a href="#faq">SLA Contract</a></li>
              </ul>
            </div>
          </div>

          <div className="footer-bottom">
            <p>&copy; 2026 SchoolDom Technologies, Inc. All rights reserved.</p>
            <div className="footer-social">
              <a href="#">🐙</a>
              <a href="#">🐦</a>
              <a href="#">🔗</a>
            </div>
          </div>
        </div>
      </footer>

      {/* ===== CSS STYLES ===== */}
      <style jsx>{`
        /* ============================================
           RESET & BASE
           ============================================ */
        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }

        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
          overflow-x: hidden;
        }

        .landing-page {
          min-height: 100vh;
          transition: background-color 0.4s ease, color 0.4s ease;
          position: relative;
        }

        .landing-page.theme-dark {
          background: #030014;
          color: #f8fafc;
        }

        .landing-page.theme-light {
          background: #f5f0ff;
          color: #0f172a;
        }

        /* ============================================
           NAVBAR
           ============================================ */
        .navbar {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          z-index: 1000;
          padding: 0.75rem 1.5rem;
          background: rgba(3, 0, 20, 0.85);
          backdrop-filter: blur(16px);
          border-bottom: 1px solid rgba(255, 255, 255, 0.06);
          transition: all 0.3s ease;
        }

        .theme-light .navbar {
          background: rgba(245, 240, 255, 0.92);
          border-bottom: 1px solid rgba(108, 77, 246, 0.08);
        }

        .nav-container {
          max-width: 1280px;
          margin: 0 auto;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
        }

        .nav-brand {
          display: flex;
          align-items: center;
          gap: 0.6rem;
          cursor: pointer;
          flex-shrink: 0;
        }

        .logo-svg {
          width: 32px;
          height: 32px;
        }

        .brand-text {
          font-size: 1.3rem;
          font-weight: 800;
          background: linear-gradient(135deg, #6366f1, #8b5cf6, #a78bfa);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .brand-highlight {
          color: #6C4DF6;
          -webkit-text-fill-color: #6C4DF6;
        }

        .nav-links {
          display: flex;
          align-items: center;
          gap: 2rem;
        }

        .nav-links button {
          background: none;
          border: none;
          color: #9ca3af;
          font-size: 0.9rem;
          cursor: pointer;
          transition: color 0.2s;
          padding: 0.4rem 0;
          position: relative;
        }

        .nav-links button:hover {
          color: #6366f1;
        }

        .nav-links button::after {
          content: '';
          position: absolute;
          bottom: 0;
          left: 0;
          width: 0;
          height: 2px;
          background: #6366f1;
          transition: width 0.3s;
        }

        .nav-links button:hover::after {
          width: 100%;
        }

        .theme-light .nav-links button {
          color: #4b5563;
        }

        .theme-light .nav-links button:hover {
          color: #6366f1;
        }

        .nav-login {
          padding: 0.4rem 1.2rem !important;
          border: 1px solid rgba(99, 102, 241, 0.3) !important;
          border-radius: 8px;
          background: rgba(99, 102, 241, 0.08) !important;
        }

        .nav-login::after {
          display: none !important;
        }

        .nav-login:hover {
          background: rgba(99, 102, 241, 0.15) !important;
          border-color: #6366f1 !important;
        }

        .nav-cta {
          padding: 0.5rem 1.5rem !important;
          border-radius: 10px !important;
          background: linear-gradient(135deg, #6366f1, #7c3aed) !important;
          color: white !important;
          font-weight: 600 !important;
          box-shadow: 0 4px 20px rgba(99, 102, 241, 0.3) !important;
        }

        .nav-cta:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 30px rgba(99, 102, 241, 0.4) !important;
          color: white !important;
        }

        .nav-cta::after {
          display: none !important;
        }

        .nav-actions {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          flex-shrink: 0;
        }

        .theme-toggle {
          width: 38px;
          height: 38px;
          border-radius: 50%;
          border: 1px solid rgba(255, 255, 255, 0.1);
          background: rgba(255, 255, 255, 0.06);
          font-size: 1.2rem;
          cursor: pointer;
          transition: all 0.3s;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .theme-toggle:hover {
          transform: rotate(20deg) scale(1.05);
          background: rgba(99, 102, 241, 0.15);
        }

        .theme-light .theme-toggle {
          background: rgba(99, 102, 241, 0.08);
          border-color: rgba(99, 102, 241, 0.15);
        }

        .mobile-toggle {
          display: none;
          flex-direction: column;
          gap: 4px;
          background: none;
          border: none;
          cursor: pointer;
          padding: 4px;
        }

        .mobile-toggle span {
          display: block;
          width: 24px;
          height: 2px;
          background: #9ca3af;
          border-radius: 2px;
          transition: all 0.3s;
        }

        .mobile-toggle:hover span {
          background: #6366f1;
        }

        /* ============================================
           HERO
           ============================================ */
        .hero-section {
          padding: 8rem 1.5rem 4rem;
          max-width: 1280px;
          margin: 0 auto;
          text-align: center;
        }

        .hero-badge {
          display: inline-block;
          padding: 0.3rem 1rem;
          border-radius: 50px;
          background: rgba(99, 102, 241, 0.12);
          color: #818cf8;
          font-size: 0.8rem;
          font-weight: 500;
          margin-bottom: 1.5rem;
          border: 1px solid rgba(99, 102, 241, 0.2);
        }

        .hero-title {
          font-size: 3.5rem;
          font-weight: 800;
          line-height: 1.1;
          margin-bottom: 1.5rem;
          letter-spacing: -0.02em;
        }

        .typing-text {
          display: inline-block;
          font-weight: 900;
          font-style: italic;
          text-shadow: 0 0 40px rgba(99, 102, 241, 0.2);
        }

        .typing-text.serif {
          font-family: 'Georgia', 'Times New Roman', serif;
        }

        .typing-text.mono {
          font-family: 'Courier New', monospace;
        }

        .typing-text.sans {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        .cursor-blink {
          animation: blink 0.7s step-end infinite;
        }

        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }

        .hero-subtitle {
          font-size: 1.1rem;
          color: #9ca3af;
          max-width: 640px;
          margin: 0 auto 2.5rem;
          line-height: 1.7;
        }

        .theme-light .hero-subtitle {
          color: #4b5563;
        }

        .hero-actions {
          display: flex;
          gap: 0.75rem;
          justify-content: center;
          flex-wrap: wrap;
          margin-bottom: 3rem;
        }

        .btn-primary {
          display: inline-flex;
          align-items: center;
          gap: 0.6rem;
          padding: 0.8rem 2rem;
          border-radius: 12px;
          font-size: 0.95rem;
          font-weight: 600;
          cursor: pointer;
          border: none;
          background: linear-gradient(135deg, #6366f1, #7c3aed);
          color: white;
          box-shadow: 0 4px 20px rgba(99, 102, 241, 0.3);
          transition: all 0.3s;
        }

        .btn-primary:hover {
          transform: translateY(-2px) scale(1.02);
          box-shadow: 0 8px 30px rgba(99, 102, 241, 0.4);
        }

        .btn-secondary {
          display: inline-flex;
          align-items: center;
          padding: 0.8rem 2rem;
          border-radius: 12px;
          font-size: 0.95rem;
          font-weight: 600;
          cursor: pointer;
          border: 1px solid rgba(255, 255, 255, 0.1);
          background: rgba(255, 255, 255, 0.06);
          color: #e5e7eb;
          transition: all 0.3s;
        }

        .btn-secondary:hover {
          background: rgba(255, 255, 255, 0.12);
        }

        .theme-light .btn-secondary {
          border-color: rgba(0, 0, 0, 0.1);
          background: rgba(0, 0, 0, 0.04);
          color: #1a1a2e;
        }

        .theme-light .btn-secondary:hover {
          background: rgba(0, 0, 0, 0.08);
        }

        .hero-stats {
          display: flex;
          justify-content: center;
          gap: 3rem;
          padding-top: 1.5rem;
          border-top: 1px solid rgba(255, 255, 255, 0.06);
          flex-wrap: wrap;
        }

        .theme-light .hero-stats {
          border-top-color: rgba(0, 0, 0, 0.06);
        }

        .stat-item {
          display: flex;
          flex-direction: column;
          align-items: center;
        }

        .stat-number {
          font-size: 1.8rem;
          font-weight: 700;
          color: #6366f1;
        }

        .stat-label {
          font-size: 0.8rem;
          color: #9ca3af;
          margin-top: 0.15rem;
        }

        /* ============================================
           VALUE STRIP
           ============================================ */
        .value-strip {
          padding: 2rem 1.5rem;
          background: rgba(255, 255, 255, 0.03);
          border-top: 1px solid rgba(255, 255, 255, 0.06);
          border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        }

        .theme-light .value-strip {
          background: rgba(255, 255, 255, 0.5);
          border-color: rgba(0, 0, 0, 0.06);
        }

        .value-strip-container {
          max-width: 1280px;
          margin: 0 auto;
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 2rem;
        }

        .value-item {
          display: flex;
          align-items: flex-start;
          gap: 1rem;
        }

        .value-icon {
          font-size: 2rem;
          flex-shrink: 0;
        }

        .value-item h4 {
          font-size: 0.95rem;
          font-weight: 600;
          margin-bottom: 0.25rem;
        }

        .value-item p {
          font-size: 0.85rem;
          color: #9ca3af;
        }

        .theme-light .value-item p {
          color: #6b7280;
        }

        /* ============================================
           SECTION COMMON
           ============================================ */
        .section-container {
          max-width: 1280px;
          margin: 0 auto;
          padding: 0 1.5rem;
        }

        .section-header {
          text-align: center;
          max-width: 800px;
          margin: 0 auto 3rem;
        }

        .section-badge {
          display: inline-block;
          padding: 0.25rem 0.75rem;
          border-radius: 50px;
          background: rgba(99, 102, 241, 0.1);
          color: #818cf8;
          font-size: 0.75rem;
          font-weight: 600;
          margin-bottom: 0.75rem;
          border: 1px solid rgba(99, 102, 241, 0.15);
        }

        .section-header h2 {
          font-size: 2.5rem;
          font-weight: 700;
          margin-bottom: 0.75rem;
          background: linear-gradient(135deg, #6366f1, #8b5cf6, #a78bfa);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .section-header p {
          font-size: 1rem;
          color: #9ca3af;
          line-height: 1.6;
        }

        .theme-light .section-header p {
          color: #6b7280;
        }

        /* ============================================
           FEATURES
           ============================================ */
        .features-section {
          padding: 5rem 0;
        }

        .category-tabs {
          display: flex;
          justify-content: center;
          gap: 0.5rem;
          margin-bottom: 2.5rem;
          flex-wrap: wrap;
        }

        .category-tabs button {
          padding: 0.5rem 1.25rem;
          border-radius: 10px;
          border: 1px solid rgba(255, 255, 255, 0.06);
          background: rgba(255, 255, 255, 0.03);
          color: #9ca3af;
          font-size: 0.85rem;
          cursor: pointer;
          transition: all 0.3s;
        }

        .category-tabs button:hover {
          border-color: rgba(99, 102, 241, 0.3);
        }

        .category-tabs button.active {
          background: rgba(99, 102, 241, 0.12);
          border-color: #6366f1;
          color: #818cf8;
        }

        .theme-light .category-tabs button {
          border-color: rgba(0, 0, 0, 0.06);
          background: rgba(0, 0, 0, 0.02);
          color: #6b7280;
        }

        .theme-light .category-tabs button.active {
          background: rgba(99, 102, 241, 0.08);
          color: #6366f1;
        }

        .features-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 1.5rem;
        }

        .feature-card {
          padding: 1.5rem;
          border-radius: 16px;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.06);
          transition: all 0.3s;
        }

        .feature-card:hover {
          transform: translateY(-4px);
          border-color: var(--feature-color, #6366f1);
          box-shadow: 0 8px 30px rgba(99, 102, 241, 0.08);
        }

        .theme-light .feature-card {
          background: rgba(255, 255, 255, 0.6);
          border-color: rgba(0, 0, 0, 0.06);
        }

        .feature-icon {
          width: 48px;
          height: 48px;
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.5rem;
          margin-bottom: 0.75rem;
        }

        .feature-card h3 {
          font-size: 1.05rem;
          font-weight: 600;
          margin-bottom: 0.5rem;
        }

        .feature-card p {
          font-size: 0.85rem;
          color: #9ca3af;
          line-height: 1.5;
          margin-bottom: 0.75rem;
        }

        .theme-light .feature-card p {
          color: #6b7280;
        }

        .feature-benefit {
          font-size: 0.8rem;
          padding: 0.4rem 0.75rem;
          border-radius: 8px;
          background: rgba(99, 102, 241, 0.06);
          border: 1px solid rgba(99, 102, 241, 0.08);
          margin-bottom: 0.75rem;
        }

        .feature-benefit span {
          color: #9ca3af;
        }

        .feature-benefit strong {
          color: #6366f1;
        }

        .feature-bullets {
          list-style: none;
          font-size: 0.8rem;
          color: #9ca3af;
        }

        .theme-light .feature-bullets {
          color: #6b7280;
        }

        .feature-bullets li {
          padding: 0.2rem 0;
        }

        /* ============================================
           PRICING
           ============================================ */
        .pricing-section {
          padding: 5rem 0;
        }

        .pricing-calculator {
          background: rgba(255, 255, 255, 0.04);
          border-radius: 20px;
          padding: 2rem;
          border: 1px solid rgba(255, 255, 255, 0.06);
        }

        .theme-light .pricing-calculator {
          background: rgba(255, 255, 255, 0.7);
          border-color: rgba(99, 102, 241, 0.08);
        }

        .pricing-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 2rem;
        }

        .pricing-inputs {
          display: flex;
          flex-direction: column;
          gap: 1.25rem;
        }

        .input-group {
          display: flex;
          flex-direction: column;
          gap: 0.4rem;
        }

        .input-group label {
          font-size: 0.85rem;
          font-weight: 500;
          color: #9ca3af;
        }

        .theme-light .input-group label {
          color: #6b7280;
        }

        .input-controls {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .input-controls button {
          width: 34px;
          height: 34px;
          border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.1);
          background: rgba(255, 255, 255, 0.04);
          color: #e5e7eb;
          font-size: 1.1rem;
          cursor: pointer;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .theme-light .input-controls button {
          border-color: rgba(0, 0, 0, 0.1);
          background: rgba(0, 0, 0, 0.04);
          color: #1a1a2e;
        }

        .input-controls button:hover {
          background: rgba(99, 102, 241, 0.15);
          border-color: #6366f1;
        }

        .input-controls input {
          width: 80px;
          padding: 0.5rem 0.75rem;
          border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.1);
          background: rgba(255, 255, 255, 0.04);
          color: #e5e7eb;
          font-size: 0.95rem;
          text-align: center;
        }

        .theme-light .input-controls input {
          border-color: rgba(0, 0, 0, 0.1);
          background: white;
          color: #1a1a2e;
        }

        .toggle-group {
          display: flex;
          gap: 0.4rem;
          flex-wrap: wrap;
        }

        .toggle-group button {
          padding: 0.4rem 1rem;
          border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.08);
          background: rgba(255, 255, 255, 0.04);
          color: #9ca3af;
          cursor: pointer;
          transition: all 0.2s;
          font-size: 0.85rem;
          flex: 1;
          min-width: 50px;
          text-align: center;
        }

        .theme-light .toggle-group button {
          border-color: rgba(0, 0, 0, 0.08);
          background: rgba(0, 0, 0, 0.04);
          color: #6b7280;
        }

        .toggle-group button.active {
          background: rgba(99, 102, 241, 0.15);
          border-color: #6366f1;
          color: #818cf8;
        }

        .theme-light .toggle-group button.active {
          background: rgba(99, 102, 241, 0.1);
          color: #6366f1;
        }

        .toggle-group button:hover {
          border-color: #6366f1;
        }

        /* Result */
        .pricing-result {
          display: flex;
          align-items: stretch;
        }

        .result-card {
          background: linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(124, 58, 237, 0.05));
          border-radius: 16px;
          padding: 1.5rem;
          border: 1px solid rgba(99, 102, 241, 0.15);
          width: 100%;
          display: flex;
          flex-direction: column;
        }

        .theme-light .result-card {
          background: linear-gradient(135deg, rgba(99, 102, 241, 0.04), rgba(124, 58, 237, 0.02));
        }

        .result-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.75rem;
        }

        .result-header h3 {
          font-size: 1rem;
          font-weight: 600;
          color: #9ca3af;
        }

        .theme-light .result-header h3 {
          color: #6b7280;
        }

        .result-badge {
          font-size: 0.7rem;
          padding: 0.2rem 0.6rem;
          border-radius: 50px;
          background: rgba(99, 102, 241, 0.12);
          color: #818cf8;
          font-weight: 500;
        }

        .result-price {
          margin-bottom: 1rem;
        }

        .result-price .currency {
          font-size: 1.2rem;
          font-weight: 600;
          color: #e5e7eb;
        }

        .theme-light .result-price .currency {
          color: #1a1a2e;
        }

        .result-price .amount {
          font-size: 3rem;
          font-weight: 800;
          color: #6366f1;
        }

        .result-price .period {
          font-size: 1rem;
          color: #9ca3af;
          font-weight: 400;
        }

        .result-details {
          display: flex;
          flex-direction: column;
          gap: 0.3rem;
          margin-bottom: 1rem;
          padding: 0.75rem;
          background: rgba(0, 0, 0, 0.2);
          border-radius: 8px;
        }

        .theme-light .result-details {
          background: rgba(0, 0, 0, 0.03);
        }

        .result-details div {
          display: flex;
          justify-content: space-between;
          font-size: 0.85rem;
        }

        .result-details div span {
          color: #9ca3af;
        }

        .theme-light .result-details div span {
          color: #6b7280;
        }

        .result-details div strong {
          color: #e5e7eb;
        }

        .theme-light .result-details div strong {
          color: #1a1a2e;
        }

        .result-cta {
          padding: 0.8rem;
          border-radius: 10px;
          border: none;
          background: linear-gradient(135deg, #6366f1, #7c3aed);
          color: white;
          font-size: 0.95rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.3s;
          margin-top: auto;
        }

        .result-cta:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 25px rgba(99, 102, 241, 0.3);
        }

        /* ============================================
           TESTIMONIALS
           ============================================ */
        .testimonials-section {
          padding: 5rem 0;
        }

        .testimonials-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 1.5rem;
        }

        .testimonial-card {
          padding: 1.5rem;
          border-radius: 16px;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.06);
          transition: all 0.3s;
        }

        .testimonial-card:hover {
          transform: translateY(-4px);
          border-color: rgba(99, 102, 241, 0.3);
        }

        .theme-light .testimonial-card {
          background: rgba(255, 255, 255, 0.6);
          border-color: rgba(0, 0, 0, 0.06);
        }

        .testimonial-stars {
          font-size: 1rem;
          margin-bottom: 0.75rem;
        }

        .testimonial-quote {
          font-size: 0.9rem;
          line-height: 1.6;
          color: #d1d5db;
          font-style: italic;
          margin-bottom: 1rem;
        }

        .theme-light .testimonial-quote {
          color: #4b5563;
        }

        .testimonial-author {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding-top: 0.75rem;
          border-top: 1px solid rgba(255, 255, 255, 0.06);
          flex-wrap: wrap;
        }

        .theme-light .testimonial-author {
          border-top-color: rgba(0, 0, 0, 0.06);
        }

        .author-avatar {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          background: #6366f1;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-weight: 700;
          font-size: 1.1rem;
          flex-shrink: 0;
        }

        .testimonial-author h4 {
          font-size: 0.9rem;
          font-weight: 600;
        }

        .testimonial-author span {
          font-size: 0.75rem;
          color: #9ca3af;
          display: block;
        }

        .testimonial-author small {
          font-size: 0.7rem;
          color: #6366f1;
          display: block;
        }

        .author-metric {
          margin-left: auto;
          padding: 0.25rem 0.6rem;
          border-radius: 8px;
          background: rgba(99, 102, 241, 0.08);
          border: 1px solid rgba(99, 102, 241, 0.1);
        }

        .author-metric span {
          font-size: 0.7rem;
          font-weight: 600;
          color: #818cf8;
        }

        /* ============================================
           FAQ
           ============================================ */
        .faq-section {
          padding: 5rem 0;
        }

        .faq-list {
          max-width: 800px;
          margin: 0 auto;
        }

        .faq-item {
          border: 1px solid rgba(255, 255, 255, 0.06);
          border-radius: 12px;
          margin-bottom: 0.75rem;
          overflow: hidden;
          transition: all 0.3s;
          background: rgba(255, 255, 255, 0.02);
        }

        .theme-light .faq-item {
          border-color: rgba(0, 0, 0, 0.06);
          background: rgba(255, 255, 255, 0.4);
        }

        .faq-item.open {
          border-color: rgba(99, 102, 241, 0.3);
        }

        .faq-item button {
          width: 100%;
          padding: 1rem 1.25rem;
          background: none;
          border: none;
          color: #e5e7eb;
          font-size: 0.95rem;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          justify-content: space-between;
          align-items: center;
          text-align: left;
        }

        .theme-light .faq-item button {
          color: #1a1a2e;
        }

        .faq-item button:hover {
          color: #6366f1;
        }

        .faq-arrow {
          font-size: 1.5rem;
          color: #6366f1;
          flex-shrink: 0;
          margin-left: 1rem;
        }

        .faq-answer {
          max-height: 0;
          overflow: hidden;
          transition: all 0.3s ease;
        }

        .faq-item.open .faq-answer {
          max-height: 500px;
          padding: 0 1.25rem 1.25rem;
        }

        .faq-answer p {
          font-size: 0.9rem;
          color: #9ca3af;
          line-height: 1.6;
        }

        .theme-light .faq-answer p {
          color: #6b7280;
        }

        .faq-cta {
          text-align: center;
          margin-top: 2rem;
          font-size: 0.9rem;
          color: #9ca3af;
        }

        .faq-cta a {
          color: #6366f1;
          text-decoration: none;
          font-weight: 600;
        }

        .faq-cta a:hover {
          color: #8b5cf6;
        }

        /* ============================================
           NEWSLETTER
           ============================================ */
        .newsletter-section {
          padding: 4rem 0;
        }

        .newsletter-wrapper {
          background: linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(124, 58, 237, 0.04));
          border-radius: 24px;
          padding: 3rem 2rem;
          border: 1px solid rgba(99, 102, 241, 0.1);
          text-align: center;
        }

        .theme-light .newsletter-wrapper {
          background: rgba(99, 102, 241, 0.04);
        }

        .newsletter-icon {
          font-size: 3rem;
          margin-bottom: 1rem;
        }

        .newsletter-wrapper h2 {
          font-size: 1.8rem;
          font-weight: 700;
          margin-bottom: 0.5rem;
        }

        .newsletter-wrapper p {
          color: #9ca3af;
          font-size: 1rem;
          margin-bottom: 1.5rem;
        }

        .theme-light .newsletter-wrapper p {
          color: #6b7280;
        }

        .newsletter-form {
          display: flex;
          gap: 0.75rem;
          justify-content: center;
          flex-wrap: wrap;
        }

        .newsletter-form input {
          flex: 1;
          min-width: 200px;
          padding: 0.75rem 1rem;
          border-radius: 12px;
          border: 1px solid rgba(255, 255, 255, 0.1);
          background: rgba(255, 255, 255, 0.05);
          color: #e5e7eb;
          font-size: 0.95rem;
        }

        .theme-light .newsletter-form input {
          border-color: rgba(0, 0, 0, 0.1);
          background: rgba(255, 255, 255, 0.8);
          color: #1a1a2e;
        }

        .newsletter-form input:focus {
          outline: none;
          border-color: #6366f1;
        }

        .newsletter-btn {
          padding: 0.75rem 2rem;
          border-radius: 12px;
          border: none;
          background: linear-gradient(135deg, #6366f1, #7c3aed);
          color: white;
          font-size: 0.95rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.3s;
        }

        .newsletter-btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 25px rgba(99, 102, 241, 0.3);
        }

        .newsletter-note {
          font-size: 0.75rem;
          color: #6b7280;
          margin-top: 0.75rem;
        }

        /* ============================================
           CTA SECTION
           ============================================ */
        .cta-section {
          padding: 4rem 0;
        }

        .cta-wrapper {
          text-align: center;
          padding: 3rem 2rem;
          background: rgba(255, 255, 255, 0.02);
          border-radius: 24px;
          border: 1px solid rgba(255, 255, 255, 0.06);
        }

        .theme-light .cta-wrapper {
          background: rgba(255, 255, 255, 0.4);
          border-color: rgba(0, 0, 0, 0.06);
        }

        .cta-badge {
          display: inline-block;
          padding: 0.25rem 0.75rem;
          border-radius: 50px;
          background: rgba(99, 102, 241, 0.1);
          color: #818cf8;
          font-size: 0.75rem;
          font-weight: 600;
          margin-bottom: 1rem;
          border: 1px solid rgba(99, 102, 241, 0.15);
        }

        .cta-wrapper h2 {
          font-size: 2.5rem;
          font-weight: 700;
          margin-bottom: 0.75rem;
        }

        .cta-wrapper p {
          font-size: 1.05rem;
          color: #9ca3af;
          max-width: 600px;
          margin: 0 auto 1.5rem;
        }

        .theme-light .cta-wrapper p {
          color: #6b7280;
        }

        .cta-actions {
          display: flex;
          gap: 0.75rem;
          justify-content: center;
          flex-wrap: wrap;
        }

        /* ============================================
           FOOTER
           ============================================ */
        .footer {
          padding: 3rem 1.5rem 1.5rem;
          border-top: 1px solid rgba(255, 255, 255, 0.06);
        }

        .theme-light .footer {
          border-top-color: rgba(0, 0, 0, 0.06);
        }

        .footer-container {
          max-width: 1280px;
          margin: 0 auto;
        }

        .footer-grid {
          display: grid;
          grid-template-columns: 2fr 1fr 1fr 1fr;
          gap: 2rem;
          padding-bottom: 2rem;
          border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        }

        .theme-light .footer-grid {
          border-bottom-color: rgba(0, 0, 0, 0.04);
        }

        .footer-brand .footer-logo {
          display: flex;
          align-items: center;
          gap: 0.6rem;
          font-size: 1.2rem;
          font-weight: 700;
          margin-bottom: 0.75rem;
        }

        .footer-brand .footer-logo span {
          background: linear-gradient(135deg, #6366f1, #8b5cf6);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .footer-brand .footer-logo span span {
          -webkit-text-fill-color: #6C4DF6;
        }

        .footer-brand p {
          font-size: 0.85rem;
          color: #9ca3af;
          max-width: 250px;
          line-height: 1.5;
        }

        .theme-light .footer-brand p {
          color: #6b7280;
        }

        .footer-status {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.3rem 0.75rem;
          border-radius: 50px;
          font-size: 0.7rem;
          background: rgba(16, 185, 129, 0.1);
          border: 1px solid rgba(16, 185, 129, 0.15);
          color: #10b981;
          margin-top: 0.75rem;
        }

        .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #10b981;
          animation: pulse-dot 2s ease-in-out infinite;
        }

        @keyframes pulse-dot {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }

        .footer-links h4 {
          font-size: 0.85rem;
          font-weight: 600;
          margin-bottom: 0.75rem;
        }

        .footer-links ul {
          list-style: none;
        }

        .footer-links ul li {
          margin-bottom: 0.4rem;
        }

        .footer-links ul li a {
          color: #9ca3af;
          text-decoration: none;
          font-size: 0.85rem;
          transition: color 0.2s;
        }

        .theme-light .footer-links ul li a {
          color: #6b7280;
        }

        .footer-links ul li a:hover {
          color: #6366f1;
        }

        .footer-bottom {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-top: 1.5rem;
          font-size: 0.8rem;
          color: #6b7280;
        }

        .footer-social {
          display: flex;
          gap: 0.75rem;
        }

        .footer-social a {
          color: #9ca3af;
          text-decoration: none;
          font-size: 1.2rem;
          transition: color 0.2s;
        }

        .footer-social a:hover {
          color: #6366f1;
        }

        /* ============================================
           RESPONSIVE
           ============================================ */
        @media (max-width: 1024px) {
          .hero-title {
            font-size: 2.8rem;
          }

          .features-grid {
            grid-template-columns: repeat(2, 1fr);
          }

          .testimonials-grid {
            grid-template-columns: repeat(2, 1fr);
          }

          .pricing-grid {
            grid-template-columns: 1fr;
            gap: 1.5rem;
          }
        }

        @media (max-width: 768px) {
          .nav-links {
            display: none;
            flex-direction: column;
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: rgba(3, 0, 20, 0.98);
            padding: 1.5rem;
            gap: 1rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
          }

          .theme-light .nav-links.open {
            background: rgba(245, 240, 255, 0.98);
          }

          .nav-links.open {
            display: flex;
          }

          .mobile-toggle {
            display: flex;
          }

          .hero-title {
            font-size: 2rem;
          }

          .hero-stats {
            gap: 1.5rem;
          }

          .stat-number {
            font-size: 1.3rem;
          }

          .value-strip-container {
            grid-template-columns: 1fr;
            gap: 1.5rem;
          }

          .features-grid {
            grid-template-columns: 1fr;
          }

          .testimonials-grid {
            grid-template-columns: 1fr;
          }

          .footer-grid {
            grid-template-columns: 1fr;
            gap: 1.5rem;
          }

          .section-header h2 {
            font-size: 2rem;
          }

          .result-price .amount {
            font-size: 2.5rem;
          }

          .cta-wrapper h2 {
            font-size: 1.8rem;
          }

          .testimonial-author {
            flex-direction: column;
            align-items: flex-start;
          }

          .author-metric {
            margin-left: 0;
          }

          .newsletter-form {
            flex-direction: column;
          }

          .newsletter-form input {
            min-width: unset;
          }
        }

        @media (max-width: 480px) {
          .hero-title {
            font-size: 1.6rem;
          }

          .hero-actions {
            flex-direction: column;
            align-items: stretch;
          }

          .btn-primary,
          .btn-secondary {
            justify-content: center;
          }

          .cta-actions {
            flex-direction: column;
            align-items: stretch;
          }

          .category-tabs button {
            font-size: 0.75rem;
            padding: 0.3rem 0.8rem;
          }

          .toggle-group button {
            font-size: 0.75rem;
            padding: 0.3rem 0.6rem;
          }

          .input-controls input {
            width: 60px;
          }
        }
      `}</style>
    </div>
  );
}