"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Trash2, Upload, FileText, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";

type Cv = { id: string; label: string; createdAt: string };

export default function CvVaultPage() {
  const [cvs, setCvs] = useState<Cv[]>([]);
  const [label, setLabel] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.listCvs().then(setCvs).catch((e) => setError(e.message));

  useEffect(() => {
    load();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !label) return;
    setUploading(true);
    setError(null);
    try {
      await api.uploadCv(label, file);
      setLabel("");
      setFile(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <main className="mx-auto max-w-xl px-6 py-16">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-neutral-900">CV Vault</h1>
        <Link href="/apply" className="flex items-center gap-1 text-sm font-medium text-neutral-700 hover:text-neutral-900">
          Apply to a job <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      </div>

      <form onSubmit={handleUpload} className="mb-8 rounded-lg border border-neutral-200 p-4">
        <div className="mb-3">
          <label className="text-xs text-neutral-500">Label</label>
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. Frontend Developer CV"
            className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm outline-none focus:border-neutral-500"
          />
        </div>
        <div className="mb-3">
          <label className="text-xs text-neutral-500">File (PDF)</label>
          <input
            type="file"
            accept=".pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="mt-1 w-full text-sm"
          />
        </div>
        {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={uploading || !file || !label}
          className="flex items-center gap-2 rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 disabled:opacity-50"
        >
          <Upload className="h-4 w-4" aria-hidden="true" />
          {uploading ? "Uploading..." : "Upload CV"}
        </button>
      </form>

      <div className="space-y-2">
        {cvs.length === 0 && <p className="text-sm text-neutral-500">No CVs yet. Upload one to get started.</p>}
        {cvs.map((cv) => (
          <div key={cv.id} className="flex items-center justify-between rounded-md border border-neutral-200 px-4 py-3">
            <div className="flex items-center gap-2 text-sm text-neutral-900">
              <FileText className="h-4 w-4 text-neutral-400" aria-hidden="true" />
              {cv.label}
            </div>
            <button
              onClick={() => api.deleteCv(cv.id).then(load)}
              aria-label={`Delete ${cv.label}`}
              className="text-neutral-400 hover:text-red-600"
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        ))}
      </div>
    </main>
  );
}
