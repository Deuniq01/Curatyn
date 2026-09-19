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
  draftId: string | null;
  // Names of the fields the backend still needs before this can be sent. Empty
  // means complete. Reported by the server so the UI never restates the rule.
  missingFields: string[];
};

// How long typing has to pause before an edit is written to the server.
//
// Every keystroke used to fire its own PUT. With two writes in flight an
// earlier one could land last and leave the server holding text the user had
// already moved past — so sending straight after typing could mail that
// version, not the one on screen. Edits are now debounced, written one after
// another, and flushed before anything reads them back.
const SAVE_DEBOUNCE_MS = 600;

export default function ApplicationReviewPage() {
  const params = useParams<{ id: string }>();
  const applicationId = params.id;

  const [application, setApplication] = useState<Application | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editsPending, setEditsPending] = useState(false);

  // One idempotency key per confirmation-modal open; reused on retry of the
  // SAME attempt, replaced when the user opens the modal fresh after a
  // successful send/failure cycle resets it (PRD Section 22 / 03-api-design.md).
  const idempotencyKeyRef = useRef<string | null>(null);

  // Latest value per field that has not reached the server yet. A map rather
  // than a single slot: filling in the recipient and the letter in one burst
  // has to write both.
  const pendingRef = useRef<Record<string, string>>({});
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Writes queue onto this chain, so they reach the server in the order the
  // user made them however they overlap.
  const writeChainRef = useRef<Promise<unknown>>(Promise.resolve());

  const load = () => api.getApplication(applicationId).then(setApplication).catch((e) => setError(e.message));

  const writeField = async (field: string, value: string) => {
    if (field === "coverLetter") {
      await api.editCoverLetter(applicationId, value);
    } else {
      await api.updateApplication(applicationId, { [field]: value });
    }
  };

  const enqueueWrite = (field: string, value: string) => {
    const next = writeChainRef.current.then(() => writeField(field, value));
    // Swallow the rejection on the chain itself so one failure does not poison
    // every write queued behind it. The caller still sees `next` reject.
    writeChainRef.current = next.catch(() => {});
    return next;
  };

  /** Writes everything still pending, and resolves once the server has it all.
   *
   * Rejects if a write failed, putting the failed value back in the pending map.
   * A caller that is about to send must not continue past a rejection — the mail
   * would carry whatever the server last accepted, not what is on screen. */
  const flushEdits = async () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    const entries = Object.entries(pendingRef.current);
    if (entries.length === 0) return;

    pendingRef.current = {};
    setEditsPending(false);
    try {
      await Promise.all(
        entries.map(async ([field, value]) => {
          try {
            await enqueueWrite(field, value);
          } catch (e) {
            // Still unsaved. Keep it pending so the next attempt retries it
            // rather than quietly sending the older text.
            pendingRef.current[field] = value;
            throw e;
          }
        })
      );
    } catch (e) {
      setEditsPending(true);
      setError(e instanceof Error ? e.message : "Could not save your edits.");
      throw e;
    }
  };

  useEffect(() => {
    load();
    // The loader is intentionally scoped to the current application id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applicationId]);

  useEffect(() => {
    // Leaving with an edit still queued would drop it silently, so write it out
    // rather than lose it. Closing over refs is what makes this safe to run
    // from a cleanup: the pending map and the chain outlive the render.
    return () => {
      flushEdits().catch(() => {});
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applicationId]);

  const handleSaveField = (field: string, value: string) => {
    // Optimistic — the field shows the keystroke immediately, and the write
    // follows once typing pauses.
    setApplication((prev) => (prev ? ({ ...prev, [field]: value } as Application) : prev));
    pendingRef.current[field] = value;
    setEditsPending(true);

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      flushEdits().catch(() => {}); // the reason is already on screen
    }, SAVE_DEBOUNCE_MS);
  };

  if (!application) {
    return <main className="mx-auto max-w-xl px-6 py-16 text-sm text-neutral-500">{error || "Loading..."}</main>;
  }

  const handleRegenerateCoverLetter = async () => {
    setError(null);
    try {
      // The regenerated letter replaces whatever is pending, so the queued edit
      // goes out first. Left in the queue it would land afterwards and restore
      // the text the regeneration just discarded.
      await flushEdits();
      setApplication(await api.regenerateCoverLetter(applicationId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not regenerate the cover letter.");
    }
  };

  const handleSaveDraft = async () => {
    setError(null);
    try {
      // Same rule as sending: the draft has to contain the text on screen.
      await flushEdits();
      const key = crypto.randomUUID();
      const result = await api.draftApplication(applicationId, key);
      await load();
      if (result?.status === "DRAFT_CREATION_FAILED") {
        setError(result.error || "Could not save the draft.");
      }
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save the draft.");
    }
  };

  const openSendConfirmation = () => {
    idempotencyKeyRef.current = crypto.randomUUID();
    setShowConfirm(true);
  };

  const handleMarkReviewed = async () => {
    setError(null);
    try {
      // The PUT recomputes readiness from the stored row, so a pending edit has
      // to be saved first or the decision is made against stale text.
      await flushEdits();
      await api.markReviewed(applicationId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not mark this application as reviewed.");
    }
  };

  const confirmSend = async () => {
    setSending(true);
    setError(null);
    try {
      // Flushing here rather than on every keystroke is what guarantees the
      // mail matches the screen. On rejection the send does not happen.
      await flushEdits();
      const key = idempotencyKeyRef.current || crypto.randomUUID();
      await api.sendApplication(applicationId, key);
      await load();
      setShowConfirm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not send the application.");
      setShowConfirm(false);
    } finally {
      setSending(false);
    }
  };

  return (
    <main className="px-6 py-16">
      {error && (
        <div className="mx-auto mb-4 max-w-xl rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {!error && editsPending && (
        <p role="status" className="mx-auto mb-4 max-w-xl text-xs text-neutral-500">
          Saving your edits…
        </p>
      )}
      <FinalReviewScreen
        application={application}
        onSaveField={handleSaveField}
        onRegenerateCoverLetter={handleRegenerateCoverLetter}
        onOpenSendConfirmation={openSendConfirmation}
        onSaveDraft={handleSaveDraft}
        onMarkReviewed={handleMarkReviewed}
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
