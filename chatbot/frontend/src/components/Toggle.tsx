import type { KeyboardEvent } from 'react';

export interface ToggleProps {
  /** Whether the toggle is on (true) or off (false). */
  checked: boolean;
  /** Called with the new boolean value when user toggles. */
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  /** Accessible label. */
  'aria-label': string;
  /** Optional label shown next to the track. */
  label?: string;
  /** Optional icon (e.g. Brain) shown when on. */
  icon?: React.ReactNode;
  className?: string;
  title?: string;
}

/**
 * Controlled toggle (switch). Single control: checked state is the only source of truth.
 * Use for reasoning, feature flags, etc. Prevents double-toggle from nested elements.
 */
export default function Toggle({
  checked,
  onCheckedChange,
  disabled = false,
  'aria-label': ariaLabel,
  label,
  icon,
  className = '',
  title,
}: ToggleProps) {
  const handleClick = () => {
    if (disabled) return;
    onCheckedChange(!checked);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onCheckedChange(!checked);
    }
  };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      title={title}
      className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium
        text-[var(--color-fg-muted)] hover:bg-[var(--color-bg-tertiary)] cursor-pointer
        transition-colors duration-150 border-0 bg-transparent disabled:opacity-50 disabled:cursor-not-allowed
        focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2
        ${className}`}
    >
      {icon != null && (
        <span className={checked ? 'text-[var(--color-accent)]' : 'text-[var(--color-fg-subtle)]'}>
          {icon}
        </span>
      )}
      {label != null && <span>{label}</span>}
      <span
        className={`inline-block w-7 h-3.5 rounded-full relative transition-colors duration-150 ${
          checked ? 'bg-[var(--color-accent)]' : 'bg-[var(--color-bg-tertiary)]'
        }`}
        aria-hidden
      >
        <span
          className={`absolute top-0.5 w-2.5 h-2.5 rounded-full bg-white shadow transition-[left] duration-150 ${
            checked ? 'left-3.5' : 'left-0.5'
          }`}
        />
      </span>
    </button>
  );
}
