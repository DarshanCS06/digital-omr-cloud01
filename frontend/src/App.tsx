import React, { useState, useEffect } from 'react';
import { User, Examination } from './types';
import { api } from './services/api';
import { Navbar } from './components/Navbar';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { ExaminationsPage } from './pages/ExaminationsPage';
import { ExamDetailPage } from './pages/ExamDetailPage';
import { ReviewQueuePage } from './pages/ReviewQueuePage';
import { UserManagementPage } from './pages/UserManagementPage';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [selectedExamId, setSelectedExamId] = useState<number | null>(null);
  const [targetReviewSubId, setTargetReviewSubId] = useState<number | undefined>(undefined);
  const [examinations, setExaminations] = useState<Examination[]>([]);
  const [isCreateExamOpen, setIsCreateExamOpen] = useState(false);
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    // Check saved session
    const savedUser = localStorage.getItem('omr_user');
    const token = localStorage.getItem('omr_access_token');
    if (savedUser && token) {
      try {
        const parsed = JSON.parse(savedUser);
        if (parsed.full_name?.includes('Sarah Jenkins') || parsed.full_name?.includes('System Administrator')) {
          parsed.full_name = 'Vidyakashi';
          localStorage.setItem('omr_user', JSON.stringify(parsed));
        }
        setCurrentUser(parsed);
        loadExaminations();
      } catch {
        api.clearToken();
      }
    }
    setInitializing(false);
  }, []);

  const loadExaminations = async () => {
    try {
      const data = await api.getExaminations();
      setExaminations(data);
    } catch (err) {
      console.error('Failed to load examinations:', err);
    }
  };

  const handleLoginSuccess = (user: User) => {
    setCurrentUser(user);
    setActiveTab('dashboard');
    loadExaminations();
  };

  const handleLogout = () => {
    api.clearToken();
    setCurrentUser(null);
    setActiveTab('dashboard');
  };

  const handleOpenExamDetail = (examId: number) => {
    setSelectedExamId(examId);
    setActiveTab('exam-detail');
  };

  const handleOpenReview = (subId: number) => {
    setTargetReviewSubId(subId);
    setActiveTab('review-queue');
  };

  if (initializing) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-white via-slate-50 to-blue-50/30 flex flex-col items-center justify-center p-4">
        <div className="relative flex flex-col items-center">
          <div className="w-24 h-24 rounded-2xl bg-white border border-slate-200 shadow-xl shadow-blue-500/10 p-2 flex items-center justify-center mb-4">
            <img
              src="/vidyakashi_logo.jpg?v=2"
              alt="Vidyakashi Study Circle"
              className="w-full h-full object-contain"
            />
          </div>
          <h1 className="text-xl font-extrabold tracking-tight text-slate-900">
            Vidyakashi <span className="text-blue-600">Study Circle</span>
          </h1>
          <p className="text-xs font-semibold text-slate-500 mt-1">
            Digital OMR Cloud
          </p>
          <div className="mt-6 flex items-center space-x-2">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-blue-600 border-t-transparent"></div>
            <span className="text-xs font-medium text-slate-600">Loading system...</span>
          </div>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
      <Navbar
        user={currentUser}
        activeTab={activeTab}
        setActiveTab={(tab) => {
          setActiveTab(tab);
          loadExaminations();
        }}
        onLogout={handleLogout}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {activeTab === 'dashboard' && (
          <DashboardPage
            user={currentUser}
            onNavigateExam={handleOpenExamDetail}
            onOpenCreateExam={() => {
              setActiveTab('examinations');
              setIsCreateExamOpen(true);
              loadExaminations();
            }}
            onNavigateExamsList={() => {
              setActiveTab('examinations');
              loadExaminations();
            }}
          />
        )}

        {activeTab === 'examinations' && (
          <ExaminationsPage
            user={currentUser}
            examinations={examinations}
            onSelectExam={handleOpenExamDetail}
            onRefresh={loadExaminations}
            isCreateOpen={isCreateExamOpen}
            setIsCreateOpen={setIsCreateExamOpen}
          />
        )}

        {activeTab === 'exam-detail' && selectedExamId && (
          <ExamDetailPage
            examId={selectedExamId}
            user={currentUser}
            onBack={() => {
              setActiveTab('examinations');
              loadExaminations();
            }}
            onOpenReview={handleOpenReview}
          />
        )}

        {activeTab === 'review-queue' && selectedExamId && (
          <ReviewQueuePage
            examId={selectedExamId}
            initialSubmissionId={targetReviewSubId}
            onBack={() => setActiveTab('exam-detail')}
          />
        )}

        {activeTab === 'users' && currentUser.role === 'ADMIN' && (
          <UserManagementPage currentUser={currentUser} />
        )}
      </main>
    </div>
  );
};

export default App;
