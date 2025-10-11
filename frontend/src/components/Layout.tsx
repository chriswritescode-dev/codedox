import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import {
  Home,
  Search,
  Database,
  Briefcase,
  Menu,
  X,
  Upload,
  FileSearch,
  Plus,
  Settings,
} from "lucide-react";
import { useState, useEffect } from "react";
import { DocumentSearchModal } from "./DocumentSearchModal";
import { NewCrawlDialog } from "./NewCrawlDialog";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useToast } from "../hooks/useToast";

const navigation = [
  { name: "Dashboard", href: "/", icon: Home },
  { name: "Search", href: "/search", icon: Search },
  { name: "Sources", href: "/sources", icon: Database },
  { name: "Crawl Jobs", href: "/crawl", icon: Briefcase },
  { name: "Upload", href: "/upload", icon: Upload },
  { name: "Settings", href: "/settings", icon: Settings },
];

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [documentSearchOpen, setDocumentSearchOpen] = useState(false);
  const [crawlDialogOpen, setCrawlDialogOpen] = useState(false);

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

  // Mutation for creating crawl jobs
  const createCrawlMutation = useMutation({
    mutationFn: api.createCrawlJob.bind(api),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["crawl-jobs"] });
      setCrawlDialogOpen(false);
      navigate(`/crawl/${(data as { id: string }).id}`);
      toast.success("Crawl job created successfully");
    },
    onError: (error) => {
      console.error("Failed to create crawl job:", error);
      toast.error(
        "Failed to create crawl job: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  const handleCrawlSubmit = (formData: {
    name?: string;
    base_url: string;
    max_depth: number;
    domain_filter?: string;
    url_patterns?: string[];
    max_concurrent_crawls?: number;
  }) => {
    createCrawlMutation.mutate(formData);
  };

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
          <div className="px-3 pt-4 pb-2 space-y-2">
            <button
              onClick={() => setCrawlDialogOpen(true)}
              className="cursor-pointer w-full flex items-center gap-2 px-3 py-2.5 text-sm bg-primary hover:bg-primary/90 text-primary-foreground rounded-lg transition-all font-semibold shadow-lg hover:shadow-xl border border-primary/30 transform hover:-translate-y-0.5"
            >
              <Plus className="h-4 w-4" />
              <span className="flex-1 text-left">New Crawl</span>
            </button>
            <button
              onClick={() => setDocumentSearchOpen(true)}
              className="cursor-pointer w-full flex items-center gap-2 px-3 py-2.5 text-sm bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 border-2 border-slate-300 dark:border-slate-500 rounded-lg transition-all text-slate-800 dark:text-slate-200 shadow-md hover:shadow-lg font-medium"
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

      {/* Floating Action Button for Mobile */}
      <button
        onClick={() => setCrawlDialogOpen(true)}
        className="fixed bottom-6 right-6 z-40 lg:hidden w-14 h-14 bg-primary text-primary-foreground rounded-full shadow-lg hover:shadow-xl hover:bg-primary/90 transition-all flex items-center justify-center"
        aria-label="New Crawl"
      >
        <Plus className="h-6 w-6" />
      </button>

      <DocumentSearchModal
        isOpen={documentSearchOpen}
        onClose={() => setDocumentSearchOpen(false)}
      />

      <NewCrawlDialog
        isOpen={crawlDialogOpen}
        onClose={() => setCrawlDialogOpen(false)}
        onSubmit={handleCrawlSubmit}
        isSubmitting={createCrawlMutation.isPending}
      />
    </div>
  );
}
