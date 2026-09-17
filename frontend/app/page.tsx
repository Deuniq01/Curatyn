import Link from "next/link";
import { Mail, ShieldCheck, Sparkles, FileText } from "lucide-react";

export default function LandingPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-20">
      <h1 className="text-4xl font-semibold tracking-tight text-neutral-900">
        Apply to jobs faster, without losing the personal touch.
      </h1>
      <p className="mt-4 text-lg text-neutral-600">
        Paste a job description. Curatyn matches your best CV, writes a
        tailored cover letter, and lets you review everything before a
        single email goes out.
      </p>

      <div className="mt-8 flex gap-3">
        <Link href="/signup" className="rounded-md bg-neutral-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-neutral-800">
          Get started
        </Link>
        <Link href="/login" className="rounded-md border border-neutral-300 px-5 py-2.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50">
          Log in
        </Link>
      </div>

      <section className="mt-16 grid gap-8 sm:grid-cols-3">
        <div>
          <FileText className="h-5 w-5 text-neutral-500" aria-hidden="true" />
          <h3 className="mt-3 text-sm font-medium text-neutral-900">Your CVs, matched</h3>
          <p className="mt-1 text-sm text-neutral-600">Upload your CVs once. Curatyn ranks them against every job you consider.</p>
        </div>
        <div>
          <Sparkles className="h-5 w-5 text-neutral-500" aria-hidden="true" />
          <h3 className="mt-3 text-sm font-medium text-neutral-900">A cover letter that fits</h3>
          <p className="mt-1 text-sm text-neutral-600">Generated from the actual posting and your actual experience, not a template.</p>
        </div>
        <div>
          <ShieldCheck className="h-5 w-5 text-neutral-500" aria-hidden="true" />
          <h3 className="mt-3 text-sm font-medium text-neutral-900">You approve every send</h3>
          <p className="mt-1 text-sm text-neutral-600">Nothing goes out until you review and confirm it. No inbox reading required.</p>
        </div>
      </section>

      <section className="mt-16 rounded-lg border border-neutral-200 p-6">
        <div className="flex items-center gap-2 text-sm font-medium text-neutral-900">
          <Mail className="h-4 w-4" aria-hidden="true" />
          How it works
        </div>
        <ol className="mt-3 space-y-2 text-sm text-neutral-600">
          <li>1. Paste or screenshot a job description.</li>
          <li>2. Curatyn recommends the best matching CV from your vault.</li>
          <li>3. Review the generated cover letter and email, edit anything.</li>
          <li>4. Send directly through your connected Gmail or Outlook, or save as a draft.</li>
        </ol>
      </section>
    </main>
  );
}
