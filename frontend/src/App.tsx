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
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-4 border-blue-600 border-t-transparent"></div>
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
          if (tab === 'examinations') loadExaminations();
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
            }}
            onNavigateExamsList={() => setActiveTab('examinations')}
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
