import Image from 'next/image';

interface WatermarkPreviewProps {
  watermarkSrc: string | null;
  scale?: number;
  x?: number;
  y?: number;
  opacity?: number;
}

export function WatermarkPreview({ 
  watermarkSrc, 
  scale = 0.2, 
  x = 0.98, 
  y = 0.98, 
  opacity = 0.7 
}: WatermarkPreviewProps) {
  return (
    <div className="relative w-full aspect-[3/2] rounded-lg overflow-hidden bg-muted border select-none pointer-events-none">
      {/* Sample Photo */}
      <Image
        src="https://images.unsplash.com/photo-1519741497674-611481863552?q=80&w=1200&auto=format&fit=crop"
        alt="Sample event photo"
        fill
        className="object-cover"
        unoptimized
      />
      
      {/* Watermark Overlay */}
      {watermarkSrc ? (
        <div 
          className="absolute z-10"
          style={{
            width: `${scale * 100}%`,
            left: `${x * 100}%`,
            top: `${y * 100}%`,
            opacity: opacity
          }}
        >
          <img
            src={watermarkSrc}
            alt="Watermark preview"
            className="w-full h-auto object-contain pointer-events-none"
          />
        </div>
      ) : (
        <div className="absolute inset-0 flex items-center justify-center bg-background/20 backdrop-blur-sm">
          <p className="text-sm font-medium text-foreground bg-background/80 px-4 py-2 rounded-full shadow-sm">
            No watermark uploaded
          </p>
        </div>
      )}
    </div>
  );
}
