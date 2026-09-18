import Link from "next/link";
import Image from "next/image";
import { ArrowUpRight, Check, Sparkles } from "lucide-react";

export default function AuthShell({ mode, children }: { mode: "login" | "signup"; children: React.ReactNode }) {
  const isLogin = mode === "login";
  return (
    <main className="auth-scene">
      <div className="auth-noise" />
      <div className="auth-topbar"><Link href="/" className="auth-logo" aria-label="Curatyn home"><Image src="/logo.png" alt="Curatyn" width={150} height={76} priority /></Link><Link href={isLogin ? "/signup" : "/login"} className="auth-switch">{isLogin ? "Create an account" : "I already have an account"} <ArrowUpRight size={15} aria-hidden="true" /></Link></div>
      <div className="auth-layout">
        <section className="auth-story">
          <div className="eyebrow"><Sparkles size={14} aria-hidden="true" /> Intentional applications</div>
          <h1>{isLogin ? "Your best work, already in motion." : "Make every application feel considered."}</h1>
          <p>{isLogin ? "Pick up where you left off. Your CVs, drafts, and decisions are waiting." : "Curatyn turns the messy middle of job hunting into a clear, reviewable ritual."}</p>
          <div className="auth-proof">{["Your voice stays yours", "Nothing sends without approval", "One calm place for every role"].map((item) => <span key={item}><Check size={14} aria-hidden="true" />{item}</span>)}</div>
          <div className="auth-orbit" aria-hidden="true"><div className="orbit-ring orbit-ring-one" /><div className="orbit-ring orbit-ring-two" /><div className="orbit-core"><span>01</span><strong>apply<br />with intent</strong></div><div className="orbit-card orbit-card-one"><span>Best match</span><strong>Your CV</strong></div><div className="orbit-card orbit-card-two"><span>Before send</span><strong>You approve</strong></div></div>
        </section>
        <section className="auth-panel"><div className="auth-panel-top"><span>{isLogin ? "Welcome back" : "Start your workspace"}</span><span className="panel-index">{isLogin ? "02 / 02" : "01 / 02"}</span></div>{children}</section>
      </div>
      <div className="auth-footer"><span>curatyn — apply with intention</span><span>© 2026</span></div>
    </main>
  );
}