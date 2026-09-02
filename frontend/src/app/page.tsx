export default function Home() {
  return (
    <main className="flex flex-col items-center justify-center min-h-screen p-8 text-center space-y-8 bg-canvas text-ink">
      <h1 className="text-6xl font-medium tracking-tight -tracking-[0.02em]">SpotMe</h1>
      <p className="text-lg opacity-80 max-w-md font-[450]">
        Every guest, every photo, found.
      </p>
      
      <div className="flex gap-4">
        <button className="bg-ink text-canvas rounded-button px-6 py-2.5 font-medium -tracking-[0.02em]">
          Learn more
        </button>
        <button className="bg-white text-ink border-[1.5px] border-ink rounded-button px-6 py-2.5 font-[450]">
          Secondary action
        </button>
      </div>

      <div className="mt-12">
        <button className="bg-signal text-white rounded-[24px] px-[30px] py-[1px] text-[13px] tracking-[0.01em]">
          Consent / Compliance
        </button>
      </div>
    </main>
  );
}
