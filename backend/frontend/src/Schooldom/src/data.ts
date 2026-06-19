import { SolutionFeature, Testimonial } from './types';

export const SOLUTIONS: SolutionFeature[] = [
  {
    id: 'cbt-system',
    title: 'Hybrid Online/Offline CBT',
    shortDescription: 'Conduct major assessments and exams confidently without worrying about internet cuts or costly web subscriptions.',
    description: 'A revolutionary computer-based testing engine designed for local African operations. It runs locally via smart caching and local area hosting, then synchs scores to the cloud when connections resume. Includes specialized modes for JAMB (UTME) and WAEC formats.',
    category: 'academic',
    icon: 'Terminal',
    benefits: [
      'Works 100% offline via a local server module',
      'JAMB and WAEC replica timer & review modes',
      'Anti-cheat viewport tracking and secure lock-out browser app',
      'Instant grading and auto-uploaded feedback sheets'
    ],
    specs: 'Requires zero external bandwidth during active exams.'
  },
  {
    id: 'finance-gateways',
    title: 'Finance & Payments Ledger',
    shortDescription: 'Automate termly school fee collections, generate invoices, send receipts, and manage direct splits.',
    description: 'Equip your school bursar with self-reconciling records. Parents receive digital invoices via SMS or WhatsApp and can make secure payments via integrated cards, bank transfers, or bank branch channels. Splitting payments between group accounts is simple and automatic.',
    category: 'finance',
    icon: 'CreditCard',
    benefits: [
      'Multi-channel online pay integration (Flutterwave, Paystack)',
      'Partial payments tracking and late fee automations',
      'Automated expense recording and vendor balances ledger',
      'Salary and payroll slips builder for teachers & admin staff'
    ],
    specs: 'Saves finance admins up to 18 hours per week in audits.'
  },
  {
    id: 'report-cards',
    title: 'Academic Report Sheets Generator',
    shortDescription: 'Replace manual excel computing with automated beautiful analytics for continuous assessments and term finals.',
    description: 'Transform continuous assessments (CAs) and exams scores into graphic, fully-formatted progress reports instantly. Custom comment templates driven by performance indicators make report compiling painless for teachers.',
    category: 'academic',
    icon: 'FileSpreadsheet',
    benefits: [
      'Fully customizable grading scales (A1 to F9 presets or customized)',
      'Automated aggregate, class averages, and position rankings',
      'Dynamic charts illustrating subject performance history',
      'Principal and class teacher auto-signature stamp placements'
    ]
  },
  {
    id: 'attendance-tracking',
    title: 'Biometric & QR Attendance',
    shortDescription: 'Dynamic registers for staff development, teacher schedules, and student safety checking.',
    description: 'Track clock-ins for students and staff with lightning fast scanning. Use existing tablets/smartphones as QR code readers or pair with compatible fingerprint readers. Know exactly who enters, leaves, or misses lessons.',
    category: 'operations',
    icon: 'UserCheck',
    benefits: [
      'SMS alerts sent automatically to parents on student entry/exit',
      'Teacher lesson attendance verification tracking',
      'Comprehensive monthly export sheets for payroll calculations',
      'Mobile-responsive check-in console'
    ]
  },
  {
    id: 'daily-quizzes',
    title: 'Daily Personalized Learner Quizzes',
    shortDescription: 'Nurture revision habits with custom questions targeted at individual weak points.',
    description: 'Schooldom leverages systematic feedback algorithms to give students 10 personalized micro-questions daily on topics they covered in their lesson planners. Keeps material fresh and keeps students highly active.',
    category: 'students',
    icon: 'Sparkles',
    benefits: [
      'Curriculum-mapped to WAEC/JAMB standards (O-Level / UTME)',
      'Bite-sized micro-learning gamification with profile levels',
      'Parent dashboard to view personalized study progress',
      'Offline-capable quiz sheets printable with clear solutions'
    ]
  },
  {
    id: 'jamb-waec-bank',
    title: 'Extensive JAMB/WAEC Exam Banks',
    shortDescription: 'Over 25,000+ past questions across 18 subjects for thorough external exam prep.',
    description: 'Empower senior secondary students with real, fully solved historical exams. Our databases contain verified answers, detailed step-by-step reasoning diagrams, and mock simulations to maximize pass rates.',
    category: 'students',
    icon: 'Library',
    benefits: [
      'Full subject past papers covering physics, maths, English, and more',
      'Performance analytics detailing score predictions',
      'Diagnostic tests to find where student conceptual gaps are',
      'Classroom-wide teacher-led exam assignment tasks'
    ]
  },
  {
    id: 'data-migration',
    title: 'Seamless Data Integration',
    shortDescription: 'Migrate thousands of legacy papers, spreadsheets, or physical records effortlessly with our white-glove migration tier.',
    description: 'Worried about losing historical records? Our dedicated integration experts do all the heavy lifting. Send us your Excel files, CSV files, or access codes, and we will translate your school records to Schooldom flawlessly in under 48 hours.',
    category: 'operations',
    icon: 'DatabaseZap',
    benefits: [
      'Zero downtime migration of thousands of historical student files',
      'Duplicate detection and deep clean indexing',
      'Bulk photo uploads for automatic face identification matching',
      'Import directly from other legacy school managers'
    ]
  },
  {
    id: 'lesson-planner',
    title: 'Interactive Lesson Planner & Materials Hub',
    shortDescription: 'Simplify curriculum scheduling, standard lesson objectives, and direct sharing to school portals.',
    description: 'Standardize material quality across all arms of your school. Teachers map lessons easily against preloaded academic curricula, attach homework handouts, and submit layouts to vice principals for approval before classes begin.',
    category: 'operations',
    icon: 'Layers',
    benefits: [
      'Digital curriculum templates synced to major West African frameworks',
      'Share notes, slides, and links directly into student home screens',
      'Review workflow with simple dean approval logs',
      'Substituted teacher helper mode to access standard class plans'
    ]
  },
  {
    id: 'id-cards',
    title: 'Bulk Digital & Printable ID Cards',
    shortDescription: 'Export modern, professional student and staff badges in bulk with active security QR codes.',
    description: 'Ditch expensive local graphic designers. Design, configure, and output ready-to-print identification cards on demand. Each card features an high-security QR badge code that can be scanned for verified cloud dossiers.',
    category: 'operations',
    icon: 'Contact',
    benefits: [
      'One-click template matching with school themes and shields',
      'Barcodes/QRs integrated natively with our attendance scanners',
      'Includes emergency contacts & allergic reactions info on layout',
      'Ready format exporting for standard cards (CR80 PVC size)'
    ]
  }
];

export const TESTIMONIALS: Testimonial[] = [
  {
    id: 'test-1',
    schoolName: 'Crown Heights Int\'l College',
    type: 'Multi-School Group',
    principalName: 'Dr. (Mrs) Florence Adebayo',
    role: 'Executive Proprietress',
    location: 'Ibadan, Oyo State',
    quote: 'Schooldom completely transformed our 4 school branches. Managing finances and fees collection used to keep me awake, but the integrated payments portal raised our collections rate by 38% in the first term alone. Highly recommended!',
    activeStudents: 2240
  },
  {
    id: 'test-2',
    schoolName: 'Zion Academy',
    type: 'K12',
    principalName: 'Mr. Jude El-Amin',
    role: 'Principal Administrator',
    location: 'Lekki, Lagos State',
    quote: 'Our students absolutely love the Daily Personalized Quizzes and JAMB banks. The Hybrid CBT feature saved us during high-stakes exams when city fiber lines snapped. We didn\'t skip a single minute of testing.',
    activeStudents: 850
  },
  {
    id: 'test-3',
    schoolName: 'Grace Crest Vocational Academy',
    type: 'Vocational',
    principalName: 'Engr. Kenneth Nduka',
    role: 'Director of Studies',
    location: 'Port Harcourt, Rivers State',
    quote: 'As a vocational school catering to flexible schedules, the non-K12 monthly active plan of 200 Naira is exceptionally fair. The attendance SMS alerts keep parents in close sync with student arrivals.',
    activeStudents: 540
  },
  {
    id: 'test-4',
    schoolName: 'Elite Builders Group of Schools',
    type: 'Multi-School Group',
    principalName: 'Hajia Amina Wali',
    role: 'President & Founder',
    location: 'Kaduna, Kaduna State',
    quote: 'Schooldom made managing 12 separate schools across different zones look trivial. Data is beautifully integrated and I can view total termly fee collections from a single live dashboard in Abuja.',
    activeStudents: 6100
  }
];

export const FAQS = [
  {
    question: 'How does the Hybrid CBT offline feature actually work?',
    answer: 'Each school gets a local Schooldom Bridge Server configuration setup (usually running on a direct laptop or inexpensive desktop in your server room). Students connect to this local server via your local Wi-Fi router. Exams run offline directly on this network. Once completed, scores are compiled locally, and when an internet connection is detected, the gateway automatically synchronizes the reports with the secure Schooldom cloud.'
  },
  {
    question: 'Is Schooldom free to use for teachers, principals, and admins?',
    answer: 'Yes, 100%! Schooldom is completely free to construct, customize, and manage for school owners, directors, principals, bursars, and teachers. You get absolute, unrestricted access to set up classrooms, issue lesson plans, track attendance, print high-security PVC QR ID cards, view finance ledgers, and manage schools. Only student accounts are restricted from logging in until the school pays our very small activation fee per active seat.'
  },
  {
    question: 'How much is the student account activation fee, and are there hidden costs?',
    answer: 'Absolutely zero hidden costs. Data migration is completely free with our white-glove migration tier! To grant student accounts active access to write web CBT assessments, practice JAMB past paper simulators, and log onto the student and parent portal, school owners pay a tiny activation fee of just ₦500 per student per term for K-12 schools, or ₦200 per student per month for vocational/continuing education. All administrative features remain 100% free!'
  },
  {
    question: 'What is the distinction between K12 and Non-K12 student activation plans?',
    answer: 'K12 schools operate seasonally, so student activation is flatly ₦500 per active student per term. Non-K12 schools (such as high-flex vocational camps, tertiary training centers, or adult computer programs) operate on rolling monthly slots, so student activation is just ₦200 per active student per month. Both plans open complete parental and student tracking dashboard portals!'
  },
  {
    question: 'Can I onboard multiple campuses? How are Group of Schools handled?',
    answer: 'Yes! Schooldom excels at administering groups of schools. We provide a single master dashboard console where directors can see fee receipts, audit books, evaluate teachers, and check exam performance across dozens of separate school branches, while teachers and principals only see indicators specific to their local branch.'
  },
  {
    question: 'Can parents log on and pay fees directly?',
    answer: 'Yes! Schooldom includes a secure Parent Portal and WhatsApp gateway. Parents receive dynamic payments cards links to their phones. They can pay instantly via cards, Mobile Money, bank transfer, or USSD code. The school balance ledger records the credit instantly, auto-generates a receipt, and notifies the bursar.'
  }
];
