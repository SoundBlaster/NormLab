import type { ComponentProps } from 'react';

export function Logo({ className = '', ...props }: Omit<ComponentProps<'img'>, 'src' | 'alt'>) {
  return (
    <img
      {...props}
      className={`ui-logo ${className}`.trim()}
      src="/normlab-logo.svg"
      alt="NormLab"
      width={212}
      height={40}
    />
  );
}
