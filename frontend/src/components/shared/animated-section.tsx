'use client';

import { motion, type Variants } from 'framer-motion';
import { fadeIn, slideUp, scaleIn } from '@/lib/motion';

const variantMap: Record<string, Variants> = {
  fadeIn: { initial: fadeIn.initial, animate: fadeIn.animate },
  slideUp: { initial: slideUp.initial, animate: slideUp.animate },
  scaleIn: { initial: scaleIn.initial, animate: scaleIn.animate },
};

interface AnimatedSectionProps {
  children: React.ReactNode;
  variant?: 'fadeIn' | 'slideUp' | 'scaleIn';
  className?: string;
  delay?: number;
}

export function AnimatedSection({
  children,
  variant = 'fadeIn',
  className,
  delay = 0,
}: AnimatedSectionProps) {
  const variants = variantMap[variant];

  return (
    <motion.div
      initial="initial"
      whileInView="animate"
      viewport={{ once: true, margin: '-80px' }}
      variants={variants}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
