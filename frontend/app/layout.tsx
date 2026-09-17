import type { Metadata } from "next";
import "./globals.css";
import AppChrome from "@/components/AppChrome";

export const metadata: Metadata = {
  title: "Curatyn",
  description: "AI-powered job application assistant",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col font-sans"><AppChrome>{children}</AppChrome></body>
    </html>
  );
}
