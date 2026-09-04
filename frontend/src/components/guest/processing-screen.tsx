import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';

interface ProcessingScreenProps {
  photographerName?: string;
  photographerLogo?: string | null;
}

export function ProcessingScreen({ photographerName, photographerLogo }: ProcessingScreenProps) {
  return (
    <div className="w-full min-h-[60vh] flex flex-col items-center justify-center p-6 text-center space-y-12">
      <div className="space-y-8">
        {/* Animated Sparkle Loader */}
        <motion.div
          animate={{ 
            scale: [1, 1.2, 1],
            rotate: [0, 10, -10, 0]
          }}
          transition={{ 
            duration: 2,
            repeat: Infinity,
            ease: "easeInOut"
          }}
          className="w-24 h-24 mx-auto bg-primary/10 rounded-full flex items-center justify-center"
        >
          <Sparkles className="w-12 h-12 text-primary" />
        </motion.div>

        <div className="space-y-4 max-w-sm mx-auto">
          <h2 className="text-2xl font-bold text-white">We&apos;re gathering your memories...</h2>
          <p className="text-zinc-400 leading-relaxed">
            This might take a moment. You can close this page and come back later — just log in with your mobile number.
          </p>
        </div>
      </div>

      {/* Photographer Branding */}
      <div className="absolute bottom-8 left-0 right-0 flex items-center justify-center opacity-60">
        <div className="flex items-center gap-3">
          {photographerLogo ? (
            <img src={photographerLogo} alt={photographerName || 'Studio'} className="h-6 w-auto" />
          ) : (
            <div className="h-6 w-6 rounded-sm bg-primary flex items-center justify-center font-bold text-xs">
              {photographerName?.charAt(0) || 'P'}
            </div>
          )}
          {photographerName && <span className="text-sm font-medium tracking-wide">{photographerName}</span>}
        </div>
      </div>
    </div>
  );
}
