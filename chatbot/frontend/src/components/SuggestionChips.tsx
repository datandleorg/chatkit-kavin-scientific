import { Sparkles } from 'lucide-react';

interface SuggestionChipsProps {
  onSelect: (text: string) => void;
}

const suggestions = [
  'Find some formic acid for my lab',
  'Compare prices for sodium chloride across vendors',
  'Search for analytical grade methanol',
];

export default function SuggestionChips({ onSelect }: SuggestionChipsProps) {
  return (
    <div className="flex flex-col items-start gap-4 w-full max-w-full mx-auto px-4 sm:px-6 lg:px-8">
      <h2 className="text-lg font-semibold text-[var(--color-fg)]">
        Search for products for quote ...
      </h2>
      <div className="flex flex-col gap-1 w-full">
        {suggestions.map((text) => (
          <button
            key={text}
            onClick={() => onSelect(text)}
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-left
                       text-sm text-[var(--color-fg-muted)]
                       hover:bg-[var(--color-bg-secondary)] transition-colors duration-200"
          >
            <Sparkles size={14} className="shrink-0 text-[var(--color-fg-subtle)]" />
            <span>{text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
