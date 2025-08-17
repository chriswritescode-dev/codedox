import { Outlet, Link, useLocation } from "react-router-dom";
import {
  Home,
  Search,
  Database,
  Briefcase,
  Menu,
  X,
  Upload,
  FileSearch,
} from "lucide-react";
import { useState, useEffect } from "react";
import { DocumentSearchModal } from "./DocumentSearchModal";

const navigation = [
  { name: "Dashboard", href: "/", icon: Home },
  { name: "Search", href: "/search", icon: Search },
  { name: "Sources", href: "/sources", icon: Database },
  { name: "Crawl Jobs", href: "/crawl", icon: Briefcase },
  { name: "Upload", href: "/upload", icon: Upload },
];

export default function Layout() {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [documentSearchOpen, setDocumentSearchOpen] = useState(false);

  // Add keyboard shortcut for document search (Cmd/Ctrl + K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setDocumentSearchOpen(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile menu button */}
      <div className="lg:hidden  z-50 w-full border-b border-border flex items-center justify-between px-1 py-2 bg-slate-700 bg-linear-to-r from-slate-700 to-slate-900 text-white">
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-2 rounded-md text-white"
        >
          {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-semibold">CodeDox</h1>
        </div>
      </div>

      <div
        className={`fixed inset-y-0 left-0 z-40 w-48 bg-secondary transform transition-transform lg:translate-x-0 lg:w-64 border-r border-border ${
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-full flex-col">
          <div className="px-3 pt-4 pb-2">
            <button
              onClick={() => setDocumentSearchOpen(true)}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors text-gray-600 dark:text-gray-400"
            >
              <FileSearch className="h-4 w-4" />
              <span className="flex-1 text-left">Markdown Pages</span>
              <kbd className="text-xs bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded">
                ⌘K
              </kbd>
            </button>
          </div>
          <nav className="flex-1 space-y-1 px-3 py-4">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href;
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`group flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                    isActive
                      ? "bg-linear-to-r from-slate-700 to-slate-900 text-white"
                      : "text-secondary-foreground hover:bg-secondary/80"
                  }`}
                >
                  <item.icon className="mr-3 h-5 w-5" />
                  {item.name}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>

      <div className="lg:pl-64 flex-1 flex flex-col h-screen">
        <main className="flex-1  p-4 flex min-h-0">
          <div className="w-full flex flex-col">
            <Outlet />
          </div>
        </main>
      </div>

      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      <DocumentSearchModal
        isOpen={documentSearchOpen}
        onClose={() => setDocumentSearchOpen(false)}
      />
    </div>
  );
}
