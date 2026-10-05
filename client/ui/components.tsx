import type { ComponentProps, ReactNode } from 'react';
import './ui.css';

const classes = (base: string, extra?: string) => [base, extra].filter(Boolean).join(' ');
export type Tone = 'neutral' | 'success' | 'warning' | 'danger';

export function Button({
  variant = 'primary',
  className,
  type = 'button',
  ...props
}: ComponentProps<'button'> & { variant?: 'primary' | 'secondary' | 'quiet' }) {
  return (
    <button
      {...props}
      type={type}
      className={classes('ui-button', className)}
      data-variant={variant}
    />
  );
}
export function Input({ className, ...props }: ComponentProps<'input'>) {
  return <input {...props} className={classes('ui-control', className)} />;
}
export function Select({ className, ...props }: ComponentProps<'select'>) {
  return <select {...props} className={classes('ui-control', className)} />;
}
export function Textarea({ className, ...props }: ComponentProps<'textarea'>) {
  return <textarea {...props} className={classes('ui-control', className)} />;
}
export function Field({
  label,
  children,
  className,
  ...props
}: ComponentProps<'label'> & { label: ReactNode }) {
  return (
    <label {...props} className={classes('ui-field', className)}>
      <span>{label}</span>
      {children}
    </label>
  );
}
export function CheckField({
  children,
  className,
  ...props
}: Omit<ComponentProps<'input'>, 'type'>) {
  return (
    <label className={classes('ui-check', className)}>
      <input {...props} type="checkbox" />
      <span>{children}</span>
    </label>
  );
}
export function Panel({ className, ...props }: ComponentProps<'section'>) {
  return <section {...props} className={classes('ui-panel', className)} />;
}
export function SectionHeading({
  step,
  title,
  description,
  children,
}: {
  step?: string;
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <header className="ui-section-heading">
      {step && (
        <span className="ui-step" aria-hidden="true">
          {step}
        </span>
      )}
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {children}
    </header>
  );
}
export function Status({
  tone = 'neutral',
  className,
  ...props
}: ComponentProps<'span'> & { tone?: Tone }) {
  return <span {...props} className={classes('ui-status', className)} data-tone={tone} />;
}
export function Actions({ className, ...props }: ComponentProps<'div'>) {
  return <div {...props} className={classes('ui-actions', className)} />;
}
export function Quote({ className, ...props }: ComponentProps<'blockquote'>) {
  return <blockquote {...props} className={classes('ui-quote', className)} />;
}

export function Notice({
  tone = 'neutral',
  className,
  ...props
}: ComponentProps<'p'> & { tone?: Tone }) {
  return <p {...props} className={classes('ui-notice', className)} data-tone={tone} />;
}

export function Disclosure({
  summary,
  children,
  className,
  ...props
}: ComponentProps<'details'> & { summary: ReactNode }) {
  return (
    <details {...props} className={classes('ui-disclosure', className)}>
      <summary>{summary}</summary>
      {children}
    </details>
  );
}
