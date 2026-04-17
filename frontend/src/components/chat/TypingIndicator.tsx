"use client";

export function TypingIndicator() {
  return (
    <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-4 py-3 text-slate-500">
      {[0, 150, 300].map((delay) => (
        <span
          className="typing-indicator-dot h-2.5 w-2.5 rounded-full bg-slate-400"
          key={delay}
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
      <style jsx>{`
        .typing-indicator-dot {
          animation: typingBounce 900ms infinite ease-in-out;
        }

        @keyframes typingBounce {
          0%,
          80%,
          100% {
            transform: translateY(0);
            opacity: 0.45;
          }

          40% {
            transform: translateY(-5px);
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
}
