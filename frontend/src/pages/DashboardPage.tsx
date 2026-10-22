import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { User, DashboardStats, Examination } from '../types';
import {
  BookOpen,
  Users,
  Clock,
  AlertTriangle,
  CheckCircle2,
  FileSpreadsheet,
  ArrowRight,
  Plus,
  Printer,
  History,
  Trash2,
} from 'lucide-react';

interface DashboardPageProps {
  user: User;
  onNavigateExam: (examId: number) => void;
  onOpenCreateExam: () => void;
  onNavigateExamsList: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  user,
  onNavigateExam,
  onOpenCreateExam,
  onNavigateExamsList,
}) => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [exams, setExams] = useState<Examination[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [statsData, examsData] = await Promise.all([
        api.getDashboardStats(),
        api.getExaminations(),
      ]);
      setStats(statsData);
      setExams(examsData);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleClearHistory = async (scope: 'audit' | 'all' = 'all') => {
    const msg =
      scope === 'audit'
        ? 'Clear all recent audit activity logs?'
        : 'Clear all evaluated OMR sheets, upload batches, and activity history across the portal?';
    if (!window.confirm(msg)) return;
    try {
      await api.clearHistory(scope);
      await fetchDashboardData();
    } catch (err: any) {
      alert(`Failed to clear history: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-blue-700 via-blue-600 to-indigo-700 rounded-2xl p-6 sm:p-8 text-white shadow-xl shadow-blue-500/15 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <span className="inline-block px-2.5 py-1 rounded-full bg-blue-500/30 text-blue-100 text-xs font-semibold mb-2 backdrop-blur-sm border border-blue-400/30">
            {user.role === 'ADMIN' ? 'Administrator Workspace' : 'Teacher Evaluation Station'}
          </span>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            Welcome, {user.full_name}
          </h1>
          <p className="mt-1 text-sm text-blue-100 max-w-xl">
            Evaluate ordinary mobile phone photos of printed OMR sheets with computer vision and automated grading.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={onOpenCreateExam}
            className="flex items-center space-x-1.5 px-4 py-2.5 rounded-xl bg-white text-blue-700 hover:bg-blue-50 text-xs sm:text-sm font-bold shadow-md transition-all active:scale-95"
          >
            <Plus className="w-4 h-4" />
            <span>Create Examination</span>
          </button>

          <a
            href="/api/templates/sample-pdf"
            target="_blank"
            rel="noreferrer"
            className="flex items-center space-x-1.5 px-4 py-2.5 rounded-xl bg-blue-500/30 hover:bg-blue-500/40 text-white text-xs sm:text-sm font-semibold border border-blue-400/40 transition-colors"
          >
            <Printer className="w-4 h-4" />
            <span>Blank 100Q OMR PDF</span>
          </a>

          <a
            href="/api/templates/sample-filled-pdf"
            target="_blank"
            rel="noreferrer"
            className="flex items-center space-x-1.5 px-4 py-2.5 rounded-xl bg-emerald-500/30 hover:bg-emerald-500/40 text-white text-xs sm:text-sm font-semibold border border-emerald-400/40 transition-colors"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Sample Filled 100Q PDF</span>
          </a>

          <button
            type="button"
            onClick={() => handleClearHistory('all')}
            className="flex items-center space-x-1.5 px-4 py-2.5 rounded-xl bg-rose-500/35 hover:bg-rose-500/50 text-white text-xs sm:text-sm font-semibold border border-rose-400/40 transition-colors"
            title="Clear all evaluated submissions, batches, and activity logs"
          >
            <Trash2 className="w-4 h-4" />
            <span>Clear History</span>
          </button>
        </div>
      </div>

      {/* Primary KPI Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3 sm:gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Total Exams</span>
            <BookOpen className="w-4 h-4 text-blue-600" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {loading ? '...' : stats?.total_examinations || 0}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Configured tests</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Evaluated</span>
            <Users className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-2 text-2xl font-bold text-emerald-600">
            {loading ? '...' : stats?.total_students_evaluated || 0}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Students graded</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Pending Batches</span>
            <Clock className="w-4 h-4 text-amber-500" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {loading ? '...' : stats?.pending_batches || 0}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Processing in worker</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Needs Review</span>
            <AlertTriangle className="w-4 h-4 text-amber-600" />
          </div>
          <div className="mt-2 text-2xl font-bold text-amber-600">
            {loading ? '...' : stats?.sheets_awaiting_review || 0}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Flagged for human check</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Failed Photos</span>
            <AlertTriangle className="w-4 h-4 text-rose-500" />
          </div>
          <div className="mt-2 text-2xl font-bold text-rose-600">
            {loading ? '...' : stats?.failed_images || 0}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Blurry or invalid</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Published</span>
            <CheckCircle2 className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="mt-2 text-2xl font-bold text-indigo-600">
            {loading ? '...' : stats?.published_results || 0}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Results finalized</div>
        </div>
      </div>

      {/* Main Content Grid: Active Exams & Recent Audit Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Examinations List */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
          <div className="p-5 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900">Your Examinations</h2>
              <p className="text-xs text-slate-500">Tests assigned to or created by you</p>
            </div>
            <button
              onClick={onNavigateExamsList}
              className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center"
            >
              View All <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </button>
          </div>

          <div className="divide-y divide-slate-100 flex-1 overflow-x-auto">
            {exams.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-sm">
                No examinations found. Click "Create Examination" to set up your first test.
              </div>
            ) : (
              exams.slice(0, 5).map((exam) => (
                <div
                  key={exam.id}
                  onClick={() => onNavigateExam(exam.id)}
                  className="p-4 hover:bg-slate-50 cursor-pointer transition-colors flex items-center justify-between gap-4"
                >
                  <div className="flex items-center space-x-3 min-w-0">
                    <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-700 font-bold text-xs shrink-0">
                      {exam.code.slice(0, 4)}
                    </div>
                    <div className="min-w-0">
                      <div className="font-semibold text-sm text-slate-900 truncate">{exam.title}</div>
                      <div className="text-xs text-slate-500 flex items-center space-x-2 mt-0.5">
                        <span>{exam.subject}</span>
                        <span>•</span>
                        <span>{exam.class_grade}</span>
                        <span>•</span>
                        <span>{exam.question_count} Qs</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3 shrink-0">
                    {exam.pending_review_count && exam.pending_review_count > 0 ? (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                        {exam.pending_review_count} to review
                      </span>
                    ) : null}

                    {exam.is_published ? (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                        Published
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600">
                        Provisional
                      </span>
                    )}

                    <div className="text-xs font-semibold text-slate-700">
                      {exam.submissions_count || 0} sheets
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Audit Log / Recent Activity */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 flex flex-col">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
            <div className="flex items-center space-x-2">
              <History className="w-4 h-4 text-blue-600" />
              <h3 className="font-bold text-sm text-slate-900">Recent Audit Activity</h3>
            </div>
            {stats?.recent_activity && stats.recent_activity.length > 0 && (
              <button
                type="button"
                onClick={() => handleClearHistory('audit')}
                className="flex items-center space-x-1 text-xs font-semibold text-rose-600 hover:text-rose-700"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Clear</span>
              </button>
            )}
          </div>

          <div className="space-y-3 flex-1 overflow-y-auto max-h-[360px]">
            {!stats?.recent_activity || stats.recent_activity.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-6">No recent actions recorded.</p>
            ) : (
              stats.recent_activity.map((act) => (
                <div key={act.id} className="text-xs p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <div className="font-semibold text-slate-800">
                    {act.action.replace(/_/g, ' ')}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5 flex justify-between">
                    <span>{act.resource_type} {act.resource_id ? `#${act.resource_id}` : ''}</span>
                    <span>{act.timestamp.split(' ')[1]}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
