import { AskForm } from "@/components/AskForm";
import { DiscoveryPanel } from "@/components/DiscoveryPanel";

export default function AskPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Ask vanta</h1>
        <p className="mt-1 text-sm text-ink-2">
          Pose any future event as a question. The full agent pipeline — research, quant, market,
          sentiment, historian, skeptic, synthesis — deliberates and returns a probability with its
          reasoning and risks.
        </p>
      </div>
      <AskForm />
      <div className="mt-6 space-y-1.5 text-xs text-muted">
        <p>Examples:</p>
        <p>· &quot;Will the Fed cut rates before the December meeting?&quot;</p>
        <p>· &quot;Will AGI happen before 2035?&quot;</p>
        <p>· &quot;Will Apple stock rise after its next earnings report?&quot;</p>
      </div>
      <DiscoveryPanel />
    </div>
  );
}
