import { useState } from 'react';
import { Rnd } from 'react-rnd';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import Image from 'next/image';

interface WatermarkEditorModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  file: File | null;
  onSave: (file: File, scale: number, x: number, y: number, opacity: number) => void;
  isUploading?: boolean;
  defaultOpacity?: number;
  defaultX?: number;
  defaultY?: number;
  defaultScale?: number;
}

export function WatermarkEditorModal({
  open,
  onOpenChange,
  file,
  onSave,
  isUploading,
  defaultOpacity = 1,
  defaultX,
  defaultY,
  defaultScale = 0.2,
}: WatermarkEditorModalProps) {
  const [opacity, setOpacity] = useState(defaultOpacity);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [isInitialized, setIsInitialized] = useState(false);
  
  // Create object URL for the file to preview
  const watermarkUrl = file ? URL.createObjectURL(file) : '';

  const containerRef = (node: HTMLDivElement | null) => {
    if (node && !isInitialized) {
      const { clientWidth, clientHeight } = node;
      setContainerSize({ width: clientWidth, height: clientHeight });

      // Determine initial dimensions (using a 2:1 ratio for the watermark placeholder)
      const targetWidth = clientWidth * defaultScale;
      const targetHeight = targetWidth / 2; // Rough assumption

      let initialX = clientWidth - targetWidth - (clientWidth * 0.02);
      let initialY = clientHeight - targetHeight - (clientHeight * 0.02);

      if (defaultX !== undefined) initialX = defaultX * clientWidth;
      if (defaultY !== undefined) initialY = defaultY * clientHeight;

      setSize({ width: targetWidth, height: targetHeight });
      setPosition({ x: initialX, y: initialY });
      setIsInitialized(true);
    }
  };

  const handleSave = () => {
    if (!containerSize.width || !containerSize.height || !file) return;

    // Convert pixels to percentages (0.0 to 1.0)
    const xRatio = position.x / containerSize.width;
    const yRatio = position.y / containerSize.height;
    const scaleRatio = size.width / containerSize.width;

    onSave(file, scaleRatio, xRatio, yRatio, opacity);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>Edit Watermark</DialogTitle>
          <DialogDescription>
            Resize and position your watermark. It will be applied exactly here on all future uploads.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <label className="text-sm font-medium">Opacity: {Math.round(opacity * 100)}%</label>
            </div>
            <Slider
              value={[opacity]}
              onValueChange={([val]) => setOpacity(val)}
              min={0.1}
              max={1}
              step={0.05}
            />
          </div>

          <div
            ref={containerRef}
            className="relative w-full aspect-[3/2] bg-muted rounded-md overflow-hidden select-none"
            style={{ touchAction: 'none' }}
          >
            <Image
              src="https://images.unsplash.com/photo-1519741497674-611481863552?q=80&w=1200&auto=format&fit=crop"
              alt="Sample background"
              fill
              className="object-cover pointer-events-none"
              unoptimized
            />

            {isInitialized && (
              <Rnd
                bounds="parent"
                position={position}
                size={{ width: size.width, height: size.height }}
                onDragStop={(e, d) => setPosition({ x: d.x, y: d.y })}
                onResizeStop={(e, direction, ref, delta, position) => {
                  setSize({ width: parseInt(ref.style.width, 10), height: parseInt(ref.style.height, 10) });
                  setPosition(position);
                }}
                lockAspectRatio={true}
                className="z-10"
              >
                <div
                  className="w-full h-full relative cursor-move hover:ring-2 hover:ring-primary rounded overflow-hidden"
                  style={{ opacity }}
                >
                  <Image
                    src={watermarkUrl}
                    alt="Watermark overlay"
                    fill
                    className="object-contain pointer-events-none"
                    unoptimized
                  />
                </div>
              </Rnd>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleSave}>Save Settings</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
