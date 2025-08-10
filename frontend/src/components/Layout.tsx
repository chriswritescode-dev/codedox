import { Outlet, Link, useLocation } from "react-router-dom";
import {
  Home,
  Search,
  Database,
  Briefcase,
  Menu,
  X,
  Upload,
} from "lucide-react";
import { useState } from "react";

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

      {/* Sidebar */}
      <div
        className={`fixed inset-y-0 left-0 z-40 w-48 bg-secondary transform transition-transform lg:translate-x-0 lg:w-64 border-r border-border ${
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-full flex-col">
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

      {/* Main content */}
      <div className="lg:pl-64 flex-1 flex flex-col h-screen">
        <main className="flex-1 py-8 px-4 sm:px-6 lg:px-8 flex min-h-0">
          <div className="w-full flex flex-col">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Mobile menu overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}
    </div>
  );
}
