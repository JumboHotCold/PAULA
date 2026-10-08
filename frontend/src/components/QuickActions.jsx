/**
 * QuickActions Component
 * =======================
 * Scrollable bar of pre-set SPUS query buttons.
 */

import MaterialIcon from './MaterialIcon';

const QUICK_ACTIONS = [
  { icon: 'assignment', label: 'Enrollment Info', prompt: 'How do I enroll at SPUS? What are the requirements?' },
  { icon: 'location_on', label: 'Office Locations', prompt: 'Where are the main offices located in SPUS campus?' },
  { icon: 'payments', label: 'Tuition Fees', prompt: 'What are the current tuition fees at SPUS?' },
  { icon: 'event', label: 'Academic Calendar', prompt: 'What is the academic calendar for this school year?' },
  { icon: 'phone', label: 'Contact Info', prompt: 'How can I contact the SPUS administration?' },
  { icon: 'school', label: 'Programs Offered', prompt: 'What degree programs are offered at SPUS?' },
];

export default function QuickActions({ onAction, disabled }) {
  return (
    <div className="shrink-0 px-4 py-3 border-b border-glass-border bg-bg-secondary/50">
      <p className="text-[0.7rem] text-text-muted uppercase tracking-wider font-medium mb-2 pl-1">
        Quick Actions
      </p>
      <div className="flex gap-2 overflow-x-auto pb-1" style={{ scrollbarWidth: 'none' }}>
        {QUICK_ACTIONS.map((action, i) => (
          <button
            key={i}
            id={`quick-action-${i}`}
            onClick={() => onAction(action.prompt)}
            disabled={disabled}
            className="quick-action-btn shrink-0 text-xs px-3.5 py-2 rounded-full
                       border border-glass-border text-text-secondary
                       hover:text-spus-gold disabled:opacity-40 disabled:cursor-not-allowed
                       cursor-pointer whitespace-nowrap inline-flex items-center gap-1.5"
          >
            <MaterialIcon name={action.icon} size={14} />
            <span>{action.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
