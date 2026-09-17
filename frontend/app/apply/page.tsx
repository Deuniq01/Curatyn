"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Send } from "lucide-react";
import { api } from "@/lib/api";

export default function ApplyPage() {
  const router = useRouter();
  const [rawInput, setRawInput] = useState("");
  const [status, setStatus] = useState<"idle" | "analyzing" | "matching">("idle");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setStatus("analyzing");
    try {
      const jd = await api.submitJobDescription(rawInput);
      setStatus("matching");
      const application = await api.createApplication(jd.id);
      router.push(`/applications/${application.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setStatus("idle");
    }
  };

  return (
    <main className="mx-auto max-w-xl px-6 py-16">
      <h1 className="mb-2 text-lg font-semibold text-neutral-900">Paste a job description</h1>
      <p className="mb-6 text-sm text-neutral-600">
        Curatyn will analyze it, match it against your CV Vault, and draft a cover letter and email for you to review.
      </p>

      <form onSubmit={handleSubmit}>
        <textarea
          required
          value={rawInput}
          onChange={(e) => setRawInput(e.target.value)}
          placeholder="Paste the full job posting here..."
          className="min-h-[260px] w-full resize-y rounded-md border border-neutral-300 p-3 text-sm outline-none focus:border-neutral-500"
        />
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={status !== "idle" || !rawInput.trim()}
          className="mt-4 flex items-center gap-2 rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 disabled:opacity-50"
        >
          {status === "idle" && (<><Send className="h-4 w-4" aria-hidden="true" /> Analyze & Match</>)}
          {status === "analyzing" && (<><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Analyzing job description...</>)}
          {status === "matching" && (<><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Matching your best CV...</>)}
        </button>
      </form>
    </main>
  );
}
