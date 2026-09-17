"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ArrowUpRight, BriefcaseBusiness, FileText, LogOut, Menu, Sparkles, X } from "lucide-react";

const navItems = [
  { href: "/cvs", label: "CV vault", icon: FileText },
  { href: "/apply", label: "New application", icon: Sparkles },
  { href: "/applications", label: "Applications", icon: BriefcaseBusiness },
];

export default function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const isPublic = pathname === "/" || pathname === "/login" || pathname === "/signup" || pathname === "/privacy" || pathname === "/terms";
  if (isPublic) return <>{children}</>;

  return (
    <div className="app-frame">
      <aside className="app-sidebar">
        <Link href="/cvs" className="workspace-logo" aria-label="Curatyn home"><Image src="/logo.png" alt="Curatyn" width={150} height={76} priority /></Link>
        <div className="sidebar-kicker">Workspace</div>
        <nav className="sidebar-nav" aria-label="Main navigation">
          {navItems.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} className={`sidebar-link ${pathname.startsWith(href) ? "is-active" : ""}`}>
              <Icon size={17} aria-hidden="true" /><span>{label}</span>
              {pathname.startsWith(href) && <ArrowUpRight size={15} aria-hidden="true" />}
            </Link>
          ))}
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-note"><span className="status-pulse" /><div><strong>Private by default</strong><span>Your review stays yours.</span></div></div>
        <Link href="/" className="sidebar-logout"><LogOut size={16} aria-hidden="true" /> Exit workspace</Link>
      </aside>
      <div className="app-content">
        <header className="mobile-header"><Link href="/cvs" className="workspace-logo mobile-logo"><Image src="/logo.png" alt="Curatyn" width={118} height={60} /></Link><div className="mobile-actions"><Link href="/apply" className="mobile-action"><Sparkles size={15} aria-hidden="true" /> New apply</Link><button type="button" className="mobile-menu-button" onClick={() => setMenuOpen((open) => !open)} aria-expanded={menuOpen} aria-controls="mobile-navigation" aria-label={menuOpen ? "Close menu" : "Open menu"}>{menuOpen ? <X size={21} /> : <Menu size={21} />}</button></div></header>
        {menuOpen && <nav id="mobile-navigation" className="mobile-navigation" aria-label="Mobile navigation">{navItems.map(({ href, label, icon: Icon }) => <Link key={href} href={href} className={pathname.startsWith(href) ? "is-active" : ""} onClick={() => setMenuOpen(false)}><Icon size={17} aria-hidden="true" /><span>{label}</span>{pathname.startsWith(href) && <ArrowUpRight size={15} aria-hidden="true" />}</Link>)}<Link href="/" onClick={() => setMenuOpen(false)}><LogOut size={17} aria-hidden="true" /><span>Exit workspace</span></Link></nav>}
        {children}
      </div>
    </div>
  );
}