import Image from 'next/image';

interface WatermarkPreviewProps {
  watermarkSrc: string | null;
}

export function WatermarkPreview({ watermarkSrc }: WatermarkPreviewProps) {
  return (
    <div className="relative w-full aspect-[3/2] rounded-lg overflow-hidden bg-muted border">
      {/* Sample Photo */}
      <Image
        src="https://picsum.photos/seed/samplephoto/1200/800"
        alt="Sample event photo"
        fill
        className="object-cover"
        unoptimized
      />
      
      {/* Watermark Overlay */}
      {watermarkSrc ? (
        <div className="absolute bottom-4 right-4 w-1/4 max-w-[200px] aspect-[2/1]">
          <Image
            src={watermarkSrc}
            alt="Watermark preview"
            fill
            className="object-contain opacity-40"
            unoptimized
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
