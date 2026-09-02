import { Aperture } from 'lucide-react';

interface LogoProps {
  size?: 'sm' | 'md' | 'lg';
}

const sizeMap = {
  sm: { icon: 16, text: 'text-lg' },
  md: { icon: 20, text: 'text-2xl' },
  lg: { icon: 28, text: 'text-4xl' },
} as const;

export function Logo({ size = 'md' }: LogoProps) {
  const config = sizeMap[size];

  return (
    <span className="inline-flex items-center gap-2 select-none">
      <Aperture size={config.icon} strokeWidth={1.8} className="text-signal" />
      <span className={`${config.text} font-bold tracking-tight`}>
        SpotMe
      </span>
    </span>
  );
}
