"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type AppRow = {
  id: string;
  status: string;
  companyName: string | null;
  roleTitle: string | null;
  updatedAt: string;
};

const STATUS_LABEL: Record<string, string> = {
  READY_FOR_REVIEW: "Ready for review",
  READY_TO_SEND: "Ready to send",
  USER_REVIEWING: "In review",
  SENT: "Sent",
  DRAFT_CREATED: "Draft created",
  SEND_FAILED: "Send failed",
  DRAFT_CREATION_FAILED: "Draft creation failed",
  CANCELLED: "Cancelled",
};

export default function ApplicationsHistoryPage() {
  const [applications, setApplications] = useState<AppRow[]>([]);

  useEffect(() => {
    api.listApplications().then(setApplications);
  }, []);

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="mb-6 text-lg font-semibold text-neutral-900">Applications</h1>
      <div className="space-y-2">
        {applications.length === 0 && <p className="text-sm text-neutral-500">No applications yet.</p>}
        {applications.map((a) => (
          <Link
            key={a.id}
            href={`/applications/${a.id}`}
            className="flex items-center justify-between rounded-md border border-neutral-200 px-4 py-3 hover:border-neutral-400"
          >
            <div>
              <div className="text-sm font-medium text-neutral-900">{a.roleTitle || "Untitled role"}</div>
              <div className="text-xs text-neutral-500">{a.companyName || "Unknown company"}</div>
            </div>
            <span className="text-xs text-neutral-500">{STATUS_LABEL[a.status] || a.status}</span>
          </Link>
        ))}
      </div>
    </main>
  );
}
