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
    <main className="workspace-page">
      <div className="workspace-header"><div><div className="workspace-kicker">Workspace / 03</div><h1 className="workspace-title">Your applications.</h1><p className="workspace-intro">A clear record of the roles you are considering, reviewing, and sending into the world.</p></div></div>
      <div className="workspace-list">
        {applications.length === 0 && <div className="workspace-card"><p>No applications yet. Start with a job description when you are ready.</p></div>}
        {applications.map((a) => (
          <Link
            key={a.id}
            href={`/applications/${a.id}`}
            className="workspace-list-item"
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
