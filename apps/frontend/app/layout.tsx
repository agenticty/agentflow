import Link from "next/link";
import "./globals.css"; // <- add this line

export const metadata = {
  title: "AgentFlow",
  description: "Multi-agent workflow automation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-screen bg-zinc-50 text-zinc-900">
        <div className="border-b bg-white/70 backdrop-blur supports-[backdrop-filter]:bg-white/60 sticky top-0 z-50">
          <div className="mx-auto max-w-6xl px-4 h-14 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <div className="size-7 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow" />
              <span className="font-semibold tracking-tight">AgentFlow</span>
            </Link>
            <nav className="flex items-center gap-6 text-sm">
              {/*<a href="/docs" className="hover:text-indigo-600">Docs</a>*/}
              <a href="/settings" className="hover:text-indigo-600">Settings</a>
              <a href="/app" className="inline-flex items-center rounded-lg bg-indigo-600 px-3 py-1.5 text-white hover:bg-indigo-700 transition">
                Open App
              </a>
            </nav>
          </div>
        </div>
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 py-10 text-sm text-zinc-500">
          © {new Date().getFullYear()} AgentFlow
        </footer>
      </body>
    </html>
  );
}

