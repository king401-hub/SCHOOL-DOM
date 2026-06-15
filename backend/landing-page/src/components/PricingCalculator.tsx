import { useState } from 'react';
import { Sliders, Receipt, CheckCircle, ArrowRight, ShieldCheck, DatabaseZap, ShieldAlert } from 'lucide-react';

interface PricingCalculatorProps {
  onOpenOnboarding: () => void;
}

export default function PricingCalculator({ onOpenOnboarding }: PricingCalculatorProps) {
  const [studentCount, setStudentCount] = useState<number>(450);
  const [schoolType, setSchoolType] = useState<'K12' | 'Non-K12'>('K12');

  // Calculations
  const k12TermRate = 500; // per student per term
  const nonK12MonthRate = 200; // per student per month

  const calculateCost = () => {
    if (schoolType === 'K12') {
      const termTotal = studentCount * k12TermRate;
      const annualized3Terms = termTotal * 3;
      return {
        unitRate: `₦${k12TermRate.toLocaleString()} per activated student / term`,
        totalBill: termTotal,
        billLabel: "Total Student Activation Fee",
        extraMetric: `₦${annualized3Terms.toLocaleString()} School Year Total (3 Terms)`
      };
    } else {
      const monthTotal = studentCount * nonK12MonthRate;
      const termEquivalent = monthTotal * 3; // 3 months
      return {
        unitRate: `₦${nonK12MonthRate.toLocaleString()} per activated student / month`,
        totalBill: monthTotal,
        billLabel: "Monthly Student Activation Fee",
        extraMetric: `₦${termEquivalent.toLocaleString()} Quarter Total (3 Months)`
      };
    }
  };

  const costBreakdown = calculateCost();

  return (
    <section id="cost-calculator" className="py-20 bg-slate-900 text-white relative overflow-hidden">
      {/* Absolute design backdrops */}
      <div className="absolute top-[-25%] left-[-10%] w-[50%] h-[50%] bg-brand-500/20 rounded-full filter blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-15%] right-[-10%] w-[45%] h-[45%] bg-teal-brand-500/10 rounded-full filter blur-[100px] pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        
        {/* Header blocks */}
        <div className="text-center max-w-3xl mx-auto mb-12">
          <span className="text-xs font-semibold uppercase tracking-widest text-teal-brand-500 bg-teal-brand-500/10 border border-teal-500/20 px-3.5 py-1.5 rounded-full">
            Transparent Subscription Modeling
          </span>
          <h2 className="font-display font-bold text-3xl sm:text-4xl text-white mt-4 tracking-tight">
            Fair, Performance-Based Pricing Plans
          </h2>
          <p className="text-slate-400 mt-3 text-base">
            Schooldom is free to set up and configure. Admins and teachers run the backend completely free. Pay only the tiny activation fee to let students log in.
          </p>
        </div>

        {/* Free Administrative Access Banner Alert */}
        <div className="max-w-5xl mx-auto mb-12 p-5 sm:p-6 bg-brand-950/40 border border-brand-500/35 rounded-3xl flex flex-col sm:flex-row items-center sm:items-start gap-4 text-left shadow-lg relative overflow-hidden">
          <div className="absolute top-0 right-0 p-1 bg-brand-500/10 text-brand-400 text-[8.5px] uppercase font-bold tracking-widest rounded-bl-xl border-l border-b border-brand-500/20">
            Schooldom SLA Policy
          </div>
          <div className="p-3 bg-brand-500/10 text-teal-brand-405 rounded-2xl shrink-0 self-center sm:self-auto">
            <ShieldCheck className="h-6 w-6 text-teal-brand-400" />
          </div>
          <div className="space-y-1.5">
            <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <span>Admin &amp; Teacher Access is 100% Free</span>
              <span className="text-[10px] bg-emerald-500/20 border border-emerald-500/35 text-emerald-400 px-2 py-0.5 rounded-md font-mono">No Card Required</span>
            </h4>
            <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
              School owners, directors, principals, bursars (finance admins), and class teachers can manage classrooms, assign lesson materials, log daily attendance registers, compute scores, and design security PVC QR badges <strong className="text-white">completely free without paying a single Naira</strong>. 
            </p>
            <p className="text-xs text-slate-400 italic">
              *Only student profiles are restricted from logging on or practice testing on their personal portals until the campus admin pays the small active seat activation fee.
            </p>
          </div>
        </div>

        {/* Pricing Plan cards layout */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-5xl mx-auto mb-14">
          
          {/* Plan 1: K12 Category */}
          <div className="bg-slate-950/40 border border-slate-800 rounded-3xl p-6 sm:p-8 flex flex-col justify-between hover:border-brand-500/40 transition-all text-left">
            <div>
              <div className="flex justify-between items-start mb-6">
                <div>
                  <span className="text-[10px] font-bold tracking-widest bg-brand-600 px-3 py-1 rounded-full uppercase text-white">K12 SCHOOLS</span>
                  <h3 className="font-display font-extrabold text-2xl text-white mt-3">Kindergarten to SSS3</h3>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-display font-extrabold text-teal-brand-500">₦500</p>
                  <p className="text-[9.5px] uppercase tracking-wider text-slate-400 font-semibold mt-0.5">Per Student / Term Activation</p>
                </div>
              </div>

              <p className="text-sm text-slate-400 leading-relaxed mb-6">
                Perfect for nursery, primary, and secondary institutions. <strong className="text-white">Owners, admins, and teachers are 100% free</strong>. Student accounts require a tiny activation fee each term to enable portal logins and CBT practice testing.
              </p>

              <div className="space-y-3.5 border-t border-slate-800/80 pt-6">
                <div className="flex items-center gap-2.5 text-xs text-slate-300">
                  <span className="h-2 w-2 rounded-full bg-teal-brand-500" />
                  <span>Free, Unlimited Administrative Access Panels</span>
                </div>
                <div className="flex items-center gap-2.5 text-xs text-slate-300">
                  <span className="h-2 w-2 rounded-full bg-teal-brand-500" />
                  <span>Full access to Hybrid CBT (Online/Offline)</span>
                </div>
                <div className="flex items-center gap-2.5 text-xs text-slate-300">
                  <span className="h-2 w-2 rounded-full bg-teal-brand-500" />
                  <span>Unlimited automated terminal report cards</span>
                </div>
                <div className="flex items-center gap-2.5 text-xs text-slate-300">
                  <span className="h-2 w-2 rounded-full bg-teal-brand-500" />
                  <span>JAMB & WAEC extensive past paper simulator</span>
                </div>
                <div className="flex items-center gap-2.5 text-xs text-slate-300">
                  <span className="h-2 w-2 rounded-full bg-teal-brand-500" />
                  <span>Interactive lesson scheduler and finance gates</span>
                </div>
              </div>
            </div>

            <div className="mt-8">
              <button
                id="btn-bill-k12"
                onClick={() => { setSchoolType('K12'); onOpenOnboarding(); }}
                className="w-full text-center py-3 rounded-xl text-xs font-bold uppercase tracking-wider bg-slate-800 hover:bg-slate-700 hover:text-white border border-slate-700/60 transition-colors cursor-pointer"
              >
                Onboard under K12 Termly
              </button>
            </div>
          </div>

          {/* Plan 2: Non K12 Category */}
          <div className="bg-slate-950/40 border border-slate-800 rounded-3xl p-6 sm:p-8 flex flex-col justify-between hover:border-brand-500/40 transition-all text-left">
            <div>
              <div className="flex justify-between items-start mb-6">
                <div>
                  <span className="text-[10px] font-bold tracking-widest bg-teal-brand-500/20 border border-teal-500/30 px-3 py-1 rounded-full uppercase text-teal-brand-500">NON-K12 SCHOOLS</span>
                  <h3 className="font-display font-extrabold text-2xl text-white mt-3">Vocational & Continuing Ed</h3>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-display font-extrabold text-teal-brand-500">₦200</p>
                  <p className="text-[9.5px] uppercase tracking-wider text-slate-400 font-semibold mt-0.5">Per Student / Month Activation</p>
                </div>
              </div>

              <p className="text-sm text-slate-400 leading-relaxed mb-6">
                Engineered for flexible schedule learning, professional adult courses, continuing education classes, or tertiary tech bootcamps. <strong className="text-white">Staff run the system 100% free</strong>; only active students require monthly activation.
              </p>

              <div className="space-y-3.5 border-t border-slate-800/80 pt-6">
                <div className="flex items-center gap-2.5 text-xs text-slate-300">
                  <span className="h-2 w-2 rounded-full bg-teal-brand-500" />
                  <span>Free, Unlimited Registrar & Staff Modules</span>
                </div>
                <div className="flex items-center gap-2.5 text-xs text-slate-300">
                  <span className="h-2 w-2 rounded-full bg-teal-brand-500" />
                  <span>Flexible monthly active learner seat cycling</span>
                </div>
                <div className="flex items-center gap-2.5 text-xs text-slate-300">
                  <span className="h-2 w-2 rounded-full bg-teal-brand-500" />
                  <span>QR and Barcode mobile check-in scanners</span>
                </div>
                <div className="flex items-center gap-2.5 text-xs text-slate-300">
                  <span className="h-2 w-2 rounded-full bg-teal-brand-500" />
                  <span>On-demand printable custom PVC ID and badges</span>
                </div>
                <div className="flex items-center gap-2.5 text-xs text-slate-300">
                  <span className="h-2 w-2 rounded-full bg-teal-brand-500" />
                  <span>Splits balance finance gates (Paystack, Stripe)</span>
                </div>
              </div>
            </div>

            <div className="mt-8">
              <button
                id="btn-bill-nonk12"
                onClick={() => { setSchoolType('Non-K12'); onOpenOnboarding(); }}
                className="w-full text-center py-3 rounded-xl text-xs font-bold uppercase tracking-wider bg-slate-800 hover:bg-slate-700 hover:text-white border border-slate-700/60 transition-colors cursor-pointer"
              >
                Onboard under Month Flex
              </button>
            </div>
          </div>

        </div>

        {/* Dynamic sliding billing calculator widget */}
        <div className="max-w-4xl mx-auto bg-slate-950 p-6 sm:p-10 rounded-3xl border border-slate-800 glow-card">
          <div className="flex flex-col lg:flex-row gap-10 items-center text-left">
            
            <div className="flex-1 space-y-6 w-full">
              <div className="flex items-center gap-2 text-teal-brand-500">
                <Sliders className="h-5 w-5" />
                <span className="text-xs font-bold uppercase tracking-wider font-mono">Invoice Cost Estimator Tool</span>
              </div>
              
              <div>
                <h4 className="font-display font-extrabold text-xl text-white">Slide to Estimate For Your School</h4>
                <p className="text-xs text-slate-400 mt-1">Select school category and student volume to see student account activation estimations (Admin &amp; Teacher modules are 100% free).</p>
              </div>

              {/* Selector */}
              <div className="flex gap-2.5">
                <button
                  id="calc-selector-k12"
                  onClick={() => setSchoolType('K12')}
                  className={`flex-1 text-center py-2 rounded-xl text-xs font-bold border transition-colors cursor-pointer ${
                    schoolType === 'K12'
                      ? 'bg-brand-600 border-brand-700 text-white'
                      : 'bg-slate-900 border-slate-800 text-slate-400 hover:bg-slate-800/60'
                  }`}
                >
                  K12 (₦500 / term)
                </button>
                <button
                  id="calc-selector-nonk12"
                  onClick={() => setSchoolType('Non-K12')}
                  className={`flex-1 text-center py-2 rounded-xl text-xs font-bold border transition-colors cursor-pointer ${
                    schoolType === 'Non-K12'
                      ? 'bg-brand-600 border-brand-700 text-white'
                      : 'bg-slate-900 border-slate-800 text-slate-400 hover:bg-slate-800/60'
                  }`}
                >
                  Non K12 (₦200 / month)
                </button>
              </div>

              {/* Slider Input */}
              <div className="space-y-3">
                <div className="flex justify-between text-xs font-semibold text-slate-300">
                  <span htmlFor="student-slider-calculator">Estimated Enrollment:</span>
                  <span className="font-mono text-brand-400 text-sm font-bold">{studentCount} Students</span>
                </div>
                <input
                  id="student-slider-calculator"
                  type="range"
                  min="50"
                  max="5000"
                  step="50"
                  value={studentCount}
                  onChange={(e) => setStudentCount(parseInt(e.target.value))}
                  className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-teal-brand-500"
                />
                <div className="flex justify-between font-mono text-[9px] text-slate-500">
                  <span>50</span>
                  <span>1,000</span>
                  <span>2,500</span>
                  <span>3,500</span>
                  <span>5,000 STUDENTS</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs bg-slate-900 p-4 rounded-xl text-slate-400">
                <div className="space-y-1">
                  <p className="text-[9px] font-bold uppercase tracking-wider text-slate-500">Active Migration</p>
                  <p className="font-semibold text-white">₦0 Free Standard migration</p>
                </div>
                <div className="space-y-1 text-right">
                  <p className="text-[9px] font-bold uppercase tracking-wider text-slate-500">Schooldom support</p>
                  <p className="font-semibold text-white">24/7 Dedicated expert agent</p>
                </div>
              </div>
            </div>

            {/* Calculations Result Output */}
            <div className="w-full lg:w-72 bg-slate-900 rounded-2xl p-6 border border-slate-800 text-center flex flex-col justify-between shrink-0 h-80">
              <div className="space-y-2">
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{costBreakdown.billLabel}</p>
                <p className="text-4xl font-display font-extrabold text-teal-brand-500 tracking-tight mt-1.5">
                  ₦{costBreakdown.totalBill.toLocaleString()}
                </p>
                <p className="text-[10px] font-mono text-slate-400 font-semibold">{costBreakdown.unitRate}</p>
              </div>

              <div className="border-t border-slate-800 py-4 text-xs font-medium text-slate-300">
                {costBreakdown.extraMetric}
              </div>

              <button
                id="btn-estimator-onboard"
                onClick={onOpenOnboarding}
                className="w-full items-center justify-center gap-2 py-3 rounded-xl font-bold text-xs uppercase bg-brand-600 hover:bg-brand-700 text-white shadow-md cursor-pointer"
              >
                Onboard With This Budget
              </button>
            </div>

          </div>
        </div>

      </div>
    </section>
  );
}
