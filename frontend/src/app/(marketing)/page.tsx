import Link from 'next/link';
import { Upload, ScanFace, Images, Smartphone, Zap, Shield } from 'lucide-react';
import { AnimatedSection } from '@/components/shared/animated-section';

const steps = [
  {
    icon: Upload,
    title: 'Upload your event photos',
    description: 'Drag and drop thousands of photos. Our resumable uploads handle any connection — even on hotel Wi-Fi.',
  },
  {
    icon: ScanFace,
    title: 'AI detects every face',
    description: 'Advanced facial recognition clusters every guest across every photo, automatically.',
  },
  {
    icon: Images,
    title: 'Guests get their gallery',
    description: 'Each guest takes a quick selfie and instantly sees only the photos they appear in. No app download.',
  },
] as const;

const features = [
  {
    icon: Smartphone,
    title: 'No app required',
    description: 'Guests open a browser link. That\'s it. Works on every phone, tablet, and laptop.',
  },
  {
    icon: Zap,
    title: 'Blazing fast delivery',
    description: 'Guests get their personalized gallery before the party ends. No more waiting weeks for Google Drive links.',
  },
  {
    icon: Shield,
    title: 'Your brand, front and center',
    description: 'Your studio name, logo, and watermark on every gallery. The platform stays invisible — you get the credit.',
  },
] as const;

export default function MarketingPage() {
  return (
    <>
      {/* ─── Hero Section ─── */}
      <section className="relative overflow-hidden">
        <div className="max-w-4xl mx-auto px-6 pt-24 pb-20 md:pt-36 md:pb-32 text-center">
          <AnimatedSection variant="slideUp">
            <span className="inline-block text-xs font-semibold tracking-widest uppercase text-signal mb-6">
              AI-Powered Photo Delivery
            </span>
          </AnimatedSection>

          <AnimatedSection variant="slideUp" delay={0.1}>
            <h1 className="text-5xl md:text-7xl font-bold tracking-tight leading-[1.08] mb-6">
              Every guest finds
              <br />
              their photos.{' '}
              <span className="text-signal">Instantly.</span>
            </h1>
          </AnimatedSection>

          <AnimatedSection variant="slideUp" delay={0.2}>
            <p className="text-lg md:text-xl text-ink/60 max-w-xl mx-auto mb-10 leading-relaxed">
              Upload once. AI does the rest. Deliver personalized, branded photo galleries to every guest through a simple browser link.
            </p>
          </AnimatedSection>

          <AnimatedSection variant="slideUp" delay={0.3}>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link
                href="/register"
                className="w-full sm:w-auto bg-signal text-white rounded-button px-8 py-3 font-semibold text-base hover:bg-signal-light transition-colors"
              >
                Get Started — It&apos;s Free
              </Link>
              <Link
                href="/login"
                className="w-full sm:w-auto bg-transparent text-ink border border-ink/20 rounded-button px-8 py-3 font-medium text-base hover:border-ink/40 transition-colors"
              >
                Log In
              </Link>
            </div>
          </AnimatedSection>

          <AnimatedSection variant="fadeIn" delay={0.5}>
            <p className="mt-6 text-xs text-ink/40">
              No credit card required · Unlimited events during beta
            </p>
          </AnimatedSection>
        </div>
      </section>

      {/* ─── How It Works ─── */}
      <section className="border-t border-ink/10 bg-lifted">
        <div className="max-w-5xl mx-auto px-6 py-20 md:py-28">
          <AnimatedSection variant="slideUp" className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight mb-4">
              How it works
            </h2>
            <p className="text-ink/50 max-w-lg mx-auto">
              Three steps. Thousands of photos delivered to the right people.
            </p>
          </AnimatedSection>

          <div className="grid md:grid-cols-3 gap-10 md:gap-12">
            {steps.map((step, index) => (
              <AnimatedSection
                key={step.title}
                variant="slideUp"
                delay={index * 0.15}
                className="text-center"
              >
                <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-ink/5 mb-5">
                  <step.icon size={24} strokeWidth={1.5} className="text-ink/70" />
                </div>
                <div className="text-xs font-semibold text-signal mb-2 tracking-widest uppercase">
                  Step {index + 1}
                </div>
                <h3 className="text-lg font-semibold mb-2">{step.title}</h3>
                <p className="text-sm text-ink/50 leading-relaxed max-w-xs mx-auto">
                  {step.description}
                </p>
              </AnimatedSection>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Value Proposition ─── */}
      <section className="border-t border-ink/10">
        <div className="max-w-5xl mx-auto px-6 py-20 md:py-28">
          <AnimatedSection variant="slideUp" className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight mb-4">
              Built for professional photographers
            </h2>
            <p className="text-ink/50 max-w-lg mx-auto">
              Every photo, every guest, every time.
            </p>
          </AnimatedSection>

          <div className="grid md:grid-cols-3 gap-8">
            {features.map((feature, index) => (
              <AnimatedSection
                key={feature.title}
                variant="scaleIn"
                delay={index * 0.1}
              >
                <div className="bg-lifted rounded-2xl p-8 border border-ink/5 h-full">
                  <div className="inline-flex items-center justify-center w-11 h-11 rounded-xl bg-signal/10 mb-5">
                    <feature.icon size={20} strokeWidth={1.5} className="text-signal" />
                  </div>
                  <h3 className="text-base font-semibold mb-2">{feature.title}</h3>
                  <p className="text-sm text-ink/50 leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              </AnimatedSection>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Final CTA ─── */}
      <section className="border-t border-ink/10 bg-ink">
        <div className="max-w-3xl mx-auto px-6 py-20 md:py-28 text-center">
          <AnimatedSection variant="slideUp">
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-canvas mb-4">
              Ready to elevate your studio?
            </h2>
            <p className="text-canvas/50 max-w-md mx-auto mb-8 leading-relaxed">
              Join photographers who deliver unforgettable guest experiences. Set up your first event in minutes.
            </p>
            <Link
              href="/register"
              className="inline-block bg-signal text-white rounded-button px-10 py-3.5 font-semibold text-base hover:bg-signal-light transition-colors"
            >
              Create Free Account
            </Link>
          </AnimatedSection>
        </div>
      </section>
    </>
  );
}
