import React, { useState } from 'react';
import { Examination, User } from '../types';
import { api } from '../services/api';
import {
  BookOpen,
  Plus,
  Search,
  Printer,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  X,
  FileCheck2,
  Trash2,
} from 'lucide-react';

interface ExaminationsPageProps {
  user: User;
  examinations: Examination[];
  onSelectExam: (examId: number) => void;
  onRefresh: () => void;
  isCreateOpen: boolean;
  setIsCreateOpen: (open: boolean) => void;
}

export const ExaminationsPage: React.FC<ExaminationsPageProps> = ({
  user,
  examinations,
  onSelectExam,
  onRefresh,
  isCreateOpen,
  setIsCreateOpen,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Always refresh examinations list from database on mount
  React.useEffect(() => {
    onRefresh();
  }, []);
  
  // Create form state
  const [code, setCode] = useState('');
  const [title, setTitle] = useState('');
  const [subject, setSubject] = useState('');
  const [classGrade, setClassGrade] = useState('');
  const [examDate, setExamDate] = useState(new Date().toISOString().split('T')[0]);
  const [questionCount, setQuestionCount] = useState<number>(100);
  const [positiveMarks, setPositiveMarks] = useState<number>(1.0);
  const [negativeMarks, setNegativeMarks] = useState<number>(0.25);
  const [blankMarks, setBlankMarks] = useState<number>(0.0);
  const [multiplePenalty, setMultiplePenalty] = useState<number>(0.25);
  const [answerKeyInput, setAnswerKeyInput] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const filteredExams = examinations.filter(
    (e) =>
      e.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      e.code.toLowerCase().includes(searchTerm.toLowerCase()) ||
      e.subject.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);

    try {
      // Parse optional initial answer key
      const answersDict: Record<string, string> = {};
      if (answerKeyInput.trim()) {
        const parts = answerKeyInput.split(/[\s,]+/);
        parts.forEach((p, idx) => {
          const opt = p.toUpperCase().trim();
          if (['A', 'B', 'C', 'D'].includes(opt)) {
            answersDict[String(idx + 1)] = opt;
          }
        });
      }

      await api.createExamination({
        code: code.toUpperCase().trim(),
        title: title.trim(),
        subject: subject.trim(),
        class_grade: classGrade.trim(),
        exam_date: examDate,
        question_count: Number(questionCount),
        options_per_question: 4,
        positive_marks: Number(positiveMarks),
        negative_marks: Number(negativeMarks),
        blank_marks: Number(blankMarks),
        multiple_penalty: Number(multiplePenalty),
        allow_teacher_override: true,
        is_published: false,
        initial_answers: Object.keys(answersDict).length > 0 ? answersDict : undefined,
      });

      setIsCreateOpen(false);
      resetForm();
      onRefresh();
      setSuccessMessage('Examination created and saved permanently to database.');
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err: any) {
      setFormError(err.message || 'Failed to create examination');
    } finally {
      setSubmitting(false);
    }
  };

  const resetForm = () => {
    setCode('');
    setTitle('');
    setSubject('');
    setClassGrade('');
    setQuestionCount(100);
    setPositiveMarks(1.0);
    setNegativeMarks(0.25);
    setAnswerKeyInput('');
    setFormError(null);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Examinations</h1>
          <p className="text-xs sm:text-sm text-slate-500">
            Manage OMR test sheets, grading schemes, and answer keys
          </p>
        </div>

        <button
          onClick={() => setIsCreateOpen(true)}
          className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm shadow-md shadow-blue-500/20 transition-all self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>New Examination</span>
        </button>
      </div>

      {/* Success Alert Banner */}
      {successMessage && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center space-x-2 shadow-sm animate-fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Search Bar */}
      <div className="relative max-w-md">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
          <Search className="w-4 h-4" />
        </div>
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search by title, exam code, or subject..."
          className="w-full pl-9 pr-4 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent bg-white shadow-sm"
        />
      </div>

      {/* Examinations Cards List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {filteredExams.length === 0 ? (
          <div className="col-span-full bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-500">
            <BookOpen className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="text-base font-semibold text-slate-800">No examinations found</h3>
            <p className="text-xs text-slate-500 mt-1">
              Create a new examination or clear your search filter.
            </p>
          </div>
        ) : (
          filteredExams.map((exam) => (
            <div
              key={exam.id}
              className="bg-white rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow p-5 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="px-2.5 py-0.5 rounded-md bg-blue-50 text-blue-700 text-xs font-bold border border-blue-200">
                    {exam.code}
                  </span>
                  {exam.is_published ? (
                    <span className="flex items-center text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                      <CheckCircle2 className="w-3 h-3 mr-1" /> Published
                    </span>
                  ) : (
                    <span className="text-[11px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                      Provisional
                    </span>
                  )}
                </div>

                <h3 className="text-base font-bold text-slate-900 line-clamp-1">{exam.title}</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {exam.subject} • {exam.class_grade} • {exam.exam_date}
                </p>

                {/* Specs Pill Summary */}
                <div className="mt-4 grid grid-cols-3 gap-2 text-center p-2 rounded-xl bg-slate-50 border border-slate-100">
                  <div>
                    <div className="text-[10px] text-slate-400 uppercase font-medium">Questions</div>
                    <div className="text-xs font-bold text-slate-800">{exam.question_count}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-400 uppercase font-medium">Marking</div>
                    <div className="text-xs font-bold text-slate-800">
                      +{exam.positive_marks} / -{exam.negative_marks}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-400 uppercase font-medium">Evaluated</div>
                    <div className="text-xs font-bold text-blue-600">{exam.submissions_count || 0}</div>
                  </div>
                </div>

                {exam.pending_review_count && exam.pending_review_count > 0 ? (
                  <div className="mt-3 flex items-center space-x-1.5 text-xs text-amber-700 bg-amber-50 p-2 rounded-lg border border-amber-200">
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                    <span>{exam.pending_review_count} sheets require review</span>
                  </div>
                ) : null}
              </div>

              {/* Action Buttons */}
              <div className="mt-5 pt-4 border-t border-slate-100 flex items-center justify-between gap-2">
                <a
                  href={`/api/templates/omr-pdf/${exam.id}`}
                  target="_blank"
                  rel="noreferrer"
                  title="Download Synchronized A4 PDF Template"
                  className="p-2 rounded-lg text-slate-600 hover:text-blue-600 hover:bg-blue-50 border border-slate-200 transition-colors"
                >
                  <Printer className="w-4 h-4" />
                </a>

                <a
                  href={`/api/reports/csv/${exam.id}`}
                  target="_blank"
                  rel="noreferrer"
                  title="Download CSV Results"
                  className="p-2 rounded-lg text-slate-600 hover:text-emerald-600 hover:bg-emerald-50 border border-slate-200 transition-colors"
                >
                  <FileSpreadsheet className="w-4 h-4" />
                </a>

                <button
                  type="button"
                  onClick={async () => {
                    if (!window.confirm(`Delete examination "${exam.title}" and all its submissions?`)) return;
                    try {
                      await api.deleteExamination(exam.id);
                      onRefresh();
                    } catch (err: any) {
                      alert(`Failed to delete exam: ${err.message}`);
                    }
                  }}
                  title="Delete Examination"
                  className="p-2 rounded-lg text-rose-600 hover:bg-rose-50 border border-rose-200 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>

                <button
                  onClick={() => onSelectExam(exam.id)}
                  className="flex-1 flex items-center justify-center space-x-1 px-3 py-2 rounded-xl bg-slate-900 hover:bg-blue-600 text-white text-xs font-semibold transition-colors"
                >
                  <span>Open Console</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Create Examination Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm overflow-y-auto">
          <div className="relative w-full max-w-xl bg-white rounded-2xl shadow-2xl overflow-hidden my-8">
            <div className="flex items-center justify-between p-5 border-b border-slate-100 bg-slate-50">
              <div className="flex items-center space-x-2">
                <div className="p-1.5 bg-blue-600 text-white rounded-lg">
                  <FileCheck2 className="w-4 h-4" />
                </div>
                <h3 className="font-bold text-base text-slate-900">Create New Examination</h3>
              </div>
              <button
                onClick={() => setIsCreateOpen(false)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {formError && (
              <div className="m-5 mb-0 p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleCreateSubmit} className="p-6 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Exam Code *
                  </label>
                  <input
                    type="text"
                    required
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder="e.g. MATH-2026-F"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-600 uppercase"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={examDate}
                    onChange={(e) => setExamDate(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-600"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Examination Title *
                </label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Midterm Physics Evaluation"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-600"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Subject *
                  </label>
                  <input
                    type="text"
                    required
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    placeholder="e.g. Physics"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-600"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Class / Grade *
                  </label>
                  <input
                    type="text"
                    required
                    value={classGrade}
                    onChange={(e) => setClassGrade(e.target.value)}
                    placeholder="e.g. Grade 10-A"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-600"
                  />
                </div>
              </div>

              {/* Template Question Count Selector */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Question Count (Geometric Layout)
                </label>
                <select
                  value={questionCount}
                  onChange={(e) => setQuestionCount(Number(e.target.value))}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-600 bg-white"
                >
                  <option value={25}>25 Questions (Single column)</option>
                  <option value={40}>40 Questions (2 columns)</option>
                  <option value={50}>50 Questions (2 columns)</option>
                  <option value={100}>100 Questions (Standard 4 columns - Recommended)</option>
                  <option value={150}>150 Questions (5 columns)</option>
                  <option value={200}>200 Questions (5 columns)</option>
                </select>
              </div>

              {/* Marking Scheme */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Correct (+ve)
                  </label>
                  <input
                    type="number"
                    step="0.25"
                    min="0"
                    value={positiveMarks}
                    onChange={(e) => setPositiveMarks(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 text-sm border rounded-lg"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Incorrect (-ve)
                  </label>
                  <input
                    type="number"
                    step="0.25"
                    min="0"
                    value={negativeMarks}
                    onChange={(e) => setNegativeMarks(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 text-sm border rounded-lg"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Blank Mark
                  </label>
                  <input
                    type="number"
                    step="0.25"
                    value={blankMarks}
                    onChange={(e) => setBlankMarks(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 text-sm border rounded-lg"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Multiple Penalty
                  </label>
                  <input
                    type="number"
                    step="0.25"
                    min="0"
                    value={multiplePenalty}
                    onChange={(e) => setMultiplePenalty(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 text-sm border rounded-lg"
                  />
                </div>
              </div>

              {/* Optional Initial Answer Key Quick String */}
              <div className="pt-2">
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Initial Answer Key (Optional - e.g. "A B C D A B C D ...")
                </label>
                <textarea
                  rows={2}
                  value={answerKeyInput}
                  onChange={(e) => setAnswerKeyInput(e.target.value)}
                  placeholder="Paste space-separated options: A B C D A B ..."
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg font-mono focus:ring-2 focus:ring-blue-600"
                />
                <p className="text-[11px] text-slate-400 mt-0.5">
                  You can also edit each question bubble interactively inside the exam console.
                </p>
              </div>

              <div className="flex justify-end space-x-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-md disabled:opacity-50"
                >
                  {submitting ? 'Creating...' : 'Create Examination'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
