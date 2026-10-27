export default function PromptGrid({ onPromptClick }) {
  const prompts = [
    "What programs are offered?",
    "How do I enroll?",
    "Where is the registrar office?",
    "Does SPUS offer scholarships?"
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full max-w-2xl mx-auto mt-6 px-4">
      {prompts.map((p, i) => (
        <button
          key={i}
          onClick={() => onPromptClick(p)}
          className="suggestion-card text-left"
        >
          {p}
        </button>
      ))}
    </div>
  );
}
