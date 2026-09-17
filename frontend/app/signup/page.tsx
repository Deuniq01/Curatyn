"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";
import Link from "next/link";
import { ArrowRight, Mail } from "lucide-react";
import AuthShell from "@/components/AuthShell";
import PasswordField from "@/components/PasswordField";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const { accessToken } = await api.signup(email, password);
      setToken(accessToken);
      router.push("/cvs");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setLoading(false);
    }
  };

  return <AuthShell mode="signup">
    <h2>Start clean.</h2>
    <p className="auth-panel-intro">Set up your private workspace and bring your best work with you.</p>
    <form onSubmit={handleSubmit} className="auth-form">
      <div><label className="field-label" htmlFor="signup-email">Email address</label><div className="input-wrap"><Mail size={16} aria-hidden="true" /><input id="signup-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="you@company.com" /></div></div>
      <div><label className="field-label" htmlFor="signup-password">Password <span className="normal-case">/ 8+ characters</span></label><PasswordField value={password} onChange={setPassword} /></div>
      {error && <p className="form-error">{error}</p>}
      <button type="submit" disabled={loading} className="auth-submit"><span>{loading ? "Building workspace..." : "Create workspace"}</span><ArrowRight size={17} aria-hidden="true" /></button>
    </form>
    <p className="auth-panel-foot">Already have a workspace? <Link href="/login">Log in instead</Link></p>
  </AuthShell>;
}
