import React, { useState } from 'react';
import { X, ShieldCheck, CheckCircle2, FileText, Lock, Globe, Server } from 'lucide-react';

interface LegalDocumentsProps {
  isOpen: boolean;
  onClose: () => void;
  defaultTab?: 'terms' | 'privacy';
}

export default function LegalDocuments({ isOpen, onClose, defaultTab = 'terms' }: LegalDocumentsProps) {
  const [activeTab, setActiveTab] = useState<'terms' | 'privacy'>(defaultTab);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-xs text-left">
      <div 
        id="legal-modal-container"
        className="relative w-full max-w-3xl bg-white text-slate-800 rounded-3xl overflow-hidden shadow-2xl border border-slate-100 flex flex-col h-[85vh]"
      >
        {/* Sky-Blue / Mint Ribbon Heading */}
        <div className="bg-slate-900 text-white px-6 py-4.5 flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 bg-brand-500/10 rounded-xl flex items-center justify-center border border-brand-500/20 text-brand-400">
              {activeTab === 'terms' ? <FileText className="h-5 w-5" /> : <Lock className="h-5 w-5" />}
            </div>
            <div>
              <h3 className="font-display font-bold text-base text-slate-100">Schooldom Regulatory & Trust Portal</h3>
              <p className="text-[10px] text-brand-300 font-mono tracking-widest uppercase">
                {activeTab === 'terms' ? 'TERMS & CONDITIONS' : 'PRIVACY POLICY • NDPA COMPLIANT'}
              </p>
            </div>
          </div>
          <button
            id="legal-btn-close"
            onClick={onClose}
            className="p-1.5 hover:bg-slate-800 rounded-lg cursor-pointer transition-colors text-slate-400 hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tab Selection */}
        <div className="flex border-b border-slate-150 bg-slate-50 px-6 gap-2 pt-3">
          <button
            id="tab-btn-terms"
            onClick={() => setActiveTab('terms')}
            className={`px-4 py-2.5 text-xs font-bold transition-all border-b-2 rounded-t-lg flex items-center gap-2 cursor-pointer ${
              activeTab === 'terms'
                ? 'border-brand-500 text-brand-600 bg-white font-black'
                : 'border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-100'
            }`}
          >
            <FileText className="h-4 w-4" />
            Terms &amp; General Conditions
          </button>
          <button
            id="tab-btn-privacy"
            onClick={() => setActiveTab('privacy')}
            className={`px-4 py-2.5 text-xs font-bold transition-all border-b-2 rounded-t-lg flex items-center gap-2 cursor-pointer ${
              activeTab === 'privacy'
                ? 'border-brand-500 text-brand-600 bg-white font-black'
                : 'border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-100'
            }`}
          >
            <Lock className="h-4 w-4" />
            Privacy Policy &amp; NDPA Code
          </button>
        </div>

        {/* Dynamic Legal Copy Panel */}
        <div className="p-6 sm:p-8 overflow-y-auto flex-1 text-slate-600 space-y-6 text-xs leading-relaxed">
          
          {activeTab === 'terms' ? (
            /* TERMS AND CONDITIONS DOCUMENT */
            <div className="space-y-6 animate-in fade-in duration-150">
              <div className="p-4 bg-brand-50 border border-brand-100 rounded-2xl flex items-start gap-3">
                <ShieldCheck className="h-5 w-5 text-brand-500 shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-bold text-brand-900 text-xs uppercase tracking-wider mb-1">Institutional Service Level Agreement (SLA)</h4>
                  <p className="text-brand-800 text-[11px]">
                    This binding agreement governs the deployment, local node setup, and database provisioning of the <strong>Schooldom Academy Enterprise Resource Platform</strong> for registered schools across West Africa.
                  </p>
                </div>
              </div>

              <section className="space-y-2.5">
                <h4 className="font-display font-bold text-slate-900 text-sm">1. Legal Context and Activation</h4>
                <p>
                  By accessing or initiating registration on the Schooldom Platform, physical school proprietors, headteachers, and academic administrators warrant that they possess legal corporate authority to bind their schools to these terms.
                </p>
                <p>
                  Service commences in perpetuity upon onboarding until formally terminated by either party with a ninety (90) day written notice before a new academic term resumes.
                </p>
              </section>

              <section className="space-y-2.5">
                <h4 className="font-display font-bold text-slate-900 text-sm">2. Billing, Fees, and Student Seat Activation</h4>
                <p>
                  Schooldom provides 100% free administration. All school owners, principals, administrative registrars, bursars, and classroom teachers can configure classrooms, register students, track attendance, and build report sheets without charge.
                </p>
                <p>
                  Activation fees apply strictly to student profiles to enable active login access and practice tools. K12 schools pay a standard rate of <strong>₦500 per student per academic term</strong> to unlock student portals, while private training or non-K12 centers pay <strong>₦200 per student per month</strong>. Student logins are restricted until the administrator pays this activation fee.
                </p>
                <p>
                  Financial invoices are auto-compiled on the 4th week of each school term. Late fees accrue after term examination boards resolve, at 5% simple interest per month on the outstanding balance.
                </p>
              </section>

              <section className="space-y-2.5">
                <h4 className="font-display font-bold text-slate-900 text-sm">3. Offline Hybrid CBT Local Nodes SLA</h4>
                <p>
                  For schools choosing the CBT Exam Suite, Schooldom deploys specialized local web server proxies (the offline nodes) to prevent internet reliance during student WAEC/JAMB preparations.
                </p>
                <ul className="list-disc pl-4 space-y-1 text-[11px]">
                  <li>The institution agrees to safeguard local intranet servers against unauthorized hardware tampering.</li>
                  <li>Local synchronizations should occur at least once a term to align offline grade computational cards with secure cloud backup registries.</li>
                </ul>
              </section>

              <section className="space-y-2.5">
                <h4 className="font-display font-bold text-slate-900 text-sm">4. Data Integrity &amp; WAEC/NECO Grade Alignment</h4>
                <p>
                  Academic scores calculated via Schooldom correspond strictly to grading standards mapped by national educational boards, including WAEC cumulative assessment requirements. Authorized teachers remain responsible for authenticating marks in response to local student grievances.
                </p>
              </section>

              <section className="space-y-2.5">
                <h4 className="font-display font-bold text-slate-900 text-sm">5. Limitation of Liability</h4>
                <p>
                  To the maximum extent permitted under Nigerian law, Schooldom cumulative liabilities shall not exceed the sums paid by the subscriber school during the immediate term preceding any litigation action.
                </p>
              </section>
            </div>
          ) : (
            /* PRIVACY POLICY & NDPA DOCUMENT */
            <div className="space-y-6 animate-in fade-in duration-150 text-slate-600">
              
              {/* IMPORTANT: NDPC Compliance Seal */}
              <div className="p-5 bg-teal-brand-50 border border-teal-brand-500/20 rounded-2xl">
                <div className="flex items-center gap-3 mb-2.5">
                  <div className="h-8 w-8 rounded-lg bg-teal-brand-500 text-white flex items-center justify-center font-bold text-sm">
                    🇳🇬
                  </div>
                  <div>
                    <h4 className="font-display font-black text-slate-900 text-xs tracking-wider">NDPC REGISTERED COMPLIANCE STATUS</h4>
                    <p className="text-[10px] text-teal-brand-700 font-mono font-bold">REGISTRY NO: NDPC/REG/ERP/0491-WAEC</p>
                  </div>
                </div>
                <p className="text-slate-600 text-[11px] leading-relaxed">
                  Schooldom Academy operations comply fully with the **Nigeria Data Protection Act (NDPA)**, regulated by the **Nigeria Data Protection Commission (NDPC)**. This privacy charter details our technical measures to protect sensitive educational records, student identities, parent finances, and biometric patterns.
                </p>
              </div>

              <section className="space-y-2.5">
                <h4 className="font-display font-bold text-slate-900 text-sm">1. Scope of Data Collection</h4>
                <p>
                  Working as a Data Processor under NDPA rules, we host and aggregate instructions on behalf of subscriber institutions who act as Data Controllers. Types of information collected include:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                    <div>
                      <strong className="text-slate-800 font-bold">Student Records</strong>
                      <p className="text-[10px] text-slate-500">Legal names, age brackets, admission serial numbers, gender data, and diagnostic quiz analytics.</p>
                    </div>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                    <div>
                      <strong className="text-slate-800 font-bold">Parent &amp; Guardian Info</strong>
                      <p className="text-[10px] text-slate-500">Contact telephone, WhatsApp ID, corresponding physical addresses, and school fee receipts tracking.</p>
                    </div>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                    <div>
                      <strong className="text-slate-800 font-bold">Staff Directory Logs</strong>
                      <p className="text-[10px] text-slate-500">Certified teaching IDs, phone lines, monthly salary receipts, and assigned classroom subjects mapping.</p>
                    </div>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                    <div>
                      <strong className="text-slate-800 font-bold">Biometric Safety Keys</strong>
                      <p className="text-[10px] text-slate-500">One-way secure QR code identifiers or cryptographically salted biometric punch keys (never raw assets).</p>
                    </div>
                  </div>
                </div>
              </section>

              <section className="space-y-2.5">
                <h4 className="font-display font-bold text-slate-900 text-sm">2. Ground for Processing Under NDPA</h4>
                <p>
                  Data collection is performed strictly based on standard academic performance compute services, fulfillment of legal administrative instruction mandates (providing report cards), or direct public consent received during student enrolment.
                </p>
              </section>

              <section className="space-y-2.5">
                <h4 className="font-display font-bold text-slate-900 text-sm">3. Hardware and Data Security Measures</h4>
                <p>
                  Schooldom shields client files with industry-first redundancy architectures:
                </p>
                <div className="space-y-2 pl-2">
                  <div className="flex gap-2 text-[11px]">
                    <span className="text-teal-brand-500 font-bold">▪</span>
                    <span><strong>TLS Encryption:</strong> All client communications and REST API requests are piped through forced SHA-256 AES HTTPS connections.</span>
                  </div>
                  <div className="flex gap-2 text-[11px]">
                    <span className="text-teal-brand-500 font-bold">▪</span>
                    <span><strong>Edge Storage Isolation:</strong> School transaction journals, grade-sheets, and digital IDs are segmented into customized structural sub-buckets preventing leaks.</span>
                  </div>
                  <div className="flex gap-2 text-[11px]">
                    <span className="text-teal-brand-500 font-bold">▪</span>
                    <span><strong>Offline Storage Encryption:</strong> Local CBT server boxes operate in encrypted partitions to protect offline test assets from host physical theft.</span>
                  </div>
                </div>
              </section>

              <section className="space-y-2.5">
                <h4 className="font-display font-bold text-slate-900 text-sm">4. Rights of Children &amp; Parent Consent</h4>
                <p>
                  Because K12 students are minors, we enforce strict NDPA compliance. No student scores, identity photos, or physical reports are shared with third-parties without the explicit written/digital invitation of the primary guardian. Parents have a statutory right to request a full transcript copy of their children's aggregated profiles at any time.
                </p>
              </section>

              <section className="space-y-2.5">
                <h4 className="font-display font-bold text-slate-900 text-sm">5. NDPA Complaints &amp; Data Protection Officer (DPO)</h4>
                <p>
                  Queries regarding our security posture, NDPC credentials, or audit trails should be directed to our appointed Data Protection Officers at:
                </p>
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1 font-mono text-[10px] text-slate-500">
                  <p className="text-slate-800 font-bold">Schooldom Academy Legal &amp; Security Division</p>
                  <p>Email: enquiry@schooldom.academy</p>
                  <p>Tel: +234 907 682 1365</p>
                  <p>CC: dpo@schooldom.academy</p>
                </div>
              </section>
            </div>
          )}

        </div>

        {/* Legal Footer Section */}
        <div className="bg-slate-50 px-6 py-4 border-t border-slate-150 flex flex-col sm:flex-row items-center justify-between gap-3 text-[10px] text-slate-400 font-semibold font-display">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="h-4 w-4 text-teal-brand-500" />
            <span>NDPC Compliance status verified on June 13, 2026.</span>
          </div>
          <button
            id="legal-btn-bottom-close"
            onClick={onClose}
            className="px-5 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-bold transition-all cursor-pointer"
          >
            Acknowledge &amp; Exit
          </button>
        </div>
      </div>
    </div>
  );
}
