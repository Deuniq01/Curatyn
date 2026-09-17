"use client";

import { Eye, EyeOff, LockKeyhole } from "lucide-react";
import { useState } from "react";

export default function PasswordField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [visible, setVisible] = useState(false);
  return <div className="password-wrap"><LockKeyhole size={16} aria-hidden="true" /><input type={visible ? "text" : "password"} required minLength={8} value={value} onChange={(event) => onChange(event.target.value)} autoComplete="current-password" /><button type="button" className="password-toggle" onClick={() => setVisible((current) => !current)} aria-label={visible ? "Hide password" : "Show password"}>{visible ? <EyeOff size={17} aria-hidden="true" /> : <Eye size={17} aria-hidden="true" />}</button></div>;
}