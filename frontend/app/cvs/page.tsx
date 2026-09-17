"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Trash2, Upload, FileText, ArrowRight, Mail } from "lucide-react";
import { api } from "@/lib/api";

type Cv = { id: string; label: string; createdAt: string };

export default function CvVaultPage() {
  const [cvs, setCvs] = useState<Cv[]>([]);
  const [label, setLabel] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [emailProvider, setEmailProvider] = useState<string | null>(null);
  const [emailAccount, setEmailAccount] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const load = () => api.listCvs().then(setCvs).catch((e) => setError(e.message));
  const loadMe = () =>
    api
      .me()
      .then((m) => {
        setEmailProvider(m.emailProvider ?? null);
        setEmailAccount(m.emailProviderAccountId ?? null);
      })
      .catch(() => {});

  useEffect(() => {
    load();
    loadMe();

    // Surface the result of the OAuth redirect (?connected=gmail or ?email_error=...)
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("connected");
    const emailError = params.get("email_error");
    if (connected) setTimeout(() => setNotice({ kind: "ok", text: `Connected ${connected} for sending.` }), 0);
    else if (emailError) setTimeout(() => setNotice({ kind: "err", text: `Couldn't connect email: ${emailError}` }), 0);
    if (connected || emailError) window.history.replaceState({}, "", "/cvs");
  }, []);

  const connectGmail = async () => {
    try {
      await api.connectEmailProvider("gmail");
    } catch (err) {
      setNotice({ kind: "err", text: err instanceof Error ? err.message : "Could not start Gmail connection" });
    }
  };

  const disconnectEmail = async () => {
    await api.disconnectEmailProvider().catch(() => {});
    await loadMe();
    setNotice({ kind: "ok", text: "Email disconnected." });
  };

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
    <main className="workspace-page">
      <div className="workspace-header">
        <div><div className="workspace-kicker">Workspace / 01</div><h1 className="workspace-title">Your CV vault.</h1><p className="workspace-intro">Keep the versions of your experience close. Curatyn will surface the one that fits when you are ready to apply.</p></div>
        <Link href="/apply" className="workspace-button"><ArrowRight className="h-4 w-4" aria-hidden="true" /> Start an application
        </Link>
      </div>

      {notice && (
        <p className={`mb-4 rounded-md px-3 py-2 text-sm ${notice.kind === "ok" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>
          {notice.text}
        </p>
      )}

      <div className="workspace-card mb-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-neutral-900">
            <Mail className="h-4 w-4 text-neutral-400" aria-hidden="true" />
            {emailProvider ? (
              <span>
                Sending as <span className="font-medium">{emailAccount || emailProvider}</span>
              </span>
            ) : (
              <span className="text-neutral-500">Connect an email account to send applications.</span>
            )}
          </div>
          {emailProvider ? (
            <button onClick={disconnectEmail} className="text-sm font-medium text-neutral-500 hover:text-red-600">
              Disconnect
            </button>
          ) : (
            <button
              onClick={connectGmail}
              className="flex items-center gap-2 rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
            >
              <Mail className="h-4 w-4" aria-hidden="true" />
              Connect Gmail
            </button>
          )}
        </div>
      </div>

      <form onSubmit={handleUpload} className="workspace-card mb-5">
        <div className="mb-3">
          <label className="text-xs text-neutral-500">Label</label>
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. Frontend Developer CV"
            className="workspace-input mt-1"
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
        {error && <p className="form-error mb-3">{error}</p>}
        <button
          type="submit"
          disabled={uploading || !file || !label}
          className="workspace-button disabled:opacity-50"
        >
          <Upload className="h-4 w-4" aria-hidden="true" />
          {uploading ? "Uploading..." : "Upload CV"}
        </button>
      </form>

      <div className="workspace-list">
        {cvs.length === 0 && <div className="workspace-card"><p>No CVs yet. Upload one to get started.</p></div>}
        {cvs.map((cv) => (
          <div key={cv.id} className="workspace-list-item">
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
