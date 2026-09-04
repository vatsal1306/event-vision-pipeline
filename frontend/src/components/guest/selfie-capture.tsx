import { useRef, useState, useCallback } from 'react';
import Webcam from 'react-webcam';
import { Button } from '@/components/ui/button';
import { Camera, RefreshCw, Check } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';

interface SelfieCaptureProps {
  onCapture: (imageBlob: Blob) => Promise<void>;
  isLoading: boolean;
}

export function SelfieCapture({ onCapture, isLoading }: SelfieCaptureProps) {
  const webcamRef = useRef<Webcam>(null);
  const [imgSrc, setImgSrc] = useState<string | null>(null);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);

  const capture = useCallback(() => {
    const imageSrc = webcamRef.current?.getScreenshot();
    if (imageSrc) {
      setImgSrc(imageSrc);
    }
  }, [webcamRef]);

  const retake = () => {
    setImgSrc(null);
  };

  const handleConfirm = async () => {
    if (!imgSrc) return;
    
    try {
      // Convert base64 string to Blob
      const res = await fetch(imgSrc);
      const blob = await res.blob();
      await onCapture(blob);
    } catch (err) {
      toast.error('Failed to process image');
    }
  };

  return (
    <div className="w-full flex flex-col items-center space-y-6">
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-bold text-white tracking-tight">Almost there!</h2>
        <p className="text-zinc-400">Take a quick selfie so we can find your photos.</p>
      </div>

      <div className="relative w-full max-w-sm aspect-[3/4] bg-zinc-900 rounded-2xl overflow-hidden border-2 border-zinc-800">
        <AnimatePresence mode="wait">
          {!imgSrc ? (
            <motion.div
              key="webcam"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0"
            >
              <Webcam
                audio={false}
                ref={webcamRef}
                screenshotFormat="image/jpeg"
                videoConstraints={{ facingMode: "user" }}
                onUserMedia={() => setHasPermission(true)}
                onUserMediaError={() => setHasPermission(false)}
                className="w-full h-full object-cover"
                mirrored={true}
              />
              
              {/* Face Guide Overlay */}
              <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
                <svg className="w-full h-full" preserveAspectRatio="none">
                  <defs>
                    <mask id="face-hole">
                      <rect width="100%" height="100%" fill="white" />
                      {/* The transparent cutout for the face */}
                      <ellipse cx="50%" cy="45%" rx="35%" ry="30%" fill="black" />
                    </mask>
                  </defs>
                  {/* The semi-transparent overlay everywhere except the hole */}
                  <rect width="100%" height="100%" fill="rgba(0,0,0,0.5)" mask="url(#face-hole)" />
                  {/* The border of the guide */}
                  <ellipse cx="50%" cy="45%" rx="35%" ry="30%" fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth="2" strokeDasharray="6 6" />
                </svg>
              </div>

              {hasPermission === false && (
                <div className="absolute inset-0 bg-zinc-900 flex flex-col items-center justify-center p-6 text-center z-10">
                  <Camera className="w-12 h-12 text-zinc-500 mb-4" />
                  <p className="text-white font-medium mb-2">Camera Access Denied</p>
                  <p className="text-zinc-400 text-sm">Please allow camera access in your browser settings to take a selfie.</p>
                </div>
              )}
            </motion.div>
          ) : (
            <motion.div
              key="preview"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0"
            >
              <img src={imgSrc} alt="Selfie preview" className="w-full h-full object-cover" />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="w-full max-w-sm space-y-4">
        {!imgSrc ? (
          <Button 
            size="lg" 
            className="w-full h-14 rounded-full text-base font-semibold shadow-lg shadow-primary/20"
            onClick={capture}
            disabled={hasPermission === false}
          >
            <Camera className="w-5 h-5 mr-2" />
            Capture Selfie
          </Button>
        ) : (
          <div className="flex gap-3">
            <Button 
              variant="outline" 
              size="lg" 
              className="flex-1 h-14 rounded-full text-base font-medium border-zinc-700 hover:bg-zinc-800"
              onClick={retake}
              disabled={isLoading}
            >
              <RefreshCw className="w-5 h-5 mr-2" />
              Retake
            </Button>
            <Button 
              size="lg" 
              className="flex-1 h-14 rounded-full text-base font-semibold shadow-lg shadow-primary/20"
              onClick={handleConfirm}
              disabled={isLoading}
            >
              <Check className="w-5 h-5 mr-2" />
              {isLoading ? 'Processing...' : 'Use Photo'}
            </Button>
          </div>
        )}
        
        <p className="text-xs text-zinc-500 text-center px-4 leading-relaxed">
          Your selfie is used only to find your photos and is not stored permanently.
        </p>
      </div>
    </div>
  );
}
