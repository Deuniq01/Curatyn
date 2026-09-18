"use client";

import { useState } from "react";
import {
  Building2,
  Briefcase,
  Mail,
  FileText,
  Paperclip,
  Edit3,
  Send,
  Save,
  X,
  CheckCircle,
  AlertTriangle,
  Loader2,
} from "lucide-react";

/**
 * Component tree:
 *
 * FinalReviewScreen
 *  ├─ ReviewGateNotice            — visible while READY_FOR_REVIEW / USER_REVIEWING
 *  ├─ ReviewField (Company)
 *  ├─ ReviewField (Role)
 *  ├─ ReviewField (To)            — editable
 *  ├─ ReviewField (Subject)       — editable
 *  ├─ ReviewField (CV attachment)
 *  ├─ CoverLetterPanel            — editable textarea + regenerate action
 *  ├─ FailureBanner               — SEND_FAILED and DRAFT_CREATION_FAILED
 *  └─ ActionBar
 *      ├─ Save as Draft button
 *      └─ Send Application button → opens SendConfirmationModal
 *
 * Both action buttons are disabled unless the status is one the server will
 * accept, so a gated state is shown rather than discovered by clicking.
 *
 * SendConfirmationModal (separate file below in this same document)
 */

function ReviewField({ icon: Icon, label, value, editable, onChange }) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-neutral-200">
      <Icon className="mt-0.5 h-4 w-4 text-neutral-400" aria-hidden="true" />
      <div className="flex-1 min-w-0">
        <div className="text-xs text-neutral-500">{label}</div>
        {editable ? (
          <input
            className="mt-1 w-full bg-transparent text-sm text-neutral-900 outline-none border-b border-transparent focus:border-neutral-300"
            value={value}
            onChange={(e) => onChange(e.target.value)}
          />
        ) : (
          <div className="mt-1 text-sm text-neutral-900 truncate">{value}</div>
        )}
      </div>
    </div>
  );
}

function CoverLetterPanel({ coverLetter, onChange, onRegenerate, regenerating }) {
  return (
    <div className="py-4 border-b border-neutral-200">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 text-xs text-neutral-500">
          <FileText className="h-4 w-4" aria-hidden="true" />
          Cover Letter
        </div>
        <button
          type="button"
          onClick={onRegenerate}
          disabled={regenerating}
          className="flex items-center gap-1 text-xs text-neutral-600 hover:text-neutral-900 disabled:opacity-50"
        >
          {regenerating ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <Edit3 className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          Regenerate
        </button>
      </div>
      <textarea
        className="w-full min-h-[220px] resize-y rounded-md border border-neutral-200 bg-neutral-50 p-3 text-sm leading-relaxed text-neutral-900 outline-none focus:border-neutral-400"
        value={coverLetter}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

function FailureBanner({ title, message, retryLabel, onRetry }) {
  return (
    <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-4">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 text-red-600" aria-hidden="true" />
        <div className="flex-1">
          <p className="text-sm font-medium text-red-800">{title}</p>
          {message && <p className="mt-1 text-sm text-red-700">{message}</p>}
          <div className="mt-3">
            <button
              type="button"
              onClick={onRetry}
              className="rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700"
            >
              {retryLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * The review gate, made visible. A generated application stops at
 * READY_FOR_REVIEW and the server will not send or draft from there — which used
 * to be indistinguishable from a broken button. This states the gate and
 * provides the one action that clears it.
 */
function ReviewGateNotice({ application, onMarkReviewed }) {
  if (application.status === "READY_FOR_REVIEW") {
    return (
      <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-4">
        <div className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-600" aria-hidden="true" />
          <div className="flex-1">
            <p className="text-sm font-medium text-amber-900">This application still needs your review.</p>
            <p className="mt-1 text-sm text-amber-800">
              Everything below was generated for you. Read it over, then mark it as reviewed to unlock
              sending and drafts.
            </p>
            <button
              type="button"
              onClick={onMarkReviewed}
              className="mt-3 flex items-center gap-2 rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
            >
              <CheckCircle className="h-3.5 w-3.5" aria-hidden="true" />
              Mark as reviewed
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (application.status === "USER_REVIEWING") {
    return (
      <div className="mb-4 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-4">
        <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-600" aria-hidden="true" />
        <p className="text-sm text-amber-800">
          Still missing: {(application.missingFields || []).join(", ") || "some fields"}. Fill these in to
          unlock sending.
        </p>
      </div>
    );
  }

  return null;
}

// Mirrors CLAIMABLE_STATUSES in backend/app/idempotency.py — the states the
// server will accept a send or a draft from. Anything outside this set has an
// action that would be refused, so the buttons are disabled rather than left to
// fail on click.
const SENDABLE_STATUSES = new Set([
  "READY_TO_SEND",
  "SEND_FAILED",
  "DRAFT_CREATED",
  "DRAFT_CREATION_FAILED",
]);

export default function FinalReviewScreen({ application, onSaveField, onRegenerateCoverLetter, onOpenSendConfirmation, onSaveDraft, onMarkReviewed }) {
  const [regenerating, setRegenerating] = useState(false);
  const canAct = SENDABLE_STATUSES.has(application.status);

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      await onRegenerateCoverLetter();
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <div className="mx-auto max-w-xl rounded-lg border border-neutral-200 bg-white p-6">
      <h1 className="mb-4 text-lg font-semibold text-neutral-900">Review Application</h1>

      <ReviewGateNotice application={application} onMarkReviewed={onMarkReviewed} />

      {application.status === "SEND_FAILED" && (
        <FailureBanner
          title="Send failed. Your application has not been sent."
          message={application.lastSendError}
          retryLabel="Try Again"
          onRetry={onOpenSendConfirmation}
        />
      )}

      {application.status === "DRAFT_CREATION_FAILED" && (
        <FailureBanner
          title="Your draft was not created."
          message={application.lastSendError}
          retryLabel="Try Draft Again"
          onRetry={onSaveDraft}
        />
      )}

      {application.status === "DRAFT_CREATED" && (
        <p className="mb-4 rounded-md border border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-600">
          A draft of this application is already in your mailbox. You can still send it from here.
        </p>
      )}

      <ReviewField icon={Building2} label="Company" value={application.companyName} editable={false} />
      <ReviewField icon={Briefcase} label="Role" value={application.roleTitle} editable={false} />
      <ReviewField
        icon={Mail}
        label="To"
        value={application.recipientEmail}
        editable
        onChange={(value) => onSaveField("recipientEmail", value)}
      />
      <ReviewField
        icon={FileText}
        label="Subject"
        value={application.emailSubject}
        editable
        onChange={(value) => onSaveField("emailSubject", value)}
      />
      <ReviewField
        icon={Paperclip}
        label="CV"
        value={`${application.selectedCvLabel}.pdf`}
        editable={false}
      />

      <CoverLetterPanel
        coverLetter={application.coverLetter}
        onChange={(value) => onSaveField("coverLetter", value)}
        onRegenerate={handleRegenerate}
        regenerating={regenerating}
      />

      <div className="mt-4 flex justify-end gap-3">
        <button
          type="button"
          onClick={onSaveDraft}
          disabled={!canAct}
          className="flex items-center gap-2 rounded-md border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
        >
          <Save className="h-4 w-4" aria-hidden="true" />
          Save as Draft
        </button>
        <button
          type="button"
          onClick={onOpenSendConfirmation}
          disabled={!canAct}
          className="flex items-center gap-2 rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-neutral-900"
        >
          <Send className="h-4 w-4" aria-hidden="true" />
          Send Application
        </button>
      </div>
    </div>
  );
}

export function SendConfirmationModal({ application, sending, onCancel, onConfirmSend }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-neutral-900">Confirm Application</h2>
          <button type="button" onClick={onCancel} aria-label="Close">
            <X className="h-4 w-4 text-neutral-400 hover:text-neutral-600" aria-hidden="true" />
          </button>
        </div>

        <p className="mb-4 text-sm text-neutral-600">You are about to send:</p>

        <div className="space-y-2 rounded-md bg-neutral-50 p-3 text-sm">
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-neutral-400" aria-hidden="true" />
            <span className="text-neutral-500">To:</span>
            <span className="text-neutral-900">{application.recipientEmail}</span>
          </div>
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-neutral-400" aria-hidden="true" />
            <span className="text-neutral-500">Subject:</span>
            <span className="text-neutral-900">{application.emailSubject}</span>
          </div>
          <div className="flex items-center gap-2">
            <Paperclip className="h-4 w-4 text-neutral-400" aria-hidden="true" />
            <span className="text-neutral-500">Attachment:</span>
            <span className="text-neutral-900">{application.selectedCvLabel}.pdf</span>
          </div>
        </div>

        <p className="mt-4 text-xs text-neutral-500">
          Once sent, this email cannot be recalled by Curatyn.
        </p>

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={sending}
            className="rounded-md border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirmSend}
            disabled={sending}
            className="flex items-center gap-2 rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 disabled:opacity-50"
          >
            {sending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                Sending application...
              </>
            ) : (
              <>
                <CheckCircle className="h-4 w-4" aria-hidden="true" />
                Confirm & Send
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
