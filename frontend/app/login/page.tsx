"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";
import Link from "next/link";
import { ArrowRight, Mail } from "lucide-react";
import AuthShell from "@/components/AuthShell";
import PasswordField from "@/components/PasswordField";

export default function LoginPage() {
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
      const { accessToken } = await api.login(email, password);
      setToken(accessToken);
      router.push("/cvs");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return <AuthShell mode="login">
    <h2>Welcome back.</h2>
    <p className="auth-panel-intro">Your application workspace is ready when you are.</p>
    <form onSubmit={handleSubmit} className="auth-form">
      <div><label className="field-label" htmlFor="login-email">Email address</label><div className="input-wrap"><Mail size={16} aria-hidden="true" /><input id="login-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="you@company.com" /></div></div>
      <div><label className="field-label" htmlFor="login-password">Password</label><PasswordField value={password} onChange={setPassword} /></div>
      {error && <p className="form-error">{error}</p>}
      <button type="submit" disabled={loading} className="auth-submit"><span>{loading ? "Opening workspace..." : "Log in"}</span><ArrowRight size={17} aria-hidden="true" /></button>
    </form>
    <p className="auth-panel-foot">New to Curatyn? <Link href="/signup">Create your workspace</Link></p>
  </AuthShell>;
}
