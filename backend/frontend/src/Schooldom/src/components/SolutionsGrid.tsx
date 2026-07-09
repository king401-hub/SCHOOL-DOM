import { useState } from 'react';
import { SOLUTIONS } from '../data';
import { SolutionFeature } from '../types';
import { 
  Plus, CheckCircle2, Terminal, CreditCard, FileSpreadsheet, 
  UserCheck, Sparkles, Library, Database, Layers, Contact, BadgeAlert
} from 'lucide-react';

interface SolutionsGridProps {
  onOpenOnboarding: () => void;
}

const iconMap: { [key: string]: any } = {
  Terminal: Terminal,
  CreditCard: CreditCard,
  FileSpreadsheet: FileSpreadsheet,
  UserCheck: UserCheck,
  Sparkles: Sparkles,
  Library: Library,
  DatabaseZap: Database,
  Layers: Layers,
  Contact: Contact
};

export default function SolutionsGrid({ onOpenOnboarding }: SolutionsGridProps) {
  const [filter, setFilter] = useState<'all' | 'academic' | 'operations' | 'finance' | 'students'>('all');
  const [selectedSolution, setSelectedSolution] = useState<string | null>(null);

  const filteredSolutions = SOLUTIONS.filter(
    (sol) => filter === 'all' || sol.category === filter
  );

  return (
    <section id="solutions" className="py-20 bg-white dark:bg-slate-950 transition-colors duration-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Header content block */}
        <div className="text-center max-w-3xl mx-auto mb-12">
          <span className="text-xs font-bold uppercase tracking-widest text-teal-brand-600 dark:text-teal-brand-400 bg-teal-brand-50 dark:bg-teal-brand-950/40 px-3 py-1 rounded-full border border-teal-brand-500/15 dark:border-teal-brand-500/20">
            Solutions Avalanche
          </span>
          <h2 className="font-display font-bold text-3xl sm:text-4xl text-brand-950 dark:text-white mt-4 tracking-tight">
            Comprehensive Tools to Revolutionize School Admin
          </h2>
          <p className="text-gray-600 dark:text-slate-400 mt-3 text-base">
            Replace dozens of disparate softwares, excel trackers, and physical registries. Schooldom handles everything.
          </p>
        </div>

        {/* Categories Tab Navigation */}
        <div className="flex flex-wrap justify-center gap-2 mb-10 max-w-xl mx-auto">
          {['all', 'academic', 'operations', 'finance', 'students'].map((cat) => (
            <button
              key={cat}
              id={`btn-filter-${cat}`}
              onClick={() => {
                setFilter(cat as any);
                setSelectedSolution(null);
              }}
              className={`px-4.5 py-2 rounded-xl text-xs font-bold tracking-wide transition-all uppercase cursor-pointer ${
                filter === cat
                  ? 'bg-slate-900 dark:bg-white text-white dark:text-slate-900 shadow-sm'
                  : 'bg-slate-100 dark:bg-slate-900 text-gray-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800'
              }`}
            >
              {cat === 'all' ? 'All Modules' : cat}
            </button>
          ))}
        </div>

        {/* Feature Grid / Expanded details viewport */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* List section */}
          <div className={`space-y-4 ${selectedSolution ? 'lg:col-span-6' : 'lg:col-span-12'} transition-all duration-300`}>
            <div className={`grid grid-cols-1 ${selectedSolution ? 'sm:grid-cols-1' : 'sm:grid-cols-2 lg:grid-cols-3'} gap-4`}>
              {filteredSolutions.map((sol) => {
                const IconComponent = iconMap[sol.icon] || Terminal;
                const isSelected = selectedSolution === sol.id;
                return (
                  <div
                    key={sol.id}
                    id={`sol-card-${sol.id}`}
                    onClick={() => setSelectedSolution(isSelected ? null : sol.id)}
                    className={`p-5 rounded-2xl cursor-pointer text-left transition-all duration-300 border ${
                      isSelected
                        ? 'bg-brand-600 text-white border-brand-700 shadow-xl shadow-brand-500/20 translate-y-[-2px]'
                        : 'bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 border-gray-200/70 dark:border-slate-800 hover:border-brand-300 dark:hover:border-brand-700 hover:shadow-lg hover:shadow-brand-100/30 dark:hover:shadow-none hover:translate-y-[-3px] hover:scale-[1.02]'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className={`p-2.5 rounded-xl ${isSelected ? 'bg-white/10 text-white' : 'bg-brand-50 dark:bg-brand-950/40 text-brand-600 dark:text-brand-400'}`}>
                        <IconComponent className="h-5 w-5" />
                      </div>
                      <span className={`text-[9px] font-bold uppercase px-2 py-0.5 rounded ${
                        isSelected ? 'bg-white/20 text-white' : 'bg-slate-100 dark:bg-slate-800 text-gray-500 dark:text-slate-400'
                      }`}>
                        {sol.category}
                      </span>
                    </div>

                    <h4 className={`font-display font-bold text-sm sm:text-base mt-4 tracking-tight leading-snug ${isSelected ? 'text-white' : 'text-brand-950 dark:text-white'}`}>
                      {sol.title}
                    </h4>
                    <p className={`text-xs mt-2 leading-relaxed ${isSelected ? 'text-brand-100' : 'text-gray-500 dark:text-slate-400'}`}>
                      {sol.shortDescription}
                    </p>

                    <div className="flex items-center gap-1.5 font-semibold text-xs mt-4 group">
                      <span className={isSelected ? 'text-white' : 'text-brand-600 dark:text-brand-400 hover:text-brand-700 dark:hover:text-brand-300'}>
                        {isSelected ? 'Click to minimize spec' : 'Explore specifications'}
                      </span>
                      <Plus className={`h-4.5 w-4.5 transition-transform ${isSelected ? 'rotate-45' : ''}`} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Expanded specs module */}
          {selectedSolution && (
            <div className="lg:col-span-6 border border-gray-200/90 dark:border-slate-800 rounded-3xl p-6 sm:p-8 bg-slate-50 dark:bg-slate-900 relative animate-in fade-in slide-in-from-right-4 duration-300 text-left">
              {(() => {
                const activeSol = SOLUTIONS.find(s => s.id === selectedSolution)!;
                const IconComponent = iconMap[activeSol.icon] || Terminal;
                return (
                  <>
                    <div className="flex items-center gap-3 border-b border-gray-200 dark:border-slate-800 pb-5">
                      <div className="p-3 rounded-2xl bg-brand-600 text-white">
                        <IconComponent className="h-6 w-6" />
                      </div>
                      <div>
                        <span className="text-[10px] uppercase tracking-wider font-extrabold text-brand-600 dark:text-brand-400 bg-brand-50 dark:bg-brand-950/40 border border-brand-200/60 dark:border-brand-900/60 px-2.5 py-0.5 rounded-full">
                          {activeSol.category.toUpperCase()} SEGMENT
                        </span>
                        <h3 className="font-display font-extrabold text-xl text-brand-950 dark:text-white mt-1">{activeSol.title}</h3>
                      </div>
                    </div>

                    <div className="py-5 space-y-4">
                      <div>
                        <h5 className="text-[10px] font-bold text-gray-400 dark:text-slate-500 uppercase tracking-widest">Functional Scope</h5>
                        <p className="text-gray-600 dark:text-slate-300 text-sm leading-relaxed mt-1.5">{activeSol.description}</p>
                      </div>

                      <div>
                        <h5 className="text-[10px] font-bold text-gray-400 dark:text-slate-500 uppercase tracking-widest mb-2.5">Key Core Benefits</h5>
                        <ul className="space-y-2 text-xs text-brand-950 dark:text-slate-200">
                          {activeSol.benefits.map((benefit, idx) => (
                            <li key={idx} className="flex items-start gap-2.5 font-medium leading-relaxed">
                              <CheckCircle2 className="h-4.5 w-4.5 text-teal-brand-500 shrink-0 mt-0.5" />
                              <span>{benefit}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {activeSol.specs && (
                        <div className="p-3.5 bg-brand-50 dark:bg-brand-950/30 border border-brand-100 dark:border-brand-900/50 rounded-xl flex items-start gap-2 text-xs text-brand-900 dark:text-brand-200 font-medium">
                          <CheckCircle2 className="h-4 w-4 text-brand-600 dark:text-brand-400 shrink-0 mt-0.5" />
                          <span>
                            <strong>Enterprise Spec:</strong> {activeSol.specs}
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="border-t border-gray-200 dark:border-slate-800 pt-5 flex items-center gap-3">
                      <button
                        id="btn-onboard-solution-direct"
                        onClick={onOpenOnboarding}
                        className="flex-1 text-center py-3 rounded-xl font-bold text-sm bg-brand-600 border border-brand-700 text-white hover:bg-brand-700 active:bg-brand-800 transition-all cursor-pointer"
                      >
                        Request Active Integration
                      </button>
                      <button
                        id="btn-close-solution-detail"
                        onClick={() => setSelectedSolution(null)}
                        className="px-4 py-3 rounded-xl border border-gray-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-sm font-semibold text-gray-700 dark:text-slate-300 cursor-pointer"
                      >
                        Close
                      </button>
                    </div>
                  </>
                );
              })()}
            </div>
          )}

        </div>

      </div>
    </section>
  );
}
