import Image from 'next/image';

interface LogoProps {
  size?: 'sm' | 'md' | 'lg';
}

const sizeMap = {
  sm: { height: 24, width: 90 },
  md: { height: 32, width: 120 },
  lg: { height: 48, width: 180 },
} as const;

export function Logo({ size = 'md' }: LogoProps) {
  const config = sizeMap[size];

  return (
    <div className="relative inline-block select-none" style={{ height: config.height, width: config.width }}>
      <Image
        src="/logo.png"
        alt="SpotMe Logo"
        fill
        className="object-contain"
        priority
      />
    </div>
  );
}
