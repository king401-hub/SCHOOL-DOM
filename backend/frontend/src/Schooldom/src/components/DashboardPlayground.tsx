import React, { useState, useEffect } from 'react';
import { 
  Building2, Users, Receipt, Award, PlayCircle, Clock, BookOpen, 
  CheckCircle, Plus, Sparkles, Send, Shield, RefreshCw, 
  Search, Check, Trash2, Printer, QrCode, CreditCard, ChevronRight, UserCheck, School,
  FileText, Calendar, ClipboardList, Briefcase, Landmark, Box, BedDouble, AlertCircle, DollarSign, ArrowUpRight
} from 'lucide-react';

interface StudentData {
  id: string;
  name: string;
  class: string;
  caScore: number;
  examScore: number;
  attendance: string;
}

const MOBILE_MODULES = [
  { icon: Building2, title: 'Analytics Overview', description: 'Live dashboard of attendance, fees, and academic performance.' },
  { icon: BookOpen, title: 'Hybrid CBT Simulation', description: 'Run exams online or fully offline with local sync.' },
  { icon: Receipt, title: 'Bursar Ledger & Pay', description: 'Collect fees, generate receipts, and split payments automatically.' },
  { icon: Briefcase, title: 'HR & Staff Onboarding', description: 'Manage payroll, leave requests, and staff records.' },
  { icon: ClipboardList, title: 'Teacher Lesson & Parents', description: 'Plan lessons, track progress, and message parents.' },
  { icon: Box, title: 'Assets, Hostel & Stock', description: 'Track inventory, hostel beds, and school assets.' },
  { icon: Calendar, title: 'Activities Calendar', description: "Plan and share the full term's academic calendar." },
  { icon: Award, title: 'Automated Report Sheets', description: 'Generate WAEC-style report cards automatically.' },
  { icon: QrCode, title: 'Secure ID Badge Factory', description: 'Print QR-secured student and staff ID cards.' },
];

interface DashboardPlaygroundProps {
  onOpenOnboarding?: () => void;
}

export default function DashboardPlayground({ onOpenOnboarding }: DashboardPlaygroundProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'cbt' | 'finance' | 'reports' | 'id-cards' | 'hr-payroll' | 'teacher-planner' | 'physical-ops' | 'calendar-activities'>('overview');

  const [clientSchoolName, setClientSchoolName] = useState(() => {
    return localStorage.getItem('schooldom_onboarding_school_name') || 'ROYAL CREST ACADEMY';
  });

  // --- HR / Payroll State ---
  const [staffList, setStaffList] = useState([
    { id: 'ST-001', name: 'Mrs. Funke Adebayo', role: 'Physics Dept Head', salary: 180000, bank: 'Zenith Bank', account: '2042849104', status: 'ACTIVE' },
    { id: 'ST-002', name: 'Mr. Chidi Obi', role: 'Mathematics Instructor', salary: 155000, bank: 'Access Bank', account: '0039201494', status: 'ACTIVE' },
    { id: 'ST-003', name: 'Mrs. Sarah Alao', role: 'Chemistry Lab Specialist', salary: 145000, bank: 'GTBank', account: '0129485012', status: 'ACTIVE' }
  ]);
  const [newStaffName, setNewStaffName] = useState('');
  const [newStaffRole, setNewStaffRole] = useState('Assistant Subject Teacher');
  const [newStaffSalary, setNewStaffSalary] = useState(120000);
  const [generatedOfferLetter, setGeneratedOfferLetter] = useState<any>(null);

  // Leave & Advance requests
  const [leaveRequests, setLeaveRequests] = useState([
    { id: 'LV-102', staffName: 'Mr. Chidi Obi', type: 'Compassionate Study Use', duration: '5 Academic Days', date: 'Next Monday', status: 'PENDING' },
    { id: 'LV-101', staffName: 'Mrs. Sarah Alao', type: 'Maternity Relief Leave', duration: '3 Months', date: 'Sept - Nov', status: 'APPROVED' }
  ]);
  const [newLeaveType, setNewLeaveType] = useState('Casual Sick Leave');
  const [newLeaveDuration, setNewLeaveDuration] = useState('3 Days');

  const [advanceRequests, setAdvanceRequests] = useState([
    { id: 'AD-304', staffName: 'Mrs. Funke Adebayo', amount: 50000, reason: 'Mid-term Medical Urgent Check', status: 'PENDING' },
    { id: 'AD-303', staffName: 'Mr. Chidi Obi', amount: 35000, reason: 'Commute Logistics Repair', status: 'APPROVED' }
  ]);
  const [newAdvanceAmount, setNewAdvanceAmount] = useState(25000);
  const [newAdvanceReason, setNewAdvanceReason] = useState('');

  // Student Admission Letter state
  const [newStudentName, setNewStudentName] = useState('');
  const [newStudentClass, setNewStudentClass] = useState('SS1-A Rubies');
  const [newStudentGender, setNewStudentGender] = useState<'Male' | 'Female'>('Male');
  const [onboardedStudentLetter, setOnboardedStudentLetter] = useState<any>(null);

  // --- Teacher Lesson Planner Checklist ----
  const [lessonPlans, setLessonPlans] = useState([
    { id: 1, subject: 'Mathematics (SS3)', topic: 'Quadratic Equations & Complex Roots', status: 'Completed', progress: 100, checklist: [
      { id: 'chk-1-1', label: 'Draft scheme of work & upload resources', checked: true },
      { id: 'chk-1-2', label: 'Assign first CA mini-quiz', checked: true },
      { id: 'chk-1-3', label: 'Coordinate weekend offline CBT exam', checked: true }
    ], week: 'Week 2' },
    { id: 2, subject: 'Physics (SS3)', topic: 'Electromagnetism & Dynamo Vectors', status: 'In Progress', progress: 66, checklist: [
      { id: 'chk-2-1', label: 'Demonstrate magnetic loops in the physics lab', checked: true },
      { id: 'chk-2-2', label: 'Release lesson materials to parent portal', checked: true },
      { id: 'chk-2-3', label: 'Evaluate virtual CBT diagnostic tests', checked: false }
    ], week: 'Week 3' },
    { id: 3, subject: 'Chemistry (SS2)', topic: 'Periodic Table and Ionic Bonds', status: 'Planned', progress: 0, checklist: [
      { id: 'chk-3-1', label: 'Compile slide summaries of Noble Gases', checked: false },
      { id: 'chk-3-2', label: 'Outline CA test questions on covalent bonding', checked: false },
      { id: 'chk-3-3', label: 'Print revision past papers for WAEC alignment', checked: false }
    ], week: 'Week 4' }
  ]);
  const [newPlanSubject, setNewPlanSubject] = useState('Mathematics (SS3)');
  const [newPlanTopic, setNewPlanTopic] = useState('');
  const [newPlanWeek, setNewPlanWeek] = useState('Week 4');

  // --- Physical Ops State ---
  const [inventoryList, setInventoryList] = useState([
    { id: 'INV-101', itemName: 'Dual-Cores CBT Server Box', category: 'Hardware', qty: 12, unit: 'units', status: 'IN SERVICE', min: 2 },
    { id: 'INV-102', itemName: 'High-Sec PVC Blank ID Cards', category: 'Office', qty: 850, unit: 'cards', status: 'IN STOCK', min: 100 },
    { id: 'INV-103', itemName: 'PVC Color Ink Ribbons', category: 'Consumables', qty: 3, unit: 'ribbons', status: 'REORDER NEEDED', min: 5 },
    { id: 'INV-104', itemName: 'Schooldom WAEC Prep Booklets', category: 'Academics', qty: 120, unit: 'copies', status: 'IN STOCK', min: 25 },
    { id: 'INV-105', itemName: 'Hostel Foam Mattresses', category: 'Hostel Assets', qty: 8, unit: 'pieces', status: 'CRITICAL LOW', min: 15 }
  ]);
  const [newInventoryName, setNewInventoryName] = useState('');
  const [newInventoryQty, setNewInventoryQty] = useState(10);
  const [newInventoryMin, setNewInventoryMin] = useState(5);
  const [newInventoryCategory, setNewInventoryCategory] = useState('Office');

  const [hostelList, setHostelList] = useState([
    { id: 'HOST-01', name: 'Moremi Girls Residence Hall', warden: 'Mrs. Comfort Alabi', rooms: 20, capacity: 160, enrolled: 142, gender: 'Female' },
    { id: 'HOST-02', name: 'Murtala Mohammed Boys Hall', warden: 'Mr. Gabriel Okoro', rooms: 24, capacity: 192, enrolled: 185, gender: 'Male' },
    { id: 'HOST-03', name: 'University Trust Hostel (A)', warden: 'Alhaji Yusuf Danjuma', rooms: 15, capacity: 120, enrolled: 98, gender: 'Male' }
  ]);
  const [newHostelName, setNewHostelName] = useState('');
  const [newHostelWarden, setNewHostelWarden] = useState('');
  const [newHostelCapacity, setNewHostelCapacity] = useState(100);
  const [newHostelGender, setNewHostelGender] = useState('Male');

  const [expenses, setExpenses] = useState([
    { id: 'EXP-801', item: '350 Litres Diesel for Mock CBT Generator', category: 'Energy/Utility', amount: 285000, date: 'Today, 09:00 AM' },
    { id: 'EXP-802', item: 'White-glove data server migration hosting', category: 'Technology', amount: 0, date: 'Free Tier Co-managed' },
    { id: 'EXP-803', item: 'PVC Blank Card Pack 1000 Box Restock', category: 'Material', amount: 84000, date: 'Yesterday' },
    { id: 'EXP-804', item: 'WAEC Examination Board Revision Seals', category: 'Registrar Fees', amount: 45000, date: '3 Days Ago' }
  ]);
  const [newExpenseItem, setNewExpenseItem] = useState('');
  const [newExpenseCategory, setNewExpenseCategory] = useState('Utility');
  const [newExpenseAmount, setNewExpenseAmount] = useState(50000);

  // --- School Activities Calendar ---
  const [calendarMonth, setCalendarMonth] = useState('June 2026');
  const [academicEvents, setAcademicEvents] = useState([
    { id: 'EV-01', title: 'Mid-term Unified CBT Mock Prep', date: '2026-06-15', duration: '3 Days', type: 'academic', desc: 'Pre-examinations checkups for all terminal students.' },
    { id: 'EV-02', title: 'PVC ID Card Bulk Photo Operations', date: '2026-06-18', duration: '1 Day', type: 'admin', desc: 'Secure biometric imaging capture for new JS1 and SS1 students' },
    { id: 'EV-03', title: 'School Hostel Parent Townhall', date: '2026-06-20', duration: '1 Day', type: 'social', desc: 'Virtual session reviewing boarding security checks and fees rules' },
    { id: 'EV-04', title: 'Term 3 Examination Board CBT Runs', date: '2026-06-25', duration: '5 Days', type: 'exam', desc: 'Main local server offline examinations. Standard WAEC layout.' },
    { id: 'EV-05', title: 'Hostel Inventory Sanitation Inspection', date: '2016-06-29', duration: '1 Day', type: 'maintenance', desc: 'Complete health audit on food storage and room capacity' }
  ]);
  const [newEventTitle, setNewEventTitle] = useState('');
  const [newEventDate, setNewEventDate] = useState('2026-06-15');
  const [newEventType, setNewEventType] = useState('academic');
  const [newEventDesc, setNewEventDesc] = useState('');

  // --- CBT State ---
  const [selectedSubject, setSelectedSubject] = useState<'Maths' | 'Physics' | 'English'>('Maths');
  const [currentAnswers, setCurrentAnswers] = useState<{ [key: number]: string }>({});
  const [cbtCompleted, setCbtCompleted] = useState(false);
  const [scoreFeedback, setScoreFeedback] = useState({ score: 0, total: 3, percentage: 0 });

  const cbtQuestions = {
    Maths: [
      { id: 1, q: "Solve for x if log₁₀(x) = 3.", a: "1000", options: ["30", "100", "1000", "300"], hint: "10 raised to the power of 3." },
      { id: 2, q: "Find the sum of the first 20 terms of the sequence 3, 7, 11, 15...", a: "820", options: ["680", "740", "820", "900"], hint: "Use arithmetic progression: S_n = n/2 * (2a + (n-1)d)" },
      { id: 3, q: "A dice is rolled once. What is the probability of obtaining a prime number?", a: "1/2", options: ["1/6", "1/3", "1/2", "2/3"], hint: "Prime numbers on a dice are 2, 3, and 5." }
    ],
    Physics: [
      { id: 1, q: "A car accelerates uniformly from rest at 4 m/s². Calculate the distance traveled in 5 seconds.", a: "50m", options: ["10m", "20m", "50m", "100m"], hint: "Use formula: S = ut + 0.5 * a * t²" },
      { id: 2, q: "Which of the following describes the relationship between pressure, temperature and volume for an ideal gas?", a: "PV/T = Constant", options: ["P/VT = Constant", "PV/T = Constant", "PT/V = Constant", "PVT = Constant"], hint: "Standard general gas combination equation." },
      { id: 3, q: "An object is placed 15cm in front of a concave mirror of focal length 10cm. Find the image distance.", a: "30cm", options: ["10cm", "20cm", "30cm", "45cm"], hint: "Use mirror formula: 1/f = 1/u + 1/v" }
    ],
    English: [
      { id: 1, q: "Identify the antonym of the word 'Eminent'.", a: "Obscure", options: ["Famous", "Obscure", "Outstanding", "Aesthetic"], hint: "Eminent means highly prominent or distinguished." },
      { id: 2, q: "Choose the option that best completes: If I ______ known, I wouldn't have gone.", a: "had", options: ["would", "had", "have", "should"], hint: "Standard third conditional expression structure." },
      { id: 3, q: "The principal congratulated Chinedu ______ his outstanding WAEC results.", a: "on", options: ["for", "on", "at", "about"], hint: "Congratulate is idiomatic with the preposition 'on'." }
    ]
  };

  const handleSelectAnswer = (questionId: number, option: string) => {
    setCurrentAnswers({ ...currentAnswers, [questionId]: option });
  };

  const handleSubmitCbt = () => {
    const questions = cbtQuestions[selectedSubject];
    let correct = 0;
    questions.forEach((q) => {
      if (currentAnswers[q.id] === q.a) {
        correct++;
      }
    });
    setScoreFeedback({
      score: correct,
      total: questions.length,
      percentage: Math.round((correct / questions.length) * 100)
    });
    setCbtCompleted(true);
  };

  const handleResetCbt = () => {
    setCurrentAnswers({});
    setCbtCompleted(false);
  };

  // --- Finance State ---
  const [balanceLedger, setBalanceLedger] = useState([
    { id: 'TX-4091', schoolName: '', paymentFor: 'Tuition - Chinedu Okafor (SS3-A Gold)', amount: '₦75,000', date: 'Today, 10:14 AM', status: 'PAID' },
    { id: 'TX-4090', schoolName: '', paymentFor: 'Tuition - Fatima Abubakar (SS3-A Gold)', amount: '₦200,000', date: 'Today, 08:30 AM', status: 'PAID' },
    { id: 'TX-4089', schoolName: '', paymentFor: 'Tuition - Ayomide Alao (SS1-B Ruby)', amount: '₦35,000', date: 'Yesterday', status: 'PAID' },
    { id: 'TX-4088', schoolName: '', paymentFor: 'Tuition - Blessing Effiong (JS2 Bronze)', amount: '₦42,500', date: '2 days ago', status: 'PAID' }
  ]);
  const [totalIncome, setTotalIncome] = useState(352500);
  const [isSimulatingPayment, setIsSimulatingPayment] = useState(false);
  const [notificationMsg, setNotificationMsg] = useState<string | null>(null);

  // --- Partner Loan Credit Hub State ---
  const [loanAmount, setLoanAmount] = useState<number>(1500000);
  const [loanPurpose, setLoanPurpose] = useState<string>('cbt-expansion');
  const [monthlyRevenue, setMonthlyRevenue] = useState<number>(2000000);
  const [hasCollateral, setHasCollateral] = useState<boolean>(true);
  const [loanPrequalified, setLoanPrequalified] = useState<'IDLE' | 'APPROVED' | 'REJECTED' | 'CHECKING'>('IDLE');
  const [creditResultAmount, setCreditResultAmount] = useState<number>(0);
  const [creditRepaymentMonths, setCreditRepaymentMonths] = useState<number>(12);
  const [creditPartner, setCreditPartner] = useState<string>('EdFin Microfinance Bank');
  const [checkingStep, setCheckingStep] = useState<string>('');

  const handleRunLoanPrequalification = () => {
    if (loanAmount <= 0 || monthlyRevenue <= 0) return;
    setLoanPrequalified('CHECKING');
    setCheckingStep('Scanning active school profile density...');

    setTimeout(() => {
      setCheckingStep('Analyzing CA grade sheets & syllabus index...');

      setTimeout(() => {
        setCheckingStep('Verifying parent invoice settlement frequency...');

        setTimeout(() => {
          if (monthlyRevenue < 250000) {
            setLoanPrequalified('REJECTED');
          } else {
            // formula: can get up to 2.5x of monthly revenue, capped by requested amount
            const factor = hasCollateral ? 2.5 : 1.75;
            const possibleAmount = Math.round(monthlyRevenue * factor);
            const approvedCap = Math.min(loanAmount, possibleAmount);
            // round to nearest thousand
            setCreditResultAmount(Math.round(approvedCap / 1000) * 1000);

            // set tenor based on purpose
            if (loanPurpose === 'solar-power') {
              setCreditRepaymentMonths(18);
              setCreditPartner('Sterling Bank (Renewable Division)');
            } else if (loanPurpose === 'cbt-expansion' || loanPurpose === 'hostel-upgrade') {
              setCreditRepaymentMonths(12);
              setCreditPartner('EdFin Microfinance Bank');
            } else {
              setCreditRepaymentMonths(6);
              setCreditPartner('Schooldom Liquidity Co-op');
            }

            setLoanPrequalified('APPROVED');
          }
        }, 500);
      }, 500);
    }, 500);
  };

  const simulateParentPaymentAndSync = () => {
    setIsSimulatingPayment(true);
    setTimeout(() => {
      const studentsArray = Object.values(studentsList) as StudentData[];
      const randomStudent = studentsArray[Math.floor(Math.random() * studentsArray.length)];
      const schoolTx = clientSchoolName;
      const txNum = Math.floor(1000 + Math.random() * 9000);
      const amount = Math.floor(15 + Math.random() * 35) * 1000; // e.g., ₦15,000 to ₦50,000
      
      const newTx = {
        id: `TX-${txNum}`,
        schoolName: schoolTx,
        paymentFor: `Tuition - ${randomStudent.name} (${randomStudent.class})`,
        amount: `₦${amount.toLocaleString()}`,
        date: 'Just Now',
        status: 'PAID'
      };

      setBalanceLedger([newTx, ...balanceLedger]);
      setTotalIncome(prev => prev + amount);
      setIsSimulatingPayment(false);
      
      setNotificationMsg(`🔔 WhatsApp fee alert dispatched to parent of ${randomStudent.name}. Invoice successfully paid & synced to administrative ledger!`);
      setTimeout(() => setNotificationMsg(null), 5500);
    }, 1400);
  };

  // --- Reports State ---
  const [selectedStudent, setSelectedStudent] = useState<string>('stu-1');
  const [studentsList, setStudentsList] = useState<{ [key: string]: StudentData }>({
    'stu-1': { id: 'stu-1', name: 'Chinedu Okafor', class: 'SS3-A Gold', caScore: 28, examScore: 61, attendance: '96%' },
    'stu-2': { id: 'stu-2', name: 'Fatima Abubakar', class: 'SS3-A Gold', caScore: 29, examScore: 68, attendance: '98%' },
    'stu-3': { id: 'stu-3', name: 'Ayomide Alao', class: 'SS1-B Ruby', caScore: 24, examScore: 51, attendance: '91%' },
    'stu-4': { id: 'stu-4', name: 'Blessing Effiong', class: 'JS2 Bronze', caScore: 22, examScore: 42, attendance: '88%' }
  });

  const handleScoreChange = (type: 'ca' | 'exam', val: number) => {
    const freshVal = Math.min(Math.max(0, val), type === 'ca' ? 30 : 70);
    setStudentsList({
      ...studentsList,
      [selectedStudent]: {
        ...studentsList[selectedStudent],
        [type === 'ca' ? 'caScore' : 'examScore']: freshVal
      }
    });
  };

  const activeStudent = studentsList[selectedStudent];
  const finalTotal = activeStudent.caScore + activeStudent.examScore;
  
  const computeWestGrade = (score: number) => {
    if (score >= 75) return { grade: 'A1', desc: 'Excellent', color: 'text-emerald-600 bg-emerald-50 border-emerald-200' };
    if (score >= 70) return { grade: 'B2', desc: 'Very Good', color: 'text-emerald-500 bg-emerald-50 border-emerald-100' };
    if (score >= 65) return { grade: 'B3', desc: 'Good', color: 'text-blue-500 bg-blue-50 border-blue-100' };
    if (score >= 60) return { grade: 'C4', desc: 'Credit', color: 'text-blue-500 bg-blue-50 border-blue-100' };
    if (score >= 55) return { grade: 'C5', desc: 'Credit', color: 'text-indigo-400 bg-indigo-50/50' };
    if (score >= 50) return { grade: 'C6', desc: 'Credit', color: 'text-indigo-600 bg-indigo-50 border-indigo-100' };
    if (score >= 45) return { grade: 'D7', desc: 'Pass', color: 'text-amber-500 bg-amber-50 border-amber-100' };
    if (score >= 40) return { grade: 'E8', desc: 'Pass', color: 'text-amber-600 bg-amber-50 border-amber-200' };
    return { grade: 'F9', desc: 'Fail', color: 'text-rose-500 bg-rose-50 border-rose-200' };
  };
  const activeGradeObj = computeWestGrade(finalTotal);

  // --- ID Card State ---
  const [idRole, setIdRole] = useState<'Student' | 'Teacher' | 'Administrator'>('Student');
  const [idCardColor, setIdCardColor] = useState<'indigo' | 'slate' | 'emerald'>('indigo');
  const [idName, setIdName] = useState('Chinedu Okafor');
  const [idSchoolName, setIdSchoolName] = useState(() => {
    return localStorage.getItem('schooldom_onboarding_school_name') || 'ROYAL CREST ACADEMY';
  });
  const [idDepartment, setIdDepartment] = useState('Science Engineering');
  const [idCode, setIdCode] = useState('SD-31084');
  const [idDownloaded, setIdDownloaded] = useState(false);

  useEffect(() => {
    const handleSchoolNameSync = () => {
      const stored = localStorage.getItem('schooldom_onboarding_school_name');
      if (stored) {
        setIdSchoolName(stored);
        setClientSchoolName(stored);
      }
    };
    window.addEventListener('schooldom_school_name_changed', handleSchoolNameSync);
    window.addEventListener('storage', handleSchoolNameSync);
    return () => {
      window.removeEventListener('schooldom_school_name_changed', handleSchoolNameSync);
      window.removeEventListener('storage', handleSchoolNameSync);
    };
  }, []);

  const triggerMockDownload = () => {
    setIdDownloaded(true);
    setTimeout(() => setIdDownloaded(false), 3000);
  };

  return (
    <section
      id="demo-center"
      className="py-20 bg-gray-50 dark:bg-slate-900 border-y border-gray-100/70 dark:border-slate-800 transition-colors duration-300"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Section Headings */}
        <div className="text-center max-w-3xl mx-auto mb-12">
          <span className="text-xs font-bold uppercase tracking-widest text-brand-600 dark:text-brand-400 bg-brand-50 dark:bg-brand-950/40 px-3 py-1 rounded-full border border-brand-200/50 dark:border-brand-900/50">
            Interactive Test Drive
          </span>
          <h2 className="font-display font-bold text-3xl sm:text-4xl text-brand-950 dark:text-white mt-4 tracking-tight">
            Explore the Digital Solution Sandbox
          </h2>
          <p className="text-gray-600 dark:text-slate-400 mt-3 text-base">
            Click through the mock administration panels below to experience why hundreds of schools have digitized their operations.
          </p>
        </div>

        {/* Dynamic State alerts */}
        {notificationMsg && (
          <div className="max-w-5xl mx-auto mb-5 bg-teal-brand-50 border border-teal-brand-500/20 text-teal-brand-600 p-3.5 rounded-2xl flex items-center gap-2.5 shadow-sm text-sm font-medium animate-in fade-in slide-in-from-top-3 duration-300">
            <UserCheck className="h-5 w-5 text-teal-brand-500 shrink-0" />
            <span>{notificationMsg}</span>
          </div>
        )}

        {/* Mobile module showcase — the interactive sandbox below is a dense,
            desktop-only admin mockup (tables, sliders, multi-panel forms) that
            doesn't work as a cramped mobile layout, so phones get a simple,
            readable list of the same modules instead. */}
        <div className="md:hidden max-w-lg mx-auto space-y-3">
          {MOBILE_MODULES.map((mod) => {
            const Icon = mod.icon;
            return (
              <div
                key={mod.title}
                className="flex items-center gap-3.5 p-4 bg-white dark:bg-slate-800 rounded-2xl border border-gray-200 dark:border-slate-700 shadow-sm text-left"
              >
                <div className="h-10 w-10 rounded-xl bg-brand-50 dark:bg-brand-950/40 text-brand-600 dark:text-brand-400 flex items-center justify-center shrink-0">
                  <Icon className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="font-display font-bold text-sm text-brand-950 dark:text-white">{mod.title}</p>
                  <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5 leading-relaxed">{mod.description}</p>
                </div>
              </div>
            );
          })}
          <button
            id="btn-mobile-sandbox-onboard"
            onClick={onOpenOnboarding}
            className="w-full inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-2xl text-sm font-bold text-white bg-brand-600 hover:bg-brand-700 active:bg-brand-800 transition-all cursor-pointer shadow-lg shadow-brand-500/20 mt-2"
          >
            Get Started For Free
          </button>
        </div>

        {/* Sandbox Window Frame — desktop only. Always renders as a light
            "product screenshot" regardless of site theme, since its dozens of
            inner panels are styled as a fixed light-mode dashboard mockup,
            not a theme-aware section. */}
        <div className="hidden md:flex max-w-6xl mx-auto bg-white text-slate-800 rounded-3xl overflow-hidden shadow-xl border border-gray-200 md:flex-row h-[650px]">

          {/* Inner Sidebar Controls */}
          <div className="w-full md:w-64 bg-slate-900 text-white flex flex-col justify-between shrink-0 overflow-y-auto border-r border-slate-800">
            <div>
              {/* Profile Title Header */}
              <div className="p-5 border-b border-slate-800 flex items-center gap-2 sticky top-0 bg-slate-900 z-10">
                <div className="h-7.5 w-7.5 rounded-lg bg-teal-brand-500 flex items-center justify-center text-white shrink-0 font-display font-extrabold text-xs">SD</div>
                <div>
                  <h4 className="text-xs font-semibold tracking-wider uppercase text-slate-400">Sandbox School</h4>
                  <p className="font-mono text-[9px] text-teal-brand-500">Live Simulation Server</p>
                </div>
              </div>

              {/* Toolbar List */}
              <div className="p-3 space-y-1">
                <button
                  id="tab-btn-overview"
                  onClick={() => setActiveTab('overview')}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-all text-left cursor-pointer ${
                    activeTab === 'overview'
                      ? 'bg-brand-600 text-white shadow-sm'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <Building2 className="h-4 w-4" />
                  Analytics Overview
                </button>
                <button
                  id="tab-btn-cbt"
                  onClick={() => setActiveTab('cbt')}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-all text-left cursor-pointer ${
                    activeTab === 'cbt'
                      ? 'bg-brand-600 text-white shadow-sm'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <BookOpen className="h-4 w-4" />
                  Hybrid CBT Simulation
                </button>
                <button
                  id="tab-btn-finance"
                  onClick={() => setActiveTab('finance')}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-all text-left cursor-pointer ${
                    activeTab === 'finance'
                      ? 'bg-brand-600 text-white shadow-sm'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <Receipt className="h-4 w-4" />
                  Bursar Ledger & Pay
                </button>
                <button
                  id="tab-btn-hr-payroll"
                  onClick={() => setActiveTab('hr-payroll')}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-all text-left cursor-pointer ${
                    activeTab === 'hr-payroll'
                      ? 'bg-brand-600 text-white shadow-sm'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <Briefcase className="h-4 w-4" />
                  HR &amp; Staff Onboarding
                </button>
                <button
                  id="tab-btn-teacher-planner"
                  onClick={() => setActiveTab('teacher-planner')}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-all text-left cursor-pointer ${
                    activeTab === 'teacher-planner'
                      ? 'bg-brand-600 text-white shadow-sm'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <ClipboardList className="h-4 w-4" />
                  Teacher Lesson &amp; Parents
                </button>
                <button
                  id="tab-btn-physical-ops"
                  onClick={() => setActiveTab('physical-ops')}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-all text-left cursor-pointer ${
                    activeTab === 'physical-ops'
                      ? 'bg-brand-600 text-white shadow-sm'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <Box className="h-4 w-4" />
                  Assets, Hostel &amp; Stock
                </button>
                <button
                  id="tab-btn-calendar-activities"
                  onClick={() => setActiveTab('calendar-activities')}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-all text-left cursor-pointer ${
                    activeTab === 'calendar-activities'
                      ? 'bg-brand-600 text-white shadow-sm'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <Calendar className="h-4 w-4" />
                  Activities Calendar
                </button>
                <button
                  id="tab-btn-reports"
                  onClick={() => setActiveTab('reports')}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-all text-left cursor-pointer ${
                    activeTab === 'reports'
                      ? 'bg-brand-600 text-white shadow-sm'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <Award className="h-4 w-4" />
                  Automated Report Sheets
                </button>
                <button
                  id="tab-btn-id-cards"
                  onClick={() => setActiveTab('id-cards')}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-all text-left cursor-pointer ${
                    activeTab === 'id-cards'
                      ? 'bg-brand-600 text-white shadow-sm'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <QrCode className="h-4 w-4" />
                  Secure ID Badge Factory
                </button>
              </div>
            </div>

            {/* Platform status indicator */}
            <div className="p-4 border-t border-slate-800 bg-slate-950/40 text-left">
              <div className="flex items-center gap-1.5 mb-1">
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="text-[10px] uppercase font-mono tracking-wider font-semibold text-slate-300">ONLINE CLOUD SYNCED</span>
              </div>
              <p className="text-[10px] text-gray-500 font-medium">Free white-glove migration tier applies dynamically.</p>
            </div>
          </div>

          {/* Interactive Core Display */}
          <div className="flex-1 bg-white p-6 overflow-y-auto">
            
            {/* 1. ANALYTICS OVERVIEW WINDOW */}
            {activeTab === 'overview' && (
              <div className="space-y-6 animate-in fade-in duration-300 text-left">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-gray-100 pb-4">
                  <div>
                    <h3 className="font-display font-bold text-lg text-brand-950">Administrative Intelligence Console</h3>
                    <p className="text-xs text-gray-400 mt-0.5">Summary of digitized campuses under single login control</p>
                  </div>
                  <span className="text-xs bg-slate-100 px-3 py-1 rounded-full font-semibold text-slate-600 font-mono">TERM 3 AUDIT (LIVE)</span>
                </div>

                {/* Dashboard micro-widgets */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="p-4 border border-gray-100 rounded-2xl bg-slate-50">
                    <div className="flex items-center justify-between">
                      <Users className="h-5 w-5 text-brand-600" />
                      <span className="text-[10px] font-bold text-emerald-500 font-mono">+12% Since Wk 1</span>
                    </div>
                    <p className="text-2xl font-display font-extrabold text-brand-950 mt-1.5">3,485</p>
                    <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mt-0.5">Active Students</p>
                  </div>

                  <div className="p-4 border border-gray-100 rounded-2xl bg-slate-50">
                    <div className="flex items-center justify-between">
                      <Receipt className="h-5 w-5 text-teal-brand-500" />
                      <span className="text-[10px] font-semibold text-brand-600 bg-brand-50 px-1 py-0.5 rounded">94% Target</span>
                    </div>
                    <p className="text-2xl font-display font-extrabold text-brand-950 mt-1.5">₦{totalIncome.toLocaleString()}</p>
                    <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mt-0.5">Fees Collected</p>
                  </div>

                  <div className="p-4 border border-gray-100 rounded-2xl bg-slate-50">
                    <div className="flex items-center justify-between">
                      <UserCheck className="h-5 w-5 text-emerald-500" />
                      <span className="text-[10px] font-bold text-green-500 bg-emerald-50 px-1 py-0.5 rounded">Stable</span>
                    </div>
                    <p className="text-2xl font-display font-extrabold text-brand-950 mt-1.5">97.4%</p>
                    <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mt-0.5">Teacher Attendance</p>
                  </div>

                  <div className="p-4 border border-gray-100 rounded-2xl bg-slate-50">
                    <div className="flex items-center justify-between">
                      <Award className="h-5 w-5 text-indigo-500" />
                      <span className="text-[10px] font-semibold text-emerald-600 font-mono">+8.4% YoY</span>
                    </div>
                    <p className="text-2xl font-display font-extrabold text-brand-950 mt-1.5">88.5%</p>
                    <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mt-0.5">CBT Passing Rate</p>
                  </div>
                </div>

                {/* Simulated Custom Line/Bar Chart (using simple responsive SVG elements) */}
                <div className="border border-gray-100 rounded-2xl p-5 bg-white">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-gray-400">Termly Cashflow Realization Ledger</h4>
                      <p className="text-xs font-semibold text-brand-950 mt-0.5">Total Revenue Inflows by Academic Session</p>
                    </div>
                    <div className="flex gap-4 text-xs font-medium text-gray-600">
                      <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-brand-600 inline-block"/> K12 Termly</span>
                      <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-teal-brand-500 inline-block"/> Non-K12 Monthly</span>
                    </div>
                  </div>

                  <div className="relative h-44">
                    {/* SVG Chart with gridlines */}
                    <svg className="w-full h-full" viewBox="0 0 500 150" preserveAspectRatio="none">
                      {/* Grid Lines */}
                      <line x1="0" y1="30" x2="500" y2="30" stroke="#f1f5f9" strokeWidth="1" />
                      <line x1="0" y1="75" x2="500" y2="75" stroke="#f1f5f9" strokeWidth="1" />
                      <line x1="0" y1="120" x2="500" y2="120" stroke="#f1f5f9" strokeWidth="1" />
                      
                      {/* Smooth Area Path under Chart Line (Coordinates mapped dynamically) */}
                      <path 
                        d="M0,150 L50,110 L150,120 L250,70 L350,55 L450,25 L500,20 L500,150 Z" 
                        fill="url(#chart-gradient)" 
                        opacity="0.1"
                      />
                      
                      {/* Curved Stroke Line */}
                      <path 
                        d="M0,110 Q50,110 150,120 T250,70 T350,55 T450,25 T500,20" 
                        fill="none" 
                        stroke="var(--color-brand-600)" 
                        strokeWidth="3.5"
                        strokeLinecap="round"
                      />

                      {/* Accent Second Line (e.g. Non-K12) */}
                      <path 
                        d="M0,135 Q70,120 180,95 T300,85 T420,60 T500,50" 
                        fill="none" 
                        stroke="var(--color-teal-brand-500)" 
                        strokeWidth="2.5"
                        strokeDasharray="4 2"
                      />

                      {/* Tooltip pointer nodes */}
                      <circle cx="250" cy="70" r="5" fill="var(--color-brand-600)" stroke="white" strokeWidth="1.5" />
                      <circle cx="450" cy="25" r="5" fill="var(--color-brand-600)" stroke="white" strokeWidth="1.5" />

                      <defs>
                        <linearGradient id="chart-gradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="var(--color-brand-600)" />
                          <stop offset="100%" stopColor="white" />
                        </linearGradient>
                      </defs>
                    </svg>
                    
                    {/* Floating annotated popovers for high interactivity */}
                    <div className="absolute top-[35%] left-[50%] bg-slate-900 text-white rounded-lg px-2.5 py-1 text-[9px] font-semibold shadow-md pointer-events-none transform -translate-x-1/2">
                      Mid Term: ₦240.5M
                    </div>
                    <div className="absolute top-[8%] left-[84%] bg-slate-900 text-white rounded-lg px-2.5 py-1 text-[9px] font-semibold shadow-md pointer-events-none transform -translate-x-1/2">
                      Term Final: ₦{totalIncome.toLocaleString()}
                    </div>
                  </div>

                  <div className="flex justify-between font-mono text-[9px] text-gray-400 mt-2 font-medium">
                    <span>WEEK 1 - ADMISSIONS</span>
                    <span>WEEK 4 - MIDTERM TEST</span>
                    <span>WEEK 8 - CBT FINALS</span>
                    <span>WEEK 12 - GRADUATION PORTAL</span>
                  </div>
                </div>

                {/* Live Audit Log Stream */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="border border-gray-100 rounded-xl p-4">
                    <h5 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-2.5">System Operations Feed</h5>
                    <div className="space-y-2 text-xs">
                      <div className="flex items-start gap-2 p-1.5 rounded-lg hover:bg-gray-50">
                        <span className="p-1 rounded-md bg-emerald-50 text-emerald-600 font-bold shrink-0 text-[10px]">CBT</span>
                        <div>
                          <p className="font-semibold text-brand-900">Student CBT Score Sync Completed</p>
                          <p className="text-[10px] text-gray-400">Class SS3-A • Physics Exam offline packet integrated</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-2 p-1.5 rounded-lg hover:bg-gray-50">
                        <span className="p-1 rounded-md bg-brand-50 text-brand-600 font-bold shrink-0 text-[10px]">PAY</span>
                        <div>
                          <p className="font-semibold text-brand-900">₦120k Unified Parent payout receipt</p>
                          <p className="text-[10px] text-gray-400">Bursar Ledger synced with Flutterwave channel</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="border border-gray-100 rounded-xl p-4">
                    <h5 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-2.5">Daily Attendance Status</h5>
                    <div className="flex items-center gap-4">
                      {/* Circular Gauge */}
                      <div className="relative h-20 w-20 shrink-0">
                        <svg className="w-full h-full" viewBox="0 0 36 36">
                          <path
                            className="text-gray-100"
                            strokeWidth="3.5"
                            stroke="currentColor"
                            fill="none"
                            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                          />
                          <path
                            className="text-teal-brand-500"
                            strokeWidth="3.5"
                            strokeDasharray="96, 100"
                            strokeLinecap="round"
                            stroke="currentColor"
                            fill="none"
                            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                          />
                        </svg>
                        <div className="absolute inset-0 flex flex-col items-center justify-center">
                          <span className="font-display font-bold text-sm text-brand-950">96.8%</span>
                          <span className="text-[7px] text-gray-400 uppercase tracking-widest font-bold">In-class</span>
                        </div>
                      </div>
                      <div className="text-xs text-gray-600 space-y-1">
                        <p className="font-semibold text-brand-950">Biometric Attendance Active</p>
                        <p>Teachers log: <span className="text-emerald-600 font-bold">48 Present</span> / 0 Absent</p>
                        <p>Total Class Student Logs: <span className="text-emerald-600 font-medium">3,373 Logged</span></p>
                        <p className="text-[10px] text-gray-400 italic">Parents automatically updated via SMS alerts.</p>
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            )}

            {/* 2. HYBRID CBT SIMULATOR WINDOW */}
            {activeTab === 'cbt' && (
              <div className="space-y-4 animate-in fade-in duration-300 text-left">
                <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                  <div>
                    <h3 className="font-display font-bold text-lg text-brand-950">Hybrid CBT Assessment Engine</h3>
                    <p className="text-xs text-gray-400">Offline-sync enabled candidate testing application</p>
                  </div>
                  <div className="flex gap-1.5 bg-gray-100 p-0.5 rounded-lg text-xs font-semibold">
                    <button
                      id="cbt-sub-maths"
                      onClick={() => { setSelectedSubject('Maths'); handleResetCbt(); }}
                      className={`px-3 py-1 rounded-md transition-all ${selectedSubject === 'Maths' ? 'bg-white text-brand-950 shadow-xs' : 'text-gray-500'}`}
                    >
                      Mathematics
                    </button>
                    <button
                      id="cbt-sub-physics"
                      onClick={() => { setSelectedSubject('Physics'); handleResetCbt(); }}
                      className={`px-3 py-1 rounded-md transition-all ${selectedSubject === 'Physics' ? 'bg-white text-brand-950 shadow-xs' : 'text-gray-500'}`}
                    >
                      Physics
                    </button>
                    <button
                      id="cbt-sub-english"
                      onClick={() => { setSelectedSubject('English'); handleResetCbt(); }}
                      className={`px-3 py-1 rounded-md transition-all ${selectedSubject === 'English' ? 'bg-white text-brand-950 shadow-xs' : 'text-gray-500'}`}
                    >
                      English
                    </button>
                  </div>
                </div>

                {!cbtCompleted ? (
                  <div className="space-y-4">
                    {/* Mock exam details header bar */}
                    <div className="flex justify-between items-center text-xs bg-slate-900 text-white px-4 py-2.5 rounded-xl font-mono">
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-teal-brand-500 animate-pulse" />
                        <span>TIME REMAINING: 42m 14s</span>
                      </div>
                      <div className="text-slate-400">
                        SUBJECT: <span className="text-white font-bold">{selectedSubject.toUpperCase()}</span>
                      </div>
                    </div>

                    {/* Question List */}
                    <div className="space-y-3 max-h-[290px] overflow-y-auto pr-1">
                      {cbtQuestions[selectedSubject].map((question, qIdx) => (
                        <div key={question.id} className="p-4 border border-gray-100 rounded-xl bg-white hover:border-gray-200 shadow-xs">
                          <p className="text-xs font-bold text-brand-600 mb-1">Question {qIdx + 1} of 3</p>
                          <p className="text-sm font-semibold text-brand-950 mb-3">{question.q}</p>
                          
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            {question.options.map((opt) => {
                              const uniqueKey = `${question.id}-${opt}`;
                              const isSelected = currentAnswers[question.id] === opt;
                              return (
                                <button
                                  key={uniqueKey}
                                  id={`opt-${question.id}-${opt.replace(/\s+/g, '')}`}
                                  onClick={() => handleSelectAnswer(question.id, opt)}
                                  className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-semibold text-left transition-all border ${
                                    isSelected
                                      ? 'bg-brand-50 border-brand-500 text-brand-950 shadow-xs'
                                      : 'bg-slate-50 border-gray-200/60 hover:bg-slate-100 text-gray-700'
                                  }`}
                                >
                                  <span className={`h-4.5 w-4.5 rounded-full flex items-center justify-center text-[9px] font-bold border ${isSelected ? 'bg-brand-600 border-brand-700 text-white' : 'bg-white border-gray-300'}`}>
                                    {isSelected ? '✓' : ''}
                                  </span>
                                  {opt}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>

                    <button
                      id="btn-submit-cbt"
                      onClick={handleSubmitCbt}
                      disabled={Object.keys(currentAnswers).length < 2}
                      className="w-full text-center py-3 rounded-xl font-bold bg-slate-900 border border-slate-950 text-white hover:bg-slate-800 disabled:opacity-50 disabled:pointer-events-none cursor-pointer"
                    >
                      Submit Exam Paper
                    </button>
                  </div>
                ) : (
                  /* CBT Graded Response Card */
                  <div className="p-6 border border-emerald-100 rounded-2xl bg-emerald-50/50 text-center space-y-4 animate-in zoom-in-95 duration-200">
                    <div className="h-12 w-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto text-xl font-bold">✓</div>
                    <div>
                      <h4 className="font-display font-extrabold text-xl text-brand-950">Exams Synced Successfully!</h4>
                      <p className="text-xs text-gray-500 mt-1">Schooldom offline engine computed raw score sheets immediately.</p>
                    </div>

                    <div className="max-w-xs mx-auto bg-white rounded-xl p-4 border border-emerald-200/60 shadow-xs">
                      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Candidate Performance Summary</p>
                      <p className="text-3xl font-display font-extrabold text-brand-900 mt-2">{scoreFeedback.score} / {scoreFeedback.total}</p>
                      <p className="text-xs font-bold text-emerald-600">{scoreFeedback.percentage}% Correct Sheets</p>
                    </div>

                    <div className="flex gap-3 max-w-sm mx-auto">
                      <button
                        id="cbt-retry"
                        onClick={handleResetCbt}
                        className="flex-1 py-2 rounded-lg text-xs font-bold border border-gray-200 text-gray-700 bg-white hover:bg-gray-50 cursor-pointer"
                      >
                        Try Another Subject
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 3. FINANCE & FEES LEDGER WINDOW */}
            {activeTab === 'finance' && (
              <div className="space-y-4 animate-in fade-in duration-300 text-left">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-gray-100 pb-3">
                  <div>
                    <h3 className="font-display font-bold text-lg text-brand-950">School Fees Bursar Desk</h3>
                    <p className="text-xs text-gray-400">Automate payment links, print receipts and track group balances</p>
                  </div>
                  <button
                    id="btn-simulate-payment"
                    onClick={simulateParentPaymentAndSync}
                    disabled={isSimulatingPayment}
                    className="inline-flex items-center gap-1.5 px-4.5 py-2 rounded-xl text-xs font-bold text-white bg-teal-brand-500 hover:bg-teal-brand-600 hover:scale-[1.01] active:scale-100 transition-all shadow-sm shadow-teal-500/10 cursor-pointer"
                  >
                    {isSimulatingPayment ? (
                      <>
                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        Processing Parent Handshake...
                      </>
                    ) : (
                      <>
                        <CreditCard className="h-3.5 w-3.5" />
                        Simulate Parent Payment
                      </>
                    )}
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="p-3 border border-gray-100 rounded-xl bg-slate-50">
                    <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Gross Terms Target</p>
                    <p className="text-xl font-display font-bold text-brand-950 mt-1">₦350,000</p>
                  </div>
                  <div className="p-3 border border-gray-100 rounded-xl bg-slate-50">
                    <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Payments Collected</p>
                    <p className="text-xl font-display font-bold text-emerald-600 mt-1">₦{totalIncome.toLocaleString()}</p>
                  </div>
                  <div className="p-3 border border-gray-100 rounded-xl bg-slate-50">
                    <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Unresolved Arrears</p>
                    <p className="text-xl font-display font-bold text-amber-600 mt-1">₦42,500</p>
                  </div>
                </div>

                {/* 2-column Layout: Simulated Transaction Ledger AND Financial Credit Partner Prequalification Hub */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 pt-1">
                  
                  {/* Left Column: Live Transactions Registry Table (7 cols) */}
                  <div className="lg:col-span-7 space-y-3">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-gray-400">Live Transactions Registry</h4>
                    <div className="border border-gray-100 rounded-lg overflow-hidden text-xs bg-white">
                      <table className="w-full text-left font-sans">
                        <thead className="bg-slate-50 text-slate-500 font-bold border-b border-gray-100">
                          <tr>
                            <th className="p-2.5">Tx ID</th>
                            <th className="p-2.5">School Campus / Parent</th>
                            <th className="p-2.5">Allocation Description</th>
                            <th className="p-2.5 text-right">Amount</th>
                            <th className="p-2.5 text-right">Cleared?</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {balanceLedger.map((tx) => (
                            <tr key={tx.id} className="hover:bg-slate-50/50 transition-colors">
                              <td className="p-2.5 font-mono text-[10px] font-semibold text-gray-500">{tx.id}</td>
                              <td className="p-2.5 font-semibold text-brand-950 max-w-[150px] truncate">{tx.schoolName || clientSchoolName}</td>
                              <td className="p-2.5 font-normal text-gray-500">{tx.paymentFor}</td>
                              <td className="p-2.5 font-sans font-bold text-right text-brand-950">{tx.amount}</td>
                              <td className="p-2.5 text-right">
                                <span className="inline-block px-1.8 py-0.5 rounded text-[9px] font-bold bg-emerald-50 text-emerald-600 border border-emerald-100">
                                  {tx.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Right Column: Financial Partners Prequalification Platform (5 cols) */}
                  <div className="lg:col-span-5 space-y-3">
                    <div className="border border-brand-200/80 bg-slate-50 rounded-2xl p-4.5 space-y-3.5 relative overflow-hidden text-slate-800 text-xs shadow-xs">
                      <div className="absolute top-0 right-0 py-0.8 px-2 bg-brand-600/10 text-brand-850 text-[8.5px] font-bold font-mono rounded-bl uppercase">
                        Partnership Desk
                      </div>

                      <div className="border-b border-gray-250 pb-2">
                        <h4 className="font-display font-bold text-brand-950 text-xs uppercase tracking-wide flex items-center gap-1.5">
                          <Landmark className="h-4 w-4 text-brand-600 shrink-0" />
                          Partner Loan Prequalification
                        </h4>
                        <p className="text-[10px] text-gray-400 mt-0.5">Check provisional school upgrade credit with registered partner MFBs &amp; banks.</p>
                      </div>

                      {loanPrequalified === 'IDLE' && (
                        <div className="space-y-3 font-semibold text-[11px] text-slate-700">
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="block text-[9.5px] font-semibold text-slate-500 mb-1">Desired Capital Size (₦):</label>
                              <input
                                type="number"
                                value={loanAmount}
                                onChange={(e) => setLoanAmount(Math.max(0, parseInt(e.target.value) || 0))}
                                className="w-full border border-gray-200 rounded-lg p-2 font-mono font-bold bg-white focus:ring-1 focus:ring-brand-500/20"
                              />
                            </div>
                            <div>
                              <label className="block text-[9.5px] font-semibold text-slate-500 mb-1">Termly School Revenue (₦):</label>
                              <input
                                type="number"
                                value={monthlyRevenue}
                                onChange={(e) => setMonthlyRevenue(Math.max(0, parseInt(e.target.value) || 0))}
                                className="w-full border border-gray-200 rounded-lg p-2 font-mono font-bold bg-white focus:ring-1 focus:ring-brand-500/20"
                              />
                            </div>
                          </div>

                          <div>
                            <label className="block text-[9.5px] font-semibold text-slate-500 mb-1">Upgrade Capital Purpose:</label>
                            <select
                              value={loanPurpose}
                              onChange={(e) => setLoanPurpose(e.target.value)}
                              className="w-full border border-gray-200 rounded-lg p-2 bg-white"
                            >
                              <option value="cbt-expansion">Hybrid Local CBT Lab Setup</option>
                              <option value="solar-power">Solar Clean Power Inverters (Sterling)</option>
                              <option value="hostel-upgrade">Boarding Hostel Dormitory Bunks</option>
                              <option value="desks-school">Classroom Desks &amp; Whiteboards</option>
                              <option value="payroll-liquidity">Faculty Payroll Buffer Liquidity</option>
                            </select>
                          </div>

                          <label className="flex items-center gap-1.5 p-2 bg-white border border-gray-150 rounded-lg cursor-pointer">
                            <input
                              type="checkbox"
                              checked={hasCollateral}
                              onChange={(e) => setHasCollateral(e.target.checked)}
                              className="h-3.5 w-3.5 rounded text-brand-600 accent-brand-600"
                            />
                            <span className="text-[10px] leading-tight text-gray-500 font-semibold">Authorized state/CAC registration documents are available.</span>
                          </label>

                          <button
                            onClick={handleRunLoanPrequalification}
                            className="w-full py-2 bg-brand-600 hover:bg-brand-700 active:scale-[0.99] text-white font-bold rounded-xl transition-all cursor-pointer flex items-center justify-center gap-1.5"
                          >
                            <Sparkles className="h-3.5 w-3.5" />
                            Assess Provisional Loan Prequalification
                          </button>
                        </div>
                      )}

                      {loanPrequalified === 'CHECKING' && (
                        <div className="py-8 flex flex-col items-center justify-center text-center space-y-4">
                          <RefreshCw className="h-8 w-8 text-brand-650 animate-spin" />
                          <div className="space-y-1">
                            <p className="font-bold text-slate-900 text-xs">Assessing Portfolio Underwriting...</p>
                            <p className="text-[10.5px] text-gray-400 italic font-mono">{checkingStep}</p>
                          </div>
                        </div>
                      )}

                      {loanPrequalified === 'APPROVED' && (
                        <div className="space-y-3 animate-in zoom-in-95 duration-200 text-left">
                          <div className="p-3 bg-emerald-50 border border-emerald-150 rounded-xl space-y-1">
                            <span className="text-[9px] font-bold text-emerald-800 bg-emerald-100 border border-emerald-200 px-2 py-0.5 rounded-full uppercase">
                              PASSED PREQUALIFICATION SCAN
                            </span>
                            <p className="text-slate-600 text-[11px] leading-relaxed pt-1.5">
                              Our partner, <strong className="text-slate-950">{creditPartner}</strong>, is ready to provision credit facilities up to:
                            </p>
                            <p className="text-base font-mono font-black text-rose-600 pt-0.5">₦{creditResultAmount.toLocaleString()}</p>
                            <div className="text-[10px] text-slate-500 grid grid-cols-2 gap-2 pt-1 font-semibold">
                              <div>Interest Rate: <span className="font-mono text-emerald-700">3.5% Flat</span></div>
                              <div>Tenor: <span className="font-mono text-emerald-700">{creditRepaymentMonths} Months</span></div>
                            </div>
                          </div>

                          <div className="p-2.5 bg-amber-50 border border-amber-150 rounded-xl text-[10px] text-amber-800 font-semibold leading-normal">
                            ⚠️ terms and conditions apply. This prequalification is subject to school verification &amp; credit council assessment.
                          </div>

                          <div className="flex gap-2 text-[10px]">
                            <button
                              onClick={() => {
                                alert(`CREDIT HANDSHAKE DEMO SUCCESS:\nAn automatic draft application for ₦${creditResultAmount.toLocaleString()} has been queued under legal references for ${creditPartner}. Direct bank coordination initiated!`);
                                setLoanPrequalified('IDLE');
                              }}
                              className="flex-1 py-1.8 bg-brand-600 hover:bg-brand-700 text-white font-black rounded-lg text-center cursor-pointer transition-colors"
                            >
                              Initialize Loan Contract
                            </button>
                            <button
                              onClick={() => setLoanPrequalified('IDLE')}
                              className="px-2.5 py-1.8 bg-slate-200 hover:bg-slate-300 text-slate-705 font-bold rounded-lg cursor-pointer"
                            >
                              Recalculate
                            </button>
                          </div>
                        </div>
                      )}

                      {loanPrequalified === 'REJECTED' && (
                        <div className="py-4 space-y-3.5 text-center">
                          <AlertCircle className="h-9 w-9 text-rose-500 mx-auto" />
                          <div className="space-y-1">
                            <p className="font-bold text-slate-900 text-xs">Provisionally Decline Limit</p>
                            <p className="text-[10.5px] text-gray-400 max-w-[210px] mx-auto">Requires a minimum monthly revenue density of ₦250,000 recorded over the digital ledger.</p>
                          </div>
                          <div className="p-2.5 bg-amber-50 border border-amber-150 rounded-xl text-[9.5px] text-amber-800 font-semibold leading-normal text-left">
                            💡 *Tip*: Try adjusting your revenue parameter or onboarding more active students to bypass security hold thresholds. But remember, terms and conditions apply.
                          </div>
                          <button
                            onClick={() => setLoanPrequalified('IDLE')}
                            className="px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-lg text-[10.5px] cursor-pointer"
                          >
                            Adjust Inputs
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                </div>
              </div>
            )}

            {/* 4. AUTOMATED REPORT SHEETS WINDOW */}
            {activeTab === 'reports' && (
              <div className="space-y-4 animate-in fade-in duration-300 text-left">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-gray-100 pb-3">
                  <div>
                    <h3 className="font-display font-bold text-lg text-brand-950">Automated Performance Reports</h3>
                    <p className="text-xs text-gray-400">Continuous Assessment and Examination auto-grade computations</p>
                  </div>
                  
                  {/* Select Student Selector */}
                  <div className="flex items-center gap-1.5 text-xs text-gray-600">
                    <span className="font-semibold text-sky-950">Select Nominee: </span>
                    <select
                      id="select-student-report"
                      value={selectedStudent}
                      onChange={(e) => setSelectedStudent(e.target.value)}
                      className="border border-gray-200 rounded-lg px-2.5 py-1.5 focus:border-brand-500 bg-white font-medium"
                    >
                      {(Object.values(studentsList) as StudentData[]).map((st) => (
                        <option key={st.id} value={st.id}>{st.name} ({st.class})</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Score Controls Modifier */}
                <div className="p-4 bg-brand-50 rounded-2xl border border-brand-100 flex flex-col sm:flex-row items-center justify-between gap-4">
                  <div className="text-xs text-brand-900 font-medium">
                    <span className="font-display font-bold text-brand-950">Interactive Adjuster: </span>
                    Change grades to see performance averages & WAEC classifications translate instantly below!
                  </div>
                  <div className="flex items-center gap-4 text-xs">
                    <div className="flex items-center gap-1.5">
                      <span className="font-semibold text-slate-600">Continuous Assessment (Max 30):</span>
                      <input
                        id="user-input-ca"
                        type="number"
                        min="0"
                        max="30"
                        value={activeStudent.caScore}
                        onChange={(e) => handleScoreChange('ca', parseInt(e.target.value) || 0)}
                        className="w-14 border border-gray-200 rounded-lg bg-white p-1 text-center font-mono font-bold focus:border-brand-500"
                      />
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-semibold text-slate-600">Exam (Max 70):</span>
                      <input
                        id="user-input-exam"
                        type="number"
                        min="0"
                        max="70"
                        value={activeStudent.examScore}
                        onChange={(e) => handleScoreChange('exam', parseInt(e.target.value) || 0)}
                        className="w-14 border border-gray-200 rounded-lg bg-white p-1 text-center font-mono font-bold focus:border-brand-500"
                      />
                    </div>
                  </div>
                </div>

                {/* Sample Display Report Card Sheet layout */}
                <div className="border border-gray-200/80 rounded-2xl p-6 bg-slate-50 relative overflow-hidden max-w-xl mx-auto">
                  {/* Decorative background watermark */}
                  <div className="absolute top-[35%] left-[50%] -translate-x-1/2 -translate-y-1/2 opacity-5 pointer-events-none">
                    <School className="h-44 w-44 text-slate-900" />
                  </div>

                  <div className="text-center pb-4 border-b border-gray-200 relative">
                    <h4 className="font-display font-extrabold text-base tracking-tight text-gray-900 uppercase">{clientSchoolName} PERFORMANCE REPORT</h4>
                    <p className="text-[10px] text-gray-400 font-mono">AUTHORIZED DIGITAL CERTIFICATE OFFICE</p>
                  </div>

                  <div className="grid grid-cols-2 gap-4 py-4 text-[11px] text-gray-600 border-b border-gray-100">
                    <div>
                      <p>STUDENT NAME: <span className="font-bold text-slate-800">{activeStudent.name.toUpperCase()}</span></p>
                      <p className="mt-1">CLASS ASSIGNMENT: <span className="font-bold text-slate-800">{activeStudent.class}</span></p>
                    </div>
                    <div className="text-right">
                      <p>EXAMINATIONS DATE: <span className="font-mono text-slate-800">TERM 3 AUDIT (2026)</span></p>
                      <p className="mt-1">CLASS ATTENDANCE RATE: <span className="font-mono font-bold text-emerald-600">{activeStudent.attendance}</span></p>
                    </div>
                  </div>

                  {/* Grading sheets ledger */}
                  <div className="py-4 space-y-3">
                    <div className="grid grid-cols-4 font-mono text-[10px] text-gray-400 font-bold uppercase pb-1 border-b border-gray-200">
                      <span>SUBJECT DEPT</span>
                      <span className="text-center">CA (30)</span>
                      <span className="text-center">EXAM (70)</span>
                      <span className="text-right">TOTAL (100)</span>
                    </div>

                    <div className="grid grid-cols-4 font-normal text-xs text-brand-950 py-1 border-b border-gray-100">
                      <span className="font-semibold text-sky-950">Core Mathematics</span>
                      <span className="text-center font-mono">{activeStudent.caScore}</span>
                      <span className="text-center font-mono">{activeStudent.examScore}</span>
                      <span className="text-right font-bold font-mono">{finalTotal} %</span>
                    </div>

                    <div className="grid grid-cols-4 font-normal text-xs text-brand-950 py-1 border-b border-gray-100">
                      <span className="font-semibold text-sky-950 text-sky-950">Core Physics</span>
                      <span className="text-center font-mono">{Math.floor(activeStudent.caScore * 0.9)}</span>
                      <span className="text-center font-mono">{Math.floor(activeStudent.examScore * 0.92)}</span>
                      <span className="text-right font-bold font-mono">{Math.floor(activeStudent.caScore * 0.9) + Math.floor(activeStudent.examScore * 0.92)} %</span>
                    </div>

                    <div className="grid grid-cols-4 font-normal text-xs text-brand-950 py-1 border-b border-gray-100">
                      <span className="font-semibold text-sky-950 text-sky-950">English Literature</span>
                      <span className="text-center font-mono">{Math.floor(activeStudent.caScore * 1.05) > 30 ? 30 : Math.floor(activeStudent.caScore * 1.05)}</span>
                      <span className="text-center font-mono">{Math.floor(activeStudent.examScore * 0.88)}</span>
                      <span className="text-right font-bold font-mono">{(Math.floor(activeStudent.caScore * 1.05) > 30 ? 30 : Math.floor(activeStudent.caScore * 1.05)) + Math.floor(activeStudent.examScore * 0.88)} %</span>
                    </div>
                  </div>

                  {/* Computed Outcome Badge */}
                  <div className="p-3 bg-white rounded-xl border border-gray-100 flex items-center justify-between">
                    <div>
                      <p className="text-[9px] font-bold text-gray-400 uppercase tracking-widest">Weighted WAEC Grade Equivalent</p>
                      <p className="text-xs font-bold text-gray-800 mt-1">Classification Status: <span className="text-brand-600 font-extrabold">{activeGradeObj.desc}</span></p>
                    </div>
                    <div className={`px-4 py-2.5 rounded-xl text-center border font-display font-extrabold text-lg tracking-tight ${activeGradeObj.color}`}>
                      {activeGradeObj.grade}
                    </div>
                  </div>

                </div>
              </div>
            )}

            {/* 5. SECURE ID BADGE FACTORY */}
            {activeTab === 'id-cards' && (
              <div className="space-y-4 animate-in fade-in duration-300 text-left">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-gray-100 pb-3">
                  <div>
                    <h3 className="font-display font-bold text-lg text-brand-950">Secure ID Card Designer</h3>
                    <p className="text-xs text-gray-400">Generate printable badges paired with student dossier QRs in one click</p>
                  </div>
                  <button
                    id="btn-download-pvc"
                    onClick={triggerMockDownload}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-slate-900 border border-slate-950 hover:bg-slate-800 transition-all shadow-xs cursor-pointer"
                  >
                    <Printer className="h-3.5 w-3.5" />
                    {idDownloaded ? "Compiling PVC Grid..." : "Export CR80 PVC Card"}
                  </button>
                </div>

                {/* ID Controller Layout */}
                <div className="flex flex-col md:flex-row gap-6 items-center">
                  
                  {/* Left Parameter Panel */}
                  <div className="flex-1 space-y-3.5 text-xs text-gray-600 w-full">
                    <div>
                      <label htmlFor="input-card-school" className="block font-semibold mb-1 text-sky-950">Institution / School Name:</label>
                      <input
                        id="input-card-school"
                        type="text"
                        value={idSchoolName}
                        onChange={(e) => setIdSchoolName(e.target.value)}
                        className="w-full border border-gray-200 rounded-lg bg-white px-3 py-2 font-medium focus:border-brand-500 text-sky-950"
                        placeholder="e.g. Royal Crest Academy"
                      />
                    </div>
                    <div>
                      <label htmlFor="input-card-name" className="block font-semibold mb-1 text-sky-950">Cardholder Name:</label>
                      <input
                        id="input-card-name"
                        type="text"
                        value={idName}
                        onChange={(e) => setIdName(e.target.value)}
                        className="w-full border border-gray-200 rounded-lg bg-white px-3 py-2 font-medium focus:border-brand-500 text-sky-950"
                      />
                    </div>
                    <div>
                      <label htmlFor="select-card-color" className="block font-semibold mb-1 text-sky-950">Select Template Theme Color:</label>
                      <div className="flex gap-2">
                        <button
                          id="btn-card-color-indigo"
                          onClick={() => setIdCardColor('indigo')}
                          className={`flex-1 py-1.5 rounded-lg border text-center font-medium ${idCardColor === 'indigo' ? 'bg-brand-600 text-white border-brand-700' : 'bg-white border-gray-200 text-gray-700'}`}
                        >
                          Crimson Indigo
                        </button>
                        <button
                          id="btn-card-color-emerald"
                          onClick={() => setIdCardColor('emerald')}
                          className={`flex-1 py-1.5 rounded-lg border text-center font-medium ${idCardColor === 'emerald' ? 'bg-teal-brand-500 text-white border-teal-brand-600' : 'bg-white border-gray-200 text-gray-700'}`}
                        >
                          Smart Emerald
                        </button>
                        <button
                          id="btn-card-color-slate"
                          onClick={() => setIdCardColor('slate')}
                          className={`flex-1 py-1.5 rounded-lg border text-center font-medium ${idCardColor === 'slate' ? 'bg-slate-800 text-white border-slate-900' : 'bg-white border-gray-200 text-gray-700'}`}
                        >
                          Slate Deep
                        </button>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label htmlFor="select-card-role" className="block font-semibold mb-1 text-sky-950">User Segment:</label>
                        <select
                          id="select-card-role"
                          value={idRole}
                          onChange={(e) => setIdRole(e.target.value as any)}
                          className="w-full border border-gray-200 rounded-lg px-2.5 py-2 focus:border-brand-500 bg-white font-medium"
                        >
                          <option value="Student">Student Badge</option>
                          <option value="Teacher">Teacher Badge</option>
                          <option value="Administrator">Administrator</option>
                        </select>
                      </div>
                      <div>
                        <label htmlFor="input-card-dep" className="block font-semibold mb-1 text-sky-950">Department/Class:</label>
                        <input
                          id="input-card-dep"
                          type="text"
                          value={idDepartment}
                          onChange={(e) => setIdDepartment(e.target.value)}
                          className="w-full border border-gray-200 rounded-lg bg-white px-3 py-2 font-medium focus:border-brand-500"
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-1 gap-1">
                      <label htmlFor="input-card-id" className="block font-semibold text-sky-950">Security ID Code:</label>
                      <input
                        id="input-card-id"
                        type="text"
                        value={idCode}
                        onChange={(e) => setIdCode(e.target.value)}
                        className="w-full border border-gray-200 rounded-lg bg-white px-3 py-2 font-mono font-bold text-sky-950 focus:border-brand-500"
                      />
                    </div>
                  </div>

                  {/* Right Dynamic Live Badge Render */}
                  <div className="w-64 shrink-0 p-1">
                    <div className="border border-gray-300 rounded-2xl p-4 bg-slate-50 relative overflow-hidden shadow-md animate-in zoom-in-95 duration-200">
                      
                      {/* Top Branding Section */}
                      <div className={`p-3 -m-4 mb-4 text-white text-center rounded-t-xl flex flex-col items-center justify-center relative ${
                        idCardColor === 'indigo' ? 'bg-brand-600' : idCardColor === 'emerald' ? 'bg-teal-brand-500' : 'bg-slate-800'
                      }`}>
                        <p className="font-display font-extrabold text-[11px] uppercase tracking-wide">{idSchoolName ? idSchoolName.toUpperCase() : "ROYAL CREST ACADEMY"}</p>
                        <p className="text-[7.5px] font-mono opacity-85 uppercase tracking-wider">SECURE DIGITAL IDENTIFICATION</p>
                      </div>

                      {/* Photo Holder & QR side-by-side */}
                      <div className="flex flex-col items-center text-center space-y-3 pt-2">
                        <div className="relative">
                          <div className={`h-22 w-22 rounded-full flex items-center justify-center p-1 border-2 ${
                            idCardColor === 'indigo' ? 'border-brand-200' : idCardColor === 'emerald' ? 'border-teal-brand-200' : 'border-slate-300'
                          }`}>
                            {/* Simple fallback avatar */}
                            <div className="h-full w-full rounded-full bg-slate-200 flex items-center justify-center text-slate-500 font-display font-bold text-base">
                              {idName.split(' ').map(n=>n[0]).join('') || '?'}
                            </div>
                          </div>
                          {/* Floating Role Tab */}
                          <span className={`absolute bottom-0 left-1/2 transform -translate-x-1/2 px-2.5 py-0.5 rounded-full text-[7.5px] font-extrabold text-white border shadow-xs ${
                            idRole === 'Student' ? 'bg-emerald-600 border-emerald-500' : idRole === 'Teacher' ? 'bg-brand-500 border-brand-400' : 'bg-slate-900 border-slate-700'
                          }`}>
                            {idRole.toUpperCase()}
                          </span>
                        </div>

                        {/* Text values */}
                        <div className="space-y-1 w-full text-center">
                          <h4 className="font-display font-extrabold text-sm text-brand-950 truncate px-1">{idName}</h4>
                          <p className="text-[10px] text-gray-500 font-semibold">{idDepartment}</p>
                          <p className="font-mono text-[9px] font-bold text-slate-400">ID NO: {idCode}</p>
                        </div>

                        {/* Live scanner barcode/QR placeholder */}
                        <div className="w-full flex items-center justify-between border-t border-gray-100 pt-3 text-[8.5px] font-semibold text-gray-400">
                          <div className="text-left">
                            <p className="text-[8px] uppercase tracking-wider">ISSUE YEAR</p>
                            <p className="font-mono font-bold text-brand-950 mt-0.5">2026</p>
                          </div>
                          <div className="p-1 rounded bg-white shadow-xs border border-gray-100 flex items-center justify-center">
                            <QrCode className={`h-7 w-7 ${
                              idCardColor === 'indigo' ? 'text-brand-600' : idCardColor === 'emerald' ? 'text-teal-brand-500' : 'text-slate-800'
                            }`} />
                          </div>
                          <div className="text-right">
                            <p className="text-[8px] uppercase tracking-wider">ACCESS STAT</p>
                            <p className="text-emerald-500 font-bold mt-0.5">ACTIVE</p>
                          </div>
                        </div>
                      </div>

                    </div>
                  </div>

                </div>

                {idDownloaded && (
                  <div className="p-2 border border-emerald-100 text-center animate-pulse rounded-lg bg-emerald-50 text-[10px] font-semibold text-emerald-600 animate-in fade-in duration-200">
                    PVC file generated! Standard layout matches exact printer drivers (CR80/P600/PVC Card specs).
                  </div>
                )}
              </div>
            )}

            {/* 6. HR & STAFF PAYROLL MANAGEMENT PANEL */}
            {activeTab === 'hr-payroll' && (
              <div className="space-y-4 animate-in fade-in duration-300 text-left">
                <div className="border-b border-gray-100 pb-2">
                  <h3 className="font-display font-bold text-lg text-brand-950">Administrative HR &amp; Staff Ledger</h3>
                  <p className="text-xs text-gray-400">Onboard faculty members, auto-generate official offer letters, and manage direct bank payroll payouts</p>
                </div>

                {/* Grid sections splits */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                  {/* Left Onboarding and Requests Controls */}
                  <div className="lg:col-span-5 space-y-4">
                    {/* Onboard form */}
                    <div className="bg-slate-50 border border-gray-200 rounded-2xl p-4 text-xs space-y-3">
                      <h4 className="font-bold text-brand-950 uppercase tracking-wide flex items-center gap-1.5">
                        <UserCheck className="h-4 w-4 text-brand-600" />
                        Onboard New Staff
                      </h4>
                      <div className="space-y-2.5">
                        <div>
                          <label className="block text-[11px] font-semibold text-slate-600 mb-1">Full Representative Name:</label>
                          <input
                            id="input-staff-name"
                            type="text"
                            value={newStaffName}
                            onChange={(e) => setNewStaffName(e.target.value)}
                            placeholder="Mrs. Abigail Olayinka"
                            className="w-full border border-gray-200 rounded-lg bg-white p-2 font-medium"
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="block text-[11px] font-semibold text-slate-600 mb-1">Academic Role:</label>
                            <select
                              id="select-staff-role"
                              value={newStaffRole}
                              onChange={(e) => setNewStaffRole(e.target.value)}
                              className="w-full border border-gray-200 rounded-lg bg-white p-2 font-medium"
                            >
                              <option value="Physics Dept Head">Physics Dept Head</option>
                              <option value="Mathematics Instructor">Mathematics Instructor</option>
                              <option value="Chemistry Lab Specialist">Chemistry Lab Specialist</option>
                              <option value="Literature Coordinator">Literature Coordinator</option>
                              <option value="Junior Registrar Clerk">Junior Registrar Clerk</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-[11px] font-semibold text-slate-600 mb-1">Base Salary (₦):</label>
                            <input
                              id="input-staff-salary"
                              type="number"
                              value={newStaffSalary}
                              onChange={(e) => setNewStaffSalary(parseInt(e.target.value) || 0)}
                              className="w-full border border-gray-200 rounded-lg bg-white p-2 font-medium font-mono"
                            />
                          </div>
                        </div>
                        <button
                          id="btn-onboard-staff"
                          onClick={() => {
                            if (!newStaffName) return;
                            const newId = `ST-00${staffList.length + 1}`;
                            const newRec = {
                              id: newId,
                              name: newStaffName,
                              role: newStaffRole,
                              salary: newStaffSalary,
                              bank: 'Access Bank',
                              account: '09' + Math.floor(10000000 + Math.random() * 90000000),
                              status: 'ACTIVE'
                            };
                            setStaffList([...staffList, newRec]);
                            setGeneratedOfferLetter(newRec);
                            setNewStaffName('');
                          }}
                          className="w-full py-2 bg-brand-600 hover:bg-brand-700 active:scale-[0.99] font-bold text-white rounded-xl transition-all cursor-pointer flex items-center justify-center gap-1.5"
                        >
                          <Plus className="h-3.5 w-3.5" />
                          Onboard &amp; Build Offer Letter
                        </button>
                      </div>
                    </div>

                    {/* Pending Leave and Advance Requests section */}
                    <div className="bg-slate-50 border border-gray-200 rounded-2xl p-4 text-xs space-y-3">
                      <h4 className="font-bold text-brand-950 uppercase tracking-wide flex items-center justify-between">
                        <span>Teacher Leave &amp; Advance Desk</span>
                        <span className="text-[9px] bg-amber-500/10 text-amber-600 px-1.5 py-0.5 rounded font-mono font-bold uppercase">Staff Hub</span>
                      </h4>

                      {/* Request Forms */}
                      <div className="grid grid-cols-2 gap-2 border-b border-gray-200 pb-3">
                        <div className="space-y-1.5">
                          <p className="font-semibold text-slate-500">File Leave Request:</p>
                          <input
                            id="input-leave-type"
                            type="text"
                            placeholder="Study Exam Prep"
                            className="w-full border border-gray-200 rounded bg-white p-1 text-[11px]"
                            value={newLeaveType}
                            onChange={(e) => setNewLeaveType(e.target.value)}
                          />
                          <button
                            id="btn-submit-leave"
                            onClick={() => {
                              if (!newLeaveType) return;
                              setLeaveRequests([
                                ...leaveRequests,
                                {
                                  id: `LV-${Math.floor(100 + Math.random() * 899)}`,
                                  staffName: 'Mrs. Abigail Olayinka',
                                  type: newLeaveType,
                                  duration: '4 Days',
                                  date: 'Next week',
                                  status: 'PENDING'
                                }
                              ]);
                              setNewLeaveType('');
                            }}
                            className="w-full py-1 text-[10px] bg-slate-900 border border-slate-950 hover:bg-slate-800 text-white font-bold rounded-lg cursor-pointer"
                          >
                            Submit Leave
                          </button>
                        </div>

                        <div className="space-y-1.5">
                          <p className="font-semibold text-slate-500">Apply Salary Advance:</p>
                          <input
                            id="input-advance-reason"
                            type="text"
                            placeholder="Home Repair Logistics"
                            className="w-full border border-gray-200 rounded bg-white p-1 text-[11px]"
                            value={newAdvanceReason}
                            onChange={(e) => setNewAdvanceReason(e.target.value)}
                          />
                          <button
                            id="btn-submit-advance"
                            onClick={() => {
                              if (!newAdvanceReason) return;
                              setAdvanceRequests([
                                ...advanceRequests,
                                {
                                  id: `AD-${Math.floor(300 + Math.random() * 899)}`,
                                  staffName: 'Mr. Chidi Obi',
                                  amount: newAdvanceAmount,
                                  reason: newAdvanceReason,
                                  status: 'PENDING'
                                }
                              ]);
                              setNewAdvanceReason('');
                            }}
                            className="w-full py-1 text-[10px] bg-indigo-650 hover:bg-indigo-700 text-white font-bold rounded-lg cursor-pointer"
                          >
                            Claim Advance
                          </button>
                        </div>
                      </div>

                      {/* Pending Lists with actions */}
                      <div className="space-y-2">
                        <p className="font-bold text-slate-600 text-[10px] uppercase">Active Staff Desk Actions:</p>
                        {leaveRequests.filter(l => l.status === 'PENDING').map(leave => (
                          <div key={leave.id} className="p-2 border border-slate-200 rounded-lg bg-white flex justify-between items-center text-[11px]">
                            <div>
                              <p className="font-semibold text-slate-900">{leave.staffName} <span className="font-mono text-[9px] text-gray-400">({leave.id})</span></p>
                              <p className="text-gray-500">{leave.type} • {leave.duration}</p>
                            </div>
                            <button
                              onClick={() => {
                                setLeaveRequests(leaveRequests.map(l => l.id === leave.id ? { ...l, status: 'APPROVED' } : l));
                              }}
                              className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-700 hover:bg-emerald-200 text-[10px] font-extrabold cursor-pointer"
                            >
                              Approve
                            </button>
                          </div>
                        ))}
                        {advanceRequests.filter(a => a.status === 'PENDING').map(adv => (
                          <div key={adv.id} className="p-2 border border-slate-200 rounded-lg bg-white flex justify-between items-center text-[11px]">
                            <div>
                              <p className="font-bold text-slate-900">{adv.staffName}</p>
                              <p className="text-gray-500">Advance: ₦{adv.amount.toLocaleString()} ({adv.reason})</p>
                            </div>
                            <button
                              onClick={() => {
                                setAdvanceRequests(advanceRequests.map(a => a.id === adv.id ? { ...a, status: 'APPROVED' } : a));
                                setExpenses([...expenses, {
                                  id: `EXP-${Math.floor(820 + Math.random() * 70)}`,
                                  item: `Salary Advance Release for ${adv.staffName}`,
                                  category: 'Teacher Advance Holdback',
                                  amount: adv.amount,
                                  date: 'Disbursed Just Now'
                                }]);
                              }}
                              className="px-2 py-0.5 rounded bg-brand-100 text-brand-700 hover:bg-brand-200 text-[10px] font-extrabold cursor-pointer"
                            >
                              Approve &amp; Pay
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Right Faculty list & Offer Letter output */}
                  <div className="lg:col-span-7 space-y-4">
                    {/* Official Offer Letter Generator Outlet */}
                    {generatedOfferLetter && (
                      <div className="border border-brand-250 bg-gradient-to-br from-brand-50 to-white rounded-2xl p-4.5 text-xs text-left relative overflow-hidden shadow-md animate-in zoom-in-95 duration-200">
                        <div className="absolute top-2 right-2 flex gap-1.5">
                          <button
                            onClick={() => setGeneratedOfferLetter(null)}
                            className="bg-slate-200 hover:bg-slate-300 px-1.5 py-0.5 text-[9px] font-extrabold rounded text-slate-705"
                          >
                            Dismiss Letter
                          </button>
                        </div>
                        <div className="text-center border-b border-brand-200 pb-2 mb-3">
                          <h5 className="font-display font-black text-brand-900 tracking-wider">SCHOOLDOM INTEGRATED HR OFFICE</h5>
                          <p className="text-[8.5px] font-mono uppercase tracking-widest text-slate-500">Employment Board of Principle Credentials</p>
                        </div>
                        <div className="space-y-2 text-slate-700">
                          <p><strong>Ref Code:</strong> SDM/OFFR/2026/{generatedOfferLetter.id}</p>
                          <p>Dear <strong>{generatedOfferLetter.name}</strong>,</p>
                          <p className="leading-relaxed">
                            Following the successful credentials validation of your professional teaching and CBT monitoring competence, we are absolutely pleased to extend to you an official offer to serve as our <strong className="text-brand-900">{generatedOfferLetter.role}</strong>.
                          </p>
                          <div className="p-2.5 bg-brand-50 border border-brand-150 rounded-xl grid grid-cols-2 gap-3 font-semibold text-brand-950">
                            <div>
                              <span className="text-[9.5px] font-semibold text-slate-500 block uppercase">Monthly Emolument</span>
                              ₦{generatedOfferLetter.salary.toLocaleString()} Base Rate
                            </div>
                            <div>
                              <span className="text-[9.5px] font-semibold text-slate-500 block uppercase">Access License Rights</span>
                              100% Free Staff Dashboard Seat
                            </div>
                          </div>
                          <p className="text-[10px] text-gray-400 italic leading-snug">
                            *This contract falls under Schooldom’s co-managed free administrative terms, stating that while administrative operations, attendance cards and markbooks are completely free, student logins are strictly billed directly to the bursariat at our standard TERM rate.
                          </p>
                          <div className="flex justify-between items-center pt-2 text-[10.5px]">
                            <div className="text-center">
                              <p className="font-bold text-gray-800">DR. SOLOMON ADEIFE</p>
                              <p className="text-[8.5px] text-gray-400 uppercase">Board Chairman, Schooldom</p>
                            </div>
                            <div className="border border-brand-500/20 bg-emerald-50 text-emerald-500 px-2.5 py-1 rounded-lg text-center font-bold font-mono tracking-wide text-[8.5px]">
                              SEALED &amp; APPROVED
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Faculty payroll directory */}
                    <div className="bg-white border border-gray-200 rounded-2xl p-4 space-y-3.5">
                      <div className="flex flex-col sm:flex-row items-center justify-between gap-2">
                        <h4 className="font-bold text-gray-900 text-sm flex items-center gap-1">
                          <Landmark className="h-4.5 w-4.5 text-teal-brand-500" />
                          Faculty Employee Roll &amp; Bank Ledger
                        </h4>
                        <button
                          onClick={() => {
                            const tot = staffList.reduce((acc, current) => acc + current.salary, 0);
                            alert(`SCHOOLDOM PAYROLL DISBURSEMENT GATEWAY:\n₦${tot.toLocaleString()} overall payout instructions mapped over CBN-NIP switch to faculty partner accounts. Settlements compiled cleared!`);
                          }}
                          className="px-3 py-1 bg-teal-brand-500 hover:bg-teal-brand-600 text-white text-[11px] font-extrabold rounded-lg flex items-center gap-1 cursor-pointer transition-colors shadow-sm"
                        >
                          <DollarSign className="h-3 w-3" />
                          Release Monthly Payroll (₦)
                        </button>
                      </div>

                      <div className="overflow-x-auto text-[11px]">
                        <table className="w-full text-left">
                          <thead className="bg-slate-50 text-slate-500 font-bold border-b border-gray-100">
                            <tr>
                              <th className="p-2">ID</th>
                              <th className="p-2">Employee Name</th>
                              <th className="p-2">Role/Position</th>
                              <th className="p-2">Base monthly salary</th>
                              <th className="p-2">Deposit Transit account</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100">
                            {staffList.map((st) => (
                              <tr key={st.id} className="hover:bg-slate-50/50">
                                <td className="p-2 font-mono text-gray-400 font-bold">{st.id}</td>
                                <td className="p-2 font-bold text-brand-950">{st.name}</td>
                                <td className="p-2 font-semibold text-gray-600">{st.role}</td>
                                <td className="p-2 font-mono font-bold text-teal-brand-650">₦{st.salary.toLocaleString()}</td>
                                <td className="p-2 font-mono text-[10px] text-gray-500">{st.bank} • {st.account}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 7. TEACHER LESSON PLANNER & PARENT CHECKLIST TRACKER */}
            {activeTab === 'teacher-planner' && (
              <div className="space-y-4 animate-in fade-in duration-300 text-left">
                <div className="border-b border-gray-100 pb-2">
                  <h3 className="font-display font-bold text-lg text-brand-950">Dynamic Class Lesson Planner &amp; Parental Portal</h3>
                  <p className="text-xs text-gray-400">Manage interactive curriculum checklists. Every checked item translates directly to real-time parent tracking streams</p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                  {/* Left Column: Teacher Planner Console */}
                  <div className="lg:col-span-7 space-y-4">
                    <div className="bg-white border border-gray-200 rounded-2xl p-4 space-y-3">
                      <div className="flex justify-between items-center border-b border-gray-100 pb-2">
                        <h4 className="font-bold text-gray-900 text-sm flex items-center gap-1">
                          <ClipboardList className="h-4.5 w-4.5 text-brand-600" />
                          Teacher Syllabus Tracker
                        </h4>
                        <span className="text-[10px] font-bold text-brand-600 bg-brand-50 border border-brand-100 px-2 py-0.5 rounded-full">Syllabus Active</span>
                      </div>

                      {/* Add Scheme of Work */}
                      <div className="grid grid-cols-3 gap-2 bg-slate-50 p-2.5 rounded-xl text-xs">
                        <div className="space-y-1">
                          <label className="text-[9.5px] font-bold text-slate-500">Subject Field:</label>
                          <select
                            id="select-planner-subject"
                            className="w-full p-1.5 border border-gray-200 rounded font-medium bg-white"
                            value={newPlanSubject}
                            onChange={(e) => setNewPlanSubject(e.target.value)}
                          >
                            <option value="Mathematics (SS3)">Mathematics (SS3)</option>
                            <option value="Physics (SS3)">Physics (SS3)</option>
                            <option value="Chemistry (SS2)">Chemistry (SS2)</option>
                            <option value="English Literature">English Literature</option>
                          </select>
                        </div>
                        <div className="space-y-1">
                          <label className="text-[9.5px] font-bold text-slate-500">Weekly Topic:</label>
                          <input
                            id="input-planner-topic"
                            type="text"
                            placeholder="Indices & Calculus"
                            className="w-full p-1.5 border border-gray-200 rounded font-medium bg-white text-brand-950 font-sans"
                            value={newPlanTopic}
                            onChange={(e) => setNewPlanTopic(e.target.value)}
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[9.5px] font-bold text-slate-500">Timeline Scope:</label>
                          <div className="flex gap-1.5">
                            <input
                              id="input-planner-week"
                              type="text"
                              value={newPlanWeek}
                              onChange={(e) => setNewPlanWeek(e.target.value)}
                              className="w-full p-1.5 border border-gray-200 rounded bg-white text-center text-slate-705 font-mono"
                            />
                            <button
                              id="btn-add-planner-topic"
                              onClick={() => {
                                if (!newPlanTopic) return;
                                setLessonPlans([
                                  ...lessonPlans,
                                  {
                                    id: lessonPlans.length + 1,
                                    subject: newPlanSubject,
                                    topic: newPlanTopic,
                                    status: 'Planned',
                                    progress: 0,
                                    week: newPlanWeek,
                                    checklist: [
                                      { id: `chk-${lessonPlans.length + 1}-1`, label: 'Identify learning outcomes & key formulas', checked: false },
                                      { id: `chk-${lessonPlans.length + 1}-2`, label: 'Publish student past exam simulations', checked: false }
                                    ]
                                  }
                                ]);
                                setNewPlanTopic('');
                              }}
                              className="px-2.5 bg-brand-600 hover:bg-brand-700 text-white font-bold rounded cursor-pointer"
                            >
                              Add
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Interactive Schemes list */}
                      <div className="space-y-3.5 text-xs">
                        {lessonPlans.map((lp) => (
                          <div key={lp.id} className="p-3.5 border border-gray-200 rounded-xl space-y-2 hover:border-gray-300">
                            <div className="flex justify-between items-start">
                              <div>
                                <span className="text-[10px] font-mono uppercase bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-bold">{lp.week}</span>
                                <h5 className="font-bold text-brand-950 mt-1">{lp.subject}: <span className="font-semibold text-gray-700">{lp.topic}</span></h5>
                              </div>
                              <div className="text-right">
                                <span className={`inline-block px-1.8 py-0.5 rounded text-[9px] font-mono font-extrabold shadow-sm ${
                                  lp.status === 'Completed' ? 'bg-emerald-100 text-emerald-800' : lp.status === 'In Progress' ? 'bg-sky-100 text-sky-800' : 'bg-amber-100 text-amber-800'
                                }`}>
                                  {lp.status.toUpperCase()}
                                </span>
                                <p className="text-[9.5px] text-gray-400 font-bold mt-0.5">{lp.progress}% Done</p>
                              </div>
                            </div>

                            {/* Live progress percentage bar */}
                            <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                              <div className="bg-emerald-500 h-full transition-all duration-300" style={{ width: `${lp.progress}%` }} />
                            </div>

                            {/* Checks item loops */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 pt-1">
                              {lp.checklist.map((item) => (
                                <label key={item.id} className="flex items-start gap-1.5 p-1.5 rounded bg-slate-50 border border-slate-100 cursor-pointer hover:bg-slate-100/50">
                                  <input
                                    type="checkbox"
                                    checked={item.checked}
                                    className="mt-0.5 h-3.5 w-3.5 rounded text-brand-600 focus:ring-0 accent-brand-600"
                                    onChange={() => {
                                      // Toggle list state, then update progress percentage
                                      const updatedList = lessonPlans.map(plan => {
                                        if (plan.id === lp.id) {
                                          const updatedChecklist = plan.checklist.map(chk => {
                                            if (chk.id === item.id) {
                                              return { ...chk, checked: !chk.checked };
                                            }
                                            return chk;
                                          });
                                          const checkedCount = updatedChecklist.filter(c => c.checked).length;
                                          const nextProg = Math.round((checkedCount / updatedChecklist.length) * 100);
                                          const status = nextProg === 100 ? 'Completed' : nextProg > 0 ? 'In Progress' : 'Planned';
                                          return { ...plan, checklist: updatedChecklist, progress: nextProg, status };
                                        }
                                        return plan;
                                      });
                                      setLessonPlans(updatedList);
                                    }}
                                  />
                                  <span className="text-[10px] leading-tight text-gray-600 font-medium select-none">{item.label}</span>
                                </label>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Parent Portal live view simulator */}
                  <div className="lg:col-span-5 space-y-4">
                    <div className="bg-brand-950/95 text-white border border-brand-850 rounded-2xl p-4.5 space-y-3 relative overflow-hidden shadow-lg">
                      <div className="absolute top-0 right-0 p-1 bg-brand-500/25 text-brand-300 text-[8px] uppercase font-mono font-black rounded-bl tracking-widest">
                        SECURE SYNCED API
                      </div>
                      
                      <div className="border-b border-brand-800/80 pb-2">
                        <span className="inline-block bg-teal-brand-500/15 border border-teal-brand-500/30 text-teal-brand-400 font-mono text-[9px] font-bold px-2 py-0.5 rounded-full mb-1">
                          Parent Dashboard Stream View
                        </span>
                        <h4 className="font-display font-extrabold text-sm text-white">Parent Portal: Academic Activities Monitor</h4>
                        <p className="text-[10.5px] text-slate-400">Linked Student Account: <strong className="text-white">Solomon Adebayo Jnr</strong> (SS3-A)</p>
                      </div>

                      <div className="space-y-3 text-xs">
                        <div className="p-3 bg-brand-900/40 border border-brand-800/60 rounded-xl space-y-2">
                          <p className="text-[10px] text-teal-brand-400 font-bold tracking-wide uppercase">Current Academic Week Milestone Progress:</p>
                          <div className="flex items-center justify-between text-white font-mono font-bold text-sm">
                            <span>Syllabus Covered &amp; Quizzed</span>
                            <span>{Math.round(lessonPlans.reduce((acc, current) => acc + current.progress, 0) / lessonPlans.length)}%</span>
                          </div>
                          <div className="w-full bg-brand-950/90 h-1.8 rounded-full overflow-hidden">
                            <div className="bg-teal-brand-500 h-full transition-all duration-300" style={{ width: `${Math.round(lessonPlans.reduce((acc, current) => acc + current.progress, 0) / lessonPlans.length)}%` }} />
                          </div>
                        </div>

                        {/* List exactly what parent sees */}
                        <div className="space-y-1.5 max-h-[190px] overflow-y-auto pr-1">
                          {lessonPlans.map(plan => (
                            <div key={plan.id} className="p-2 bg-brand-900/25 border border-brand-800/30 rounded-lg text-[11px] space-y-1">
                              <div className="flex justify-between font-semibold">
                                <span className="text-teal-brand-300 truncate">{plan.subject}</span>
                                <span className="text-slate-400 font-mono text-[9px]">{plan.week}</span>
                              </div>
                              <p className="text-slate-300 text-[10px] italic">Checked: {plan.checklist.filter(c => c.checked).map(c => c.label.substring(0,25)+'..').join(', ') || 'Waiting schedule...'}</p>
                              {/* Parent Checklist rendering in real time */}
                              <div className="space-y-1 pt-1 border-t border-brand-800/40">
                                {plan.checklist.map(chk => (
                                  <div key={chk.id} className="flex items-center gap-1.5 text-[9.5px]">
                                    {chk.checked ? (
                                      <CheckCircle className="h-3 w-3 text-teal-brand-400 shrink-0" />
                                    ) : (
                                      <div className="h-3 w-3 rounded-full border border-slate-500 shrink-0" />
                                    )}
                                    <span className={chk.checked ? 'text-slate-200 line-through' : 'text-slate-400'}>{chk.label}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>

                        <div className="p-2 border border-brand-800/40 rounded-lg bg-emerald-500/10 text-center text-[10px] text-teal-brand-300 font-medium">
                          🔔 Connected Phone (+234803***494): Parents receive auto-SMS digests at 4:30 PM on exam metrics and weekly unchecked syllabus items standard.
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 8. PHYSICAL & FISCAL OPERATIONS: ASSETS, HOSTEL, EXPENSES & ADMISSIONS */}
            {activeTab === 'physical-ops' && (
              <div className="space-y-4 animate-in fade-in duration-300 text-left">
                <div className="border-b border-gray-100 pb-2">
                  <h3 className="font-display font-bold text-lg text-brand-950">Campus Operations: Stock, Hostel Halls &amp; Expenses Ledger</h3>
                  <p className="text-xs text-gray-400">Oversee hardware levels, allocate boarding slots, log micro expenses, and compile official student admission letters</p>
                </div>

                {/* Sub tabs style grid layout */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 text-slate-800 text-xs">
                  
                  {/* Left Column: Register forms and Admission Letter template */}
                  <div className="lg:col-span-5 space-y-4">
                    {/* Add to inventory stock Form */}
                    <div className="bg-slate-50 border border-gray-200 rounded-2xl p-4.5 space-y-3">
                      <h4 className="font-bold text-gray-900 uppercase tracking-wider flex items-center gap-1">
                        <Box className="h-4.5 w-4.5 text-indigo-600" />
                        Stock Inventory Register
                      </h4>
                      <div className="space-y-2 text-[11px]">
                        <div>
                          <label className="block text-slate-500 font-semibold mb-1">Item Title / Spec Code:</label>
                          <input
                            id="input-inv-name"
                            type="text"
                            value={newInventoryName}
                            onChange={(e) => setNewInventoryName(e.target.value)}
                            placeholder="e.g. CBT Wi-Fi Router antennas"
                            className="w-full p-2 border border-gray-200 rounded-lg bg-white"
                          />
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <label className="block text-slate-500 font-semibold mb-1">Category:</label>
                            <select
                              id="select-inv-cat"
                              value={newInventoryCategory}
                              onChange={(e) => setNewInventoryCategory(e.target.value)}
                              className="w-full p-1.5 border border-gray-200 rounded-lg bg-white"
                            >
                              <option value="Hardware">Hardware</option>
                              <option value="Office">Office/Paper</option>
                              <option value="Hostel Assets">Hostel Assets</option>
                              <option value="Consumables">Consumables</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-slate-500 font-semibold mb-1">Stock Vol:</label>
                            <input
                              id="input-inv-qty"
                              type="number"
                              value={newInventoryQty}
                              onChange={(e) => setNewInventoryQty(parseInt(e.target.value) || 0)}
                              className="w-full p-1.5 border border-gray-200 rounded-lg bg-white font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-slate-500 font-semibold mb-1">Min Level:</label>
                            <input
                              id="input-inv-min"
                              type="number"
                              value={newInventoryMin}
                              onChange={(e) => setNewInventoryMin(parseInt(e.target.value) || 0)}
                              className="w-full p-1.5 border border-gray-200 rounded-lg bg-white font-mono"
                            />
                          </div>
                        </div>
                        <button
                          id="btn-add-inventory"
                          onClick={() => {
                            if (!newInventoryName) return;
                            setInventoryList([
                              ...inventoryList,
                              {
                                id: `INV-${Math.floor(100 + Math.random() * 899)}`,
                                itemName: newInventoryName,
                                category: newInventoryCategory,
                                qty: newInventoryQty,
                                unit: 'units',
                                status: newInventoryQty < newInventoryMin ? 'CRITICAL LOW' : 'IN STOCK',
                                min: newInventoryMin
                              }
                            ]);
                            setNewInventoryName('');
                          }}
                          className="w-full py-2 bg-indigo-650 hover:bg-indigo-700 text-white font-bold rounded-xl cursor-pointer"
                        >
                          Register Items Stockpile
                        </button>
                      </div>
                    </div>

                    {/* Generate Admission Letter & Bill */}
                    <div className="bg-slate-50 border border-gray-200 rounded-2xl p-4.5 space-y-3">
                      <h4 className="font-bold text-brand-950 uppercase tracking-wider flex items-center gap-1">
                        <FileText className="h-4 w-4 text-brand-600" />
                        Onboard Nominee &amp; Print Admission Offer
                      </h4>
                      <div className="space-y-2 text-[11px]">
                        <div>
                          <label className="block text-slate-500 font-semibold mb-1">Student Complete Name:</label>
                          <input
                            id="input-admission-name"
                            type="text"
                            value={newStudentName}
                            onChange={(e) => setNewStudentName(e.target.value)}
                            placeholder="Adebayo Israel"
                            className="w-full p-2 border border-gray-200 rounded bg-white"
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="block text-slate-500 font-semibold mb-1">Class Assigned:</label>
                            <input
                              id="input-admission-class"
                              type="text"
                              value={newStudentClass}
                              onChange={(e) => setNewStudentClass(e.target.value)}
                              className="w-full p-2 border border-gray-200 rounded bg-white"
                            />
                          </div>
                          <div>
                            <label className="block text-slate-500 font-semibold mb-1">Gender Segment:</label>
                            <select
                              id="select-admission-gender"
                              value={newStudentGender}
                              onChange={(e) => setNewStudentGender(e.target.value as any)}
                              className="w-full p-2 border border-gray-200 rounded bg-white"
                            >
                              <option value="Male">Male Gender</option>
                              <option value="Female">Female Gender</option>
                            </select>
                          </div>
                        </div>
                        <button
                          id="btn-generate-admission"
                          onClick={() => {
                            if (!newStudentName) return;
                            const letObj = {
                              id: `ADM/2026/S-${Math.floor(2500 + Math.random() * 4900)}`,
                              name: newStudentName,
                              targetClass: newStudentClass,
                              gender: newStudentGender,
                              hostelHall: newStudentGender === 'Male' ? 'Murtala Mohammed Boys Hall' : 'Moremi Girls Residence Hall'
                            };
                            setOnboardedStudentLetter(letObj);
                            setNewStudentName('');
                          }}
                          className="w-full py-2 bg-brand-600 hover:bg-brand-700 text-white font-bold rounded-xl cursor-pointer"
                        >
                          Generate Official Admission Credentials
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Display list / Live Generated admission document & hostel registers */}
                  <div className="lg:col-span-7 space-y-4">
                    
                    {/* Official Admission Certificate container */}
                    {onboardedStudentLetter && (
                      <div className="border-2 border-dashed border-brand-500 bg-white rounded-2xl p-5 text-xs text-left relative overflow-hidden shadow-lg animate-in fade-in duration-300">
                        <div className="absolute top-2 right-2">
                          <button
                            onClick={() => setOnboardedStudentLetter(null)}
                            className="p-1 px-2 text-[9px] font-extrabold bg-slate-100 hover:bg-slate-200 rounded"
                          >
                            Close Document
                          </button>
                        </div>
                        
                        <div className="text-center border-b pb-3 mb-4">
                          <School className="h-9 w-9 text-brand-600 mx-auto mb-1.5" />
                          <h4 className="font-display font-black text-brand-950 text-sm">SCHOOLDOM INTEGRATED ACADEMY</h4>
                          <p className="text-[8.5px] font-mono tracking-widest text-slate-400">OFFICIAL OFFER OF PRIMARY/SECONDARY ADMISSION</p>
                        </div>

                        <div className="space-y-3 leading-relaxed text-slate-700 text-[11px]">
                          <div className="flex justify-between font-mono text-[9px] text-gray-500 border-b pb-1.5">
                            <span>Reference: {onboardedStudentLetter.id}</span>
                            <span>Date issued: June 13, 2026</span>
                          </div>
                          
                          <p>
                            We are absolutely pleased to register and extend this offer of Academic Admission to <strong>{onboardedStudentLetter.name.toUpperCase()}</strong> (Category: {onboardedStudentLetter.gender}) to follow our Term 3 school courses inside the Class allocation: <strong className="text-brand-950 font-bold">{onboardedStudentLetter.targetClass}</strong>.
                          </p>

                          <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
                            <p className="font-bold text-gray-900 border-b border-gray-200 pb-1 text-[10px] uppercase">Allocated Boarding Assignation:</p>
                            <p className="flex justify-between">
                              <span className="text-slate-500">Residence Hall Assigned:</span>
                              <span className="font-bold text-slate-800">{onboardedStudentLetter.hostelHall}</span>
                            </p>
                          </div>

                          <div className="p-3 bg-brand-50 border border-brand-100 rounded-xl space-y-1.5 text-[11px] font-semibold text-brand-950">
                            <p className="font-bold text-slate-500 border-b border-brand-200 pb-1 text-[9.5px] uppercase">Linked Termly Billing Invoice (₦):</p>
                            <div className="flex justify-between">
                              <span>Secondary Student Tuition:</span>
                              <span className="font-mono">₦12,500</span>
                            </div>
                            <div className="flex justify-between">
                              <span>High-sec PVC Qr badge Card charge:</span>
                              <span className="font-mono">₦1,500</span>
                            </div>
                            <div className="flex justify-between">
                              <span>Schooldom Student portal Term active license:</span>
                              <span className="font-mono text-teal-brand-650 bg-emerald-500/10 px-1 rounded">₦500 <span className="font-normal font-sans text-[8.5px] text-slate-500">(Admin is free)</span></span>
                            </div>
                            <div className="border-t border-brand-250 pt-1.5 flex justify-between font-bold text-brand-900">
                              <span>Unified Settlement Invoice Total:</span>
                              <span className="font-mono">₦14,500.00</span>
                            </div>
                          </div>
                        </div>

                        <div className="mt-4 pt-3 border-t flex justify-between items-center text-[10px] text-gray-400">
                          <div>
                            <p className="font-bold text-gray-800">OFFICE OF THE REGISTRAR</p>
                            <p className="text-[8px] uppercase">Credentials Division</p>
                          </div>
                          <QrCode className="h-7 w-7 text-brand-600" />
                        </div>
                      </div>
                    )}

                    {/* Inventory and Hostel stats panels */}
                    <div className="bg-white border border-gray-200 rounded-2xl p-4 space-y-4">
                      <div className="flex justify-between items-center border-b pb-2">
                        <h4 className="font-bold text-gray-900 text-sm flex items-center gap-1.5">
                          <Box className="h-4.5 w-4.5 text-brand-600" />
                          Classroom Supplies &amp; CBT Hardware Inventory
                        </h4>
                        <span className="text-[9.5px] text-slate-400 uppercase font-mono font-bold">Physical Asset registry</span>
                      </div>

                      <div className="space-y-2">
                        {inventoryList.map((item) => {
                          const isLow = item.qty < item.min;
                          return (
                            <div key={item.id} className={`flex justify-between items-center p-2.5 rounded-xl border text-[11.5px] ${
                              isLow ? 'bg-rose-50 border-rose-150 text-rose-950' : 'bg-slate-50 border-slate-200/60'
                            }`}>
                              <div>
                                <p className="font-bold text-brand-950">{item.itemName}</p>
                                <p className="text-[9.5px] font-mono text-gray-400 uppercase tracking-wider">{item.category} • Required Min: {item.min} {item.unit}</p>
                              </div>
                              <div className="text-right">
                                <span className={`inline-block px-2 py-0.5 rounded-full text-[9px] font-extrabold ${
                                  isLow ? 'bg-rose-500 text-white animate-pulse' : 'bg-brand-50 text-brand-650'
                                }`}>
                                  {item.qty} {item.unit.toUpperCase()}
                                </span>
                                <p className="text-[9px] text-gray-400 mt-1">{isLow ? '⚠️ REORDER NEEDED' : '✓ HEALTHY'}</p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Hostel residency database */}
                    <div className="bg-white border border-gray-200 rounded-2xl p-4 space-y-4">
                      <div className="flex justify-between items-center border-b pb-2">
                        <h4 className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                          <BedDouble className="h-4.5 w-4.5 text-indigo-650" />
                          Boarding residency Residence Halls
                        </h4>
                        <span className="text-[9.5px] text-slate-400 uppercase font-mono font-bold">Hostel check desk</span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                        {hostelList.map((hostel) => {
                          const occPercent = Math.round((hostel.enrolled / hostel.capacity) * 100);
                          return (
                            <div key={hostel.id} className="p-3 border border-gray-200 rounded-xl space-y-1.5 bg-slate-50/50">
                              <div className="flex justify-between items-start">
                                <div>
                                  <h5 className="font-bold text-brand-950 text-[11.5px]">{hostel.name}</h5>
                                  <p className="text-[10px] text-gray-500">Warden: {hostel.warden}</p>
                                </div>
                                <span className={`inline-block text-[9px] font-bold px-1.5 py-0.5 rounded ${hostel.gender === 'Female' ? 'bg-purple-100 text-purple-700' : 'bg-indigo-100 text-indigo-700'}`}>
                                  {hostel.gender}
                                </span>
                              </div>
                              <div className="w-full bg-slate-200 h-1 rounded-full overflow-hidden">
                                <div className={`h-full ${occPercent > 90 ? 'bg-amber-500' : 'bg-brand-500'}`} style={{ width: `${occPercent}%` }} />
                              </div>
                              <div className="flex justify-between text-[9.5px] text-gray-500">
                                <span>Occupied seats: <strong>{hostel.enrolled} / {hostel.capacity} beds</strong></span>
                                <span className="font-bold">{occPercent}% Full</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Micro expense logs */}
                    <div className="bg-white border border-gray-200 rounded-2xl p-4 space-y-3.5">
                      <div className="border-b pb-2">
                        <h4 className="font-bold text-gray-900 text-sm">Operation Expense Accounting Ledger</h4>
                        <p className="text-[10.5px] text-gray-400">Total operational Termly costs accrued: <strong className="text-slate-800">₦{expenses.reduce((acc,c)=>acc+c.amount,0).toLocaleString()}</strong></p>
                      </div>

                      <table className="w-full text-left text-[11px] border border-gray-100 rounded-xl overflow-hidden">
                        <thead className="bg-slate-50 text-slate-500 font-bold border-b border-gray-100">
                          <tr>
                            <th className="p-2">Item Exp</th>
                            <th className="p-2">Category</th>
                            <th className="p-2 text-right">Debit Charge (₦)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {expenses.map((exp) => (
                            <tr key={exp.id}>
                              <td className="p-2 font-bold text-brand-950">{exp.item}</td>
                              <td className="p-2 font-medium text-slate-400">{exp.category}</td>
                              <td className="p-2 text-right font-mono font-bold text-rose-650">₦{exp.amount.toLocaleString()}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                  </div>

                </div>
              </div>
            )}

            {/* 9. SCHOOL ACTIVITIES CALENDAR PANEL */}
            {activeTab === 'calendar-activities' && (
              <div className="space-y-4 animate-in fade-in duration-300 text-left">
                <div className="border-b border-gray-100 pb-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                  <div>
                    <h3 className="font-display font-bold text-lg text-brand-950">Campus Term Academic Activities Calendar</h3>
                    <p className="text-xs text-gray-400">Schedule critical exam board runs, parent assemblies, mock CBT intervals, and PVC photography slots</p>
                  </div>
                  
                  <span className="bg-brand-50 border border-brand-100 text-brand-650 text-xs px-3.5 py-1.5 rounded-xl font-bold font-mono uppercase">
                    🏠 Term 3: {calendarMonth}
                  </span>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                  {/* Left Column Calendar Scheduler Form */}
                  <div className="lg:col-span-4 space-y-4">
                    <div className="bg-slate-50 border border-gray-200 rounded-2xl p-4 text-xs space-y-3">
                      <h4 className="font-bold text-gray-900 uppercase tracking-wider flex items-center gap-1.5">
                        <Calendar className="h-4 w-4 text-brand-650" />
                        Schedule New Event
                      </h4>
                      
                      <div className="space-y-2.5 text-[11px] text-gray-600">
                        <div>
                          <label className="block font-semibold mb-1 text-slate-500">Event Label / Subject Title:</label>
                          <input
                            id="input-cal-title"
                            type="text"
                            value={newEventTitle}
                            onChange={(e) => setNewEventTitle(e.target.value)}
                            placeholder="Unified CBT Mock Prep Session"
                            className="w-full p-2 border border-gray-200 rounded bg-white text-brand-950 font-sans"
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="block font-semibold mb-1 text-slate-500">Date Node:</label>
                            <input
                              id="input-cal-date"
                              type="date"
                              value={newEventDate}
                              onChange={(e) => setNewEventDate(e.target.value)}
                              className="w-full p-1.5 border border-gray-200 rounded bg-white font-mono text-slate-705"
                            />
                          </div>
                          <div>
                            <label className="block font-semibold mb-1 text-slate-500">Event Category:</label>
                            <select
                              id="select-cal-type"
                              value={newEventType}
                              onChange={(e) => setNewEventType(e.target.value)}
                              className="w-full p-1.5 border border-gray-200 rounded bg-white font-medium"
                            >
                              <option value="academic">Academic Class</option>
                              <option value="exam">Examination Runs</option>
                              <option value="admin">Admin / ID runs</option>
                              <option value="social">Social / Parent Day</option>
                              <option value="maintenance">Sanitation Check</option>
                            </select>
                          </div>
                        </div>
                        <div>
                          <label className="block font-semibold mb-1 text-slate-500">Event Description summary (for Parent app):</label>
                          <textarea
                            id="input-cal-desc"
                            rows={2}
                            value={newEventDesc}
                            onChange={(e) => setNewEventDesc(e.target.value)}
                            placeholder="Syllabus alignment checks review before official exams release..."
                            className="w-full p-2 border border-gray-200 rounded bg-white"
                          />
                        </div>
                        <button
                          id="btn-add-calendar-event"
                          onClick={() => {
                            if (!newEventTitle) return;
                            setAcademicEvents([
                              ...academicEvents,
                              {
                                id: `EV-${academicEvents.length + 1}`,
                                title: newEventTitle,
                                date: newEventDate,
                                duration: '1 Day',
                                type: newEventType,
                                desc: newEventDesc || 'Unified scheduled academic operational node.'
                              }
                            ]);
                            setNewEventTitle('');
                            setNewEventDesc('');
                          }}
                          className="w-full py-2 bg-brand-600 hover:bg-brand-700 text-white font-bold rounded-xl cursor-pointer"
                        >
                          Publish to Core Calendar
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Timeline Event List layout */}
                  <div className="lg:col-span-8 bg-white border border-gray-200 rounded-2xl p-4.5 space-y-4">
                    <h4 className="font-bold text-gray-900 border-b pb-2 text-sm">Timeline Registry: Term sequence</h4>
                    
                    <div className="space-y-3.5 text-xs">
                      {academicEvents.sort((a,b) => a.date.localeCompare(b.date)).map((ev) => (
                        <div key={ev.id} className="p-3.5 hover:bg-slate-50 border border-gray-250/20 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-3 text-left">
                          <div className="flex items-start gap-3">
                            {/* Color Tag Indicator */}
                            <span className={`mt-1 h-3.5 w-3.5 rounded-full shrink-0 border ${
                              ev.type === 'academic' ? 'bg-emerald-500 border-emerald-450' :
                              ev.type === 'exam' ? 'bg-brand-500 border-brand-405' :
                              ev.type === 'admin' ? 'bg-sky-500 border-sky-405' :
                              ev.type === 'social' ? 'bg-purple-500 border-purple-405' :
                              'bg-amber-500 border-amber-405'
                            }`} />
                            
                            <div className="space-y-1">
                              <h5 className="font-bold text-brand-950 text-[12.5px] leading-tight">{ev.title}</h5>
                              <p className="text-gray-500 text-[10.5px] font-sans">{ev.desc}</p>
                              <div className="flex items-center gap-1.5 pt-1 text-[9px] text-slate-400 font-bold uppercase font-mono">
                                <span>SEGMENT: {ev.type.toUpperCase()}</span>
                                <span>•</span>
                                <span>SCOPE: {ev.duration}</span>
                              </div>
                            </div>
                          </div>

                          <div className="text-right self-end md:self-center font-mono text-[11px] font-bold text-gray-400 shrink-0 select-none bg-slate-50 p-2 border border-gray-150 rounded-xl">
                            ⏰ {ev.date}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

          </div>

        </div>

      </div>
    </section>
  );
}
