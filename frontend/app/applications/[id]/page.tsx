"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import FinalReviewScreen, { SendConfirmationModal } from "@/components/FinalReviewScreen.jsx";
import { api } from "@/lib/api";

type Application = {
  id: string;
  status: string;
  companyName: string | null;
  roleTitle: string | null;
  recipientEmail: string | null;
  emailSubject: string | null;
  coverLetter: string | null;
  selectedCvLabel: string | null;
  lastSendError: string | null;
};

export default function ApplicationReviewPage() {
  const params = useParams<{ id: string }>();
  const applicationId = params.id;

  const [application, setApplication] = useState<Application | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // One idempotency key per confirmation-modal open; reused on retry of the
  // SAME attempt, replaced when the user opens the modal fresh after a
  // successful send/failure cycle resets it (PRD Section 22 / 03-api-design.md).
  const idempotencyKeyRef = useRef<string | null>(null);

  const load = () => api.getApplication(applicationId).then(setApplication).catch((e) => setError(e.message));

  useEffect(() => {
    load();
    // The loader is intentionally scoped to the current application id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applicationId]);

  if (!application) {
    return <main className="mx-auto max-w-xl px-6 py-16 text-sm text-neutral-500">{error || "Loading..."}</main>;
  }

  const handleSaveField = async (field: string, value: string) => {
    const fieldMap: Record<string, string> = {
      recipientEmail: "recipientEmail",
      emailSubject: "emailSubject",
      coverLetter: "coverLetter",
    };
    setApplication((prev) => prev ? { ...prev, [field]: value } as Application : prev);

    if (field === "coverLetter") {
      await api.editCoverLetter(applicationId, value);
    } else {
      await api.updateApplication(applicationId, { [fieldMap[field]]: value });
    }
  };

  const handleRegenerateCoverLetter = async () => {
    const updated = await api.regenerateCoverLetter(applicationId);
    setApplication(updated);
  };

  const handleSaveDraft = async () => {
    const key = crypto.randomUUID();
    const result = await api.draftApplication(applicationId, key);
    await load();
    return result;
  };

  const openSendConfirmation = () => {
    idempotencyKeyRef.current = crypto.randomUUID();
    setShowConfirm(true);
  };

  const confirmSend = async () => {
    setSending(true);
    try {
      const key = idempotencyKeyRef.current || crypto.randomUUID();
      await api.sendApplication(applicationId, key);
      await load();
      setShowConfirm(false);
    } finally {
      setSending(false);
    }
  };

  return (
    <main className="px-6 py-16">
      <FinalReviewScreen
        application={application}
        onSaveField={handleSaveField}
        onRegenerateCoverLetter={handleRegenerateCoverLetter}
        onOpenSendConfirmation={openSendConfirmation}
        onSaveDraft={handleSaveDraft}
      />
      {showConfirm && (
        <SendConfirmationModal
          application={application}
          sending={sending}
          onCancel={() => setShowConfirm(false)}
          onConfirmSend={confirmSend}
        />
      )}
    </main>
  );
}
