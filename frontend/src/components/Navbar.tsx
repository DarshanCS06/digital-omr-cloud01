import React, { useState } from 'react';
import { User } from '../types';
import { FileCheck2, LayoutDashboard, Users, LogOut, BookOpen, ShieldCheck, Smartphone, X, Copy, Check } from 'lucide-react';

interface NavbarProps {
  user: User | null;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ user, activeTab, setActiveTab, onLogout }) => {
  const [mobileModalOpen, setMobileModalOpen] = useState(false);
  const [mobileInfo, setMobileInfo] = useState<{
    primary_url: string;
    lan_url: string;
    public_url: string | null;
    primary_qr_data_url: string;
    lan_qr_data_url: string;
  } | null>(null);
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null);

  const handleOpenMobileModal = async () => {
    setMobileModalOpen(true);
    try {
      const res = await fetch('/api/mobile-access');
      if (res.ok) {
        const data = await res.json();
        setMobileInfo(data);
      }
    } catch {}
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard?.writeText(text);
    setCopiedUrl(text);
    setTimeout(() => setCopiedUrl(null), 2000);
  };

  return (
    <>
      <header className="sticky top-0 z-40 bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo & Brand */}
            <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('dashboard')}>
              <div className="p-2 bg-blue-600 text-white rounded-lg shadow-sm">
                <FileCheck2 className="w-6 h-6" />
              </div>
              <div>
                <span className="text-lg sm:text-xl font-bold tracking-tight text-slate-900">
                  Vidyakashi <span className="text-blue-600">OMR</span> Portal
                </span>
                <span className="hidden lg:inline-block ml-2 text-xs bg-blue-50 text-blue-700 font-medium px-2 py-0.5 rounded-full border border-blue-200">
                  Study Circle Evaluation
                </span>
              </div>
            </div>

            {/* Navigation Links */}
            {user && (
              <nav className="flex items-center space-x-1 sm:space-x-2">
                <button
                  onClick={() => setActiveTab('dashboard')}
                  className={`flex items-center space-x-1.5 px-2.5 sm:px-3 py-2 rounded-md text-xs sm:text-sm font-medium transition-colors ${
                    activeTab === 'dashboard'
                      ? 'bg-blue-50 text-blue-700 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <LayoutDashboard className="w-4 h-4" />
                  <span className="hidden sm:inline">Dashboard</span>
                </button>

                <button
                  onClick={() => setActiveTab('examinations')}
                  className={`flex items-center space-x-1.5 px-2.5 sm:px-3 py-2 rounded-md text-xs sm:text-sm font-medium transition-colors ${
                    activeTab === 'examinations'
                      ? 'bg-blue-50 text-blue-700 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <BookOpen className="w-4 h-4" />
                  <span>Examinations</span>
                </button>

                {user.role === 'ADMIN' && (
                  <button
                    onClick={() => setActiveTab('users')}
                    className={`flex items-center space-x-1.5 px-2.5 sm:px-3 py-2 rounded-md text-xs sm:text-sm font-medium transition-colors ${
                      activeTab === 'users'
                        ? 'bg-blue-50 text-blue-700 font-semibold'
                        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                    }`}
                  >
                    <Users className="w-4 h-4" />
                    <span className="hidden sm:inline">Teachers</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={handleOpenMobileModal}
                  className="flex items-center space-x-1 px-2.5 sm:px-3 py-1.5 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 text-xs font-bold transition-colors"
                  title="Open on Android Mobile Phone"
                >
                  <Smartphone className="w-4 h-4 text-emerald-600" />
                  <span className="hidden md:inline">Android Mobile</span>
                </button>
              </nav>
            )}

            {/* User profile & Logout */}
            {user && (
              <div className="flex items-center space-x-2 sm:space-x-3">
                <div className="text-right hidden md:block">
                  <div className="text-xs font-semibold text-slate-900">{user.full_name}</div>
                  <div className="flex items-center justify-end space-x-1">
                    {user.role === 'ADMIN' ? (
                      <span className="inline-flex items-center text-[10px] font-bold uppercase tracking-wider text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded border border-purple-200">
                        <ShieldCheck className="w-3 h-3 mr-0.5 text-purple-600" /> Admin
                      </span>
                    ) : (
                      <span className="inline-flex items-center text-[10px] font-bold uppercase tracking-wider text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                        Teacher
                      </span>
                    )}
                    <span className="text-xs text-slate-500 truncate max-w-[140px]">{user.email}</span>
                  </div>
                </div>

                <button
                  onClick={onLogout}
                  title="Log out"
                  className="p-2 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors border border-transparent hover:border-rose-200"
                >
                  <LogOut className="w-5 h-5" />
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Android Mobile Access & QR Code Modal */}
      {mobileModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <div className="p-2 bg-emerald-600 text-white rounded-xl">
                  <Smartphone className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-slate-900">Open on Android Mobile Phone</h3>
                  <p className="text-xs text-slate-500">Scan QR code with your Android camera or Chrome</p>
                </div>
              </div>
              <button
                onClick={() => setMobileModalOpen(false)}
                className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {mobileInfo ? (
              <div className="space-y-4">
                <div className="flex flex-col items-center p-4 bg-slate-50 rounded-2xl border border-slate-200">
                  <img
                    src={mobileInfo.primary_qr_data_url}
                    alt="Android Mobile QR Code"
                    className="w-48 h-48 rounded-xl border border-slate-200 bg-white p-2 shadow-sm"
                  />
                  <span className="text-xs font-bold text-emerald-700 mt-2">
                    📷 Point your Android Camera at this QR Code
                  </span>
                </div>

                {mobileInfo.public_url && (
                  <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 space-y-1">
                    <div className="text-[11px] font-bold text-emerald-800 uppercase">
                      🌐 Public HTTPS Android Link (Works on 4G/5G & Wi-Fi)
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <a
                        href={mobileInfo.public_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-mono font-bold text-emerald-900 underline break-all"
                      >
                        {mobileInfo.public_url}
                      </a>
                      <button
                        type="button"
                        onClick={() => copyToClipboard(mobileInfo.public_url!)}
                        className="p-1.5 rounded-lg bg-white border border-emerald-300 text-emerald-700 hover:bg-emerald-100 shrink-0"
                      >
                        {copiedUrl === mobileInfo.public_url ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>
                )}

                <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 space-y-1">
                  <div className="text-[11px] font-bold text-blue-800 uppercase">
                    📶 Local Wi-Fi Link (Same Wi-Fi / Hotspot)
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <a
                      href={mobileInfo.lan_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-mono font-bold text-blue-900 underline break-all"
                    >
                      {mobileInfo.lan_url}
                    </a>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(mobileInfo.lan_url)}
                      className="p-1.5 rounded-lg bg-white border border-blue-300 text-blue-700 hover:bg-blue-100 shrink-0"
                    >
                      {copiedUrl === mobileInfo.lan_url ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>

                <div className="text-xs text-slate-600 bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-1">
                  <div className="font-bold text-slate-800">📲 Install as Android App:</div>
                  <p>Open the link in <strong>Android Chrome</strong>, tap the <strong>⋮ menu</strong>, and select <strong>"Add to Home screen" / "Install app"</strong>.</p>
                </div>
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-slate-500">Generating mobile QR code...</div>
            )}
          </div>
        </div>
      )}
    </>
  );
};
