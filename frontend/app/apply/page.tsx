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
    <main className="workspace-page">
      <div className="workspace-header"><div><div className="workspace-kicker">Workspace / 02</div><h1 className="workspace-title">Make your case.</h1><p className="workspace-intro">
        Curatyn will analyze it, match it against your CV Vault, and draft a cover letter and email for you to review.
      </p></div></div>

      <form onSubmit={handleSubmit} className="workspace-card">
        <textarea
          required
          value={rawInput}
          onChange={(e) => setRawInput(e.target.value)}
          placeholder="Paste the full job posting here..."
          className="workspace-textarea"
        />
        {error && <p className="form-error mt-3">{error}</p>}
        <button
          type="submit"
          disabled={status !== "idle" || !rawInput.trim()}
          className="workspace-button mt-4 disabled:opacity-50"
        >
          {status === "idle" && (<><Send className="h-4 w-4" aria-hidden="true" /> Analyze & Match</>)}
          {status === "analyzing" && (<><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Analyzing job description...</>)}
          {status === "matching" && (<><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Matching your best CV...</>)}
        </button>
      </form>
    </main>
  );
}
