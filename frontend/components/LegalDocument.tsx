import Link from "next/link";
import Image from "next/image";

type Section = { title: string; children: React.ReactNode };

type LegalDocumentProps = {
  title: string;
  lastUpdated: string;
  intro: React.ReactNode;
  sections: Section[];
};

export default function LegalDocument({ title, lastUpdated, intro, sections }: LegalDocumentProps) {
  return (
    <main className="legal-page">
      <header className="legal-header">
        <Link href="/" className="landing-logo" aria-label="Curatyn home"><Image src="/logo.png" alt="Curatyn" width={142} height={70} priority /></Link>
        <nav><Link href="/">Home</Link><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><Link href="/login">Log in</Link></nav>
      </header>
      <article className="legal-document">
        <p className="landing-kicker">Curatyn / Legal</p>
        <h1>{title}</h1>
        <p className="legal-updated">Last updated: {lastUpdated}</p>
        <div className="legal-intro">{intro}</div>
        {sections.map((section, index) => <section key={section.title}><p className="legal-index">{String(index + 1).padStart(2, "0")}</p><div><h2>{section.title}</h2>{section.children}</div></section>)}
      </article>
      <footer className="legal-footer"><span>Curatyn</span><span>Apply with intention.</span><Link href="/">Back to Curatyn <span aria-hidden="true">↗</span></Link></footer>
    </main>
  );
}
