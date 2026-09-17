"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ImagePlus, Loader2, Send, Type } from "lucide-react";
import { api } from "@/lib/api";

export default function ApplyPage() {
  const router = useRouter();
  const [rawInput, setRawInput] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [status, setStatus] = useState<"idle" | "analyzing" | "matching">("idle");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setStatus("analyzing");
    try {
      const jd = await api.submitJobDescriptionCombined(rawInput, imageFile);
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
        <div className="combined-input-heading"><Type size={16} /> <span>Job description</span><small>Paste text, add a screenshot, or use both</small></div>
        <textarea value={rawInput} onChange={(e) => setRawInput(e.target.value)} placeholder="Paste the full job posting here..." className="workspace-textarea" />
        <label className="image-upload-zone"><ImagePlus size={26} /><strong>{imageFile ? imageFile.name : "Add a job posting screenshot"}</strong><span>Optional · PNG, JPEG, or WebP up to 10 MB</span><input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setImageFile(e.target.files?.[0] || null)} /></label>
        {error && <p className="form-error mt-3">{error}</p>}
        <button
          type="submit"
          disabled={status !== "idle" || (!rawInput.trim() && !imageFile)}
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
