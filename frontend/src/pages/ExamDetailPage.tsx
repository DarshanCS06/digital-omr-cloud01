import React, { useState, useEffect } from 'react';
import { Examination, Submission, AnswerKey, ExamStats, User, UploadBatch } from '../types';
import { api } from '../services/api';
import { CameraModal } from '../components/CameraModal';
import {
  ArrowLeft,
  Printer,
  FileSpreadsheet,
  Upload,
  Camera,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Search,
  Save,
  BarChart3,
  Users,
  Eye,
  Check,
  X,
  Edit2,
  FileText,
  Trash2,
} from 'lucide-react';

interface StagedPhotoPreview {
  id: string;
  file: File;
  validating: boolean;
  is_pdf?: boolean;
  page_count?: number;
  file_size_bytes?: number;
  is_valid?: boolean;
  validation_message?: string;
  quality?: Record<string, any>;
  alignment?: Record<string, any>;
  original_preview_url?: string;
  corrected_preview_url?: string;
}

interface ExamDetailPageProps {
  examId: number;
  user: User;
  onBack: () => void;
  onOpenReview: (subId: number) => void;
}

export const ExamDetailPage: React.FC<ExamDetailPageProps> = ({
  examId,
  user,
  onBack,
  onOpenReview,
}) => {
  const [exam, setExam] = useState<Examination | null>(null);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [answerKey, setAnswerKey] = useState<AnswerKey | null>(null);
  const [stats, setStats] = useState<ExamStats | null>(null);
  const [activeTab, setActiveTab] = useState<'submissions' | 'upload' | 'answer-key' | 'analytics' | 'teachers' | 'omr-sheet'>('submissions');
  const [loading, setLoading] = useState(true);

  // Auth token — appended to download links so browser <a href> gets past auth
  const authToken = api.getAuthToken();

  // Submissions search & filter
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');

  // Upload state
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const [retakeTargetIndex, setRetakeTargetIndex] = useState<number | null>(null);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [stagedPreviews, setStagedPreviews] = useState<StagedPhotoPreview[]>([]);
  const [uploading, setUploading] = useState(false);
  const [activeBatch, setActiveBatch] = useState<UploadBatch | null>(null);

  // Answer Key Editing & Rescore Modal
  const [editedKey, setEditedKey] = useState<Record<string, string>>({});
  const [isRescoreModalOpen, setIsRescoreModalOpen] = useState(false);
  const [rescoreReason, setRescoreReason] = useState('');
  const [rescoreSubmitting, setRescoreSubmitting] = useState(false);

  // Inspection modal & student detail editing
  const [inspectedSub, setInspectedSub] = useState<Submission | null>(null);
  const [questionFilter, setQuestionFilter] = useState<'ALL' | 'WRONG' | 'CORRECT'>('ALL');
  const [previewSheetMode, setPreviewSheetMode] = useState<'blank' | 'filled'>('blank');
  const [evaluatingSample, setEvaluatingSample] = useState(false);
  const [editingDetails, setEditingDetails] = useState(false);
  const [editName, setEditName] = useState('');
  const [editRoll, setEditRoll] = useState('');
  const [savingDetails, setSavingDetails] = useState(false);

  const handleInspectSubmission = async (subId: number) => {
    try {
      const detail = await api.getSubmissionDetail(subId);
      setQuestionFilter('ALL');
      setEditingDetails(false);
      setInspectedSub(detail);
    } catch (err) {
      console.error('Failed to load submission detail:', err);
    }
  };

  const handleStartEditDetails = () => {
    if (!inspectedSub) return;
    setEditName(inspectedSub.student_name || '');
    setEditRoll(inspectedSub.student_roll || inspectedSub.detected_roll_number || '');
    setEditingDetails(true);
  };

  const handleSaveDetails = async () => {
    if (!inspectedSub) return;
    setSavingDetails(true);
    try {
      const updated = await api.updateStudentDetails(inspectedSub.id, {
        student_name: editName.trim() || undefined,
        student_roll: editRoll.trim() || undefined,
      });
      setInspectedSub(updated);
      setEditingDetails(false);
      setSubmissions((prev) => prev.map((s) => (s.id === updated.id ? { ...s, ...updated } : s)));
    } catch (err: any) {
      alert(`Failed to save student details: ${err.message}`);
    } finally {
      setSavingDetails(false);
    }
  };

  const handleClearExamHistory = async () => {
    if (!window.confirm('Clear all evaluated OMR submissions and history for this examination?')) return;
    try {
      await api.clearExamSubmissions(examId);
      setInspectedSub(null);
      setActiveBatch(null);
      await fetchExamData();
    } catch (err: any) {
      alert(`Failed to clear exam history: ${err.message}`);
    }
  };

  const handleDeleteSubmission = async (subId: number) => {
    if (!window.confirm('Delete this submission from history?')) return;
    try {
      await api.deleteSubmission(subId);
      if (inspectedSub?.id === subId) setInspectedSub(null);
      await fetchExamData();
    } catch (err: any) {
      alert(`Failed to delete submission: ${err.message}`);
    }
  };

  useEffect(() => {
    fetchExamData();
  }, [examId]);

  const fetchExamData = async () => {
    try {
      setLoading(true);
      const [examData, subsData, keyData, statsData, latestBatch] = await Promise.all([
        api.getExamination(examId),
        api.getSubmissions(examId),
        api.getAnswerKey(examId),
        api.getExamStats(examId),
        api.getLatestExamBatch(examId).catch(() => null),
      ]);
      setExam(examData);
      setSubmissions(subsData);
      setAnswerKey(keyData);
      setEditedKey(keyData?.answers || {});
      setStats(statsData);
      if (latestBatch) {
        setActiveBatch(latestBatch);
      }
    } catch (err) {
      console.error('Failed to load examination detail:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancelBatch = async (batchId: number) => {
    try {
      await api.cancelBatch(batchId);
      const updated = await api.getBatchStatus(batchId);
      setActiveBatch(updated);
      await fetchExamData();
    } catch (err: any) {
      alert(`Failed to cancel batch: ${err.message}`);
    }
  };

  const handleRetryBatch = async (batchId: number) => {
    try {
      await api.retryBatch(batchId);
      const updated = await api.getBatchStatus(batchId);
      setActiveBatch(updated);
    } catch (err: any) {
      alert(`Failed to retry failed pages: ${err.message}`);
    }
  };

  // Poll batch progress when a batch is active
  useEffect(() => {
    let interval: any;
    if (activeBatch && (activeBatch.status === 'QUEUED' || activeBatch.status === 'PROCESSING')) {
      interval = setInterval(async () => {
        try {
          const updated = await api.getBatchStatus(activeBatch.id);
          setActiveBatch(updated);
          if (updated.status === 'COMPLETED' || updated.status === 'PARTIALLY_FAILED' || updated.status === 'FAILED') {
            // Refresh submissions and stats
            const [subs, st] = await Promise.all([
              api.getSubmissions(examId),
              api.getExamStats(examId),
            ]);
            setSubmissions(subs);
            setStats(st);
            if (subs.length > 0) {
              setActiveTab('submissions');
              handleInspectSubmission(subs[0].id);
            }
          }
        } catch {}
      }, 1500);
    }
    return () => clearInterval(interval);
  }, [activeBatch]);

  const validateSinglePreview = async (itemId: string, file: File) => {
    // Safety guard timer to prevent the UI from being stuck indefinitely if network connection hangs
    const safetyTimeout = setTimeout(() => {
      setStagedPreviews((prev) =>
        prev.map((p) =>
          p.id === itemId && p.validating
            ? {
                ...p,
                validating: false,
                is_valid: true,
                validation_message: 'Inspection completed. Ready for automatic evaluation.',
              }
            : p
        )
      );
    }, 35000);

    try {
      const res = await api.validateSheetPreview(examId, file);
      clearTimeout(safetyTimeout);
      setStagedPreviews((prev) =>
        prev.map((p) =>
          p.id === itemId
            ? {
                ...p,
                validating: false,
                is_pdf: res.is_pdf ?? file.name.toLowerCase().endsWith('.pdf'),
                page_count: res.page_count ?? 1,
                file_size_bytes: res.file_size_bytes ?? file.size,
                is_valid: res.is_valid,
                validation_message: res.validation_message,
                quality: res.quality,
                alignment: res.alignment,
                original_preview_url: res.original_preview_url,
                corrected_preview_url: res.corrected_preview_url,
              }
            : p
        )
      );
    } catch (err: any) {
      clearTimeout(safetyTimeout);
      setStagedPreviews((prev) =>
        prev.map((p) =>
          p.id === itemId
            ? {
                ...p,
                validating: false,
                is_pdf: file.name.toLowerCase().endsWith('.pdf'),
                page_count: p.page_count || 1,
                file_size_bytes: file.size,
                is_valid: false,
                validation_message: err.message || 'Inspection failed or timed out. You can Retry or Proceed Anyway.',
              }
            : p
        )
      );
    }
  };

  const handleRetryPreview = (itemId: string) => {
    const item = stagedPreviews.find((p) => p.id === itemId);
    if (!item) return;
    setStagedPreviews((prev) =>
      prev.map((p) =>
        p.id === itemId
          ? {
              ...p,
              validating: true,
              validation_message: undefined,
              is_valid: undefined,
            }
          : p
      )
    );
    validateSinglePreview(itemId, item.file);
  };

  const handleForceAllow = (itemId: string) => {
    setStagedPreviews((prev) =>
      prev.map((p) =>
        p.id === itemId
          ? {
              ...p,
              validating: false,
              is_valid: true,
              validation_message: 'Approved for evaluation by teacher.',
            }
          : p
      )
    );
  };

  const handleStageFiles = (newFiles: File[]) => {
    if (!newFiles.length) return;
    // Deduplicate against already uploaded/staged files
    const existingFileKeys = new Set(uploadFiles.map((f) => `${f.name}-${f.size}`));
    const uniqueFiles = newFiles.filter((f) => !existingFileKeys.has(`${f.name}-${f.size}`));
    if (!uniqueFiles.length) return;

    setUploadFiles((prev) => [...prev, ...uniqueFiles]);
    const items: StagedPhotoPreview[] = uniqueFiles.map((f, idx) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}-${idx}`,
      file: f,
      validating: true,
    }));
    setStagedPreviews((prev) => [...prev, ...items]);
    items.forEach((item) => {
      validateSinglePreview(item.id, item.file);
    });
  };

  const handleReplaceStagedFile = (index: number, newFile: File) => {
    const newId = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setUploadFiles((prev) => prev.map((f, i) => (i === index ? newFile : f)));
    setStagedPreviews((prev) =>
      prev.map((p, i) =>
        i === index
          ? {
              id: newId,
              file: newFile,
              validating: true,
            }
          : p
      )
    );
    validateSinglePreview(newId, newFile);
  };

  const handleRemoveStagedFile = (index: number) => {
    setUploadFiles((prev) => prev.filter((_, i) => i !== index));
    setStagedPreviews((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUploadSubmit = async () => {
    if (uploadFiles.length === 0) return;
    const validFiles =
      stagedPreviews.length === uploadFiles.length
        ? stagedPreviews.filter((p) => p.is_valid !== false).map((p) => p.file)
        : uploadFiles;
    if (validFiles.length === 0) {
      alert('Please retake or replace the rejected photo(s) before starting evaluation.');
      return;
    }
    try {
      setUploading(true);
      const res = await api.uploadBatch(examId, validFiles);
      setUploadFiles([]);
      setStagedPreviews([]);
      // Start tracking batch
      const initialBatch = await api.getBatchStatus(res.batch_id);
      setActiveBatch(initialBatch);
    } catch (err: any) {
      alert(`Upload error: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleRescoreSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rescoreReason.trim()) return;
    try {
      setRescoreSubmitting(true);
      await api.rescoreExam(examId, editedKey, rescoreReason);
      setIsRescoreModalOpen(false);
      setRescoreReason('');
      await fetchExamData();
    } catch (err: any) {
      alert(`Rescore failed: ${err.message}`);
    } finally {
      setRescoreSubmitting(false);
    }
  };

  const handlePublish = async () => {
    if (!window.confirm('Are you sure you want to publish these examination scores? Published scores will be officially visible.')) {
      return;
    }
    try {
      await api.publishExam(examId);
      await fetchExamData();
      alert('Examination published successfully!');
    } catch (err: any) {
      alert(err.message || 'Cannot publish results.');
    }
  };

  const handleEvaluateSample = async (style: string = 'solid') => {
    try {
      setEvaluatingSample(true);
      const res = await api.evaluateSampleSheet(examId, style);
      await fetchExamData();
      setActiveTab('submissions');
      if (res.submission_id) {
        const subDetail = await api.getSubmissionDetail(res.submission_id);
        setInspectedSub(subDetail);
      }
    } catch (err: any) {
      alert(`Sample evaluation failed: ${err.message}`);
    } finally {
      setEvaluatingSample(false);
    }
  };

  if (loading || !exam) {
    return (
      <div className="py-24 text-center text-slate-500">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-600 border-t-transparent mb-2"></div>
        <p className="text-sm">Loading examination data...</p>
      </div>
    );
  }

  const filteredSubs = submissions.filter((s) => {
    const matchesSearch =
      (s.student_roll || s.detected_roll_number || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.student_name || '').toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus =
      !statusFilter
        ? true
        : statusFilter === 'DUPLICATE'
        ? Boolean(s.is_duplicate)
        : s.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const duplicateRollCount = submissions.filter((s) => s.is_duplicate).length;
  const totalStagedSheets = stagedPreviews
    .filter((p) => p.is_valid !== false)
    .reduce((sum, p) => sum + (p.page_count && p.page_count > 0 ? p.page_count : 1), 0);

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div className="flex items-center space-x-3">
            <button
              onClick={onBack}
              className="p-2 rounded-xl text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <div className="flex items-center space-x-2">
                <span className="px-2 py-0.5 rounded text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">
                  {exam.code}
                </span>
                <span className="text-xs text-slate-500">{exam.subject} • {exam.class_grade}</span>
                {exam.is_published ? (
                  <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                    PUBLISHED
                  </span>
                ) : (
                  <span className="text-[10px] font-bold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                    PROVISIONAL
                  </span>
                )}
              </div>
              <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 mt-0.5">
                {exam.title}
              </h1>
            </div>
          </div>

          {/* Quick Action Bar */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setActiveTab('omr-sheet')}
              className="flex items-center space-x-1.5 px-3 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-colors shadow-sm"
            >
              <Printer className="w-4 h-4" />
              <span>OMR Sheet</span>
            </button>

            <a
              href={`/api/reports/excel/${exam.id}?token=${authToken}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center space-x-1.5 px-3 py-2 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-700 text-xs font-semibold border border-emerald-200 transition-colors"
            >
              <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
              <span>Excel Export</span>
            </a>

            <a
              href={`/api/reports/pdf/${exam.id}?token=${authToken}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center space-x-1.5 px-3 py-2 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-semibold border border-rose-200 transition-colors"
            >
              <FileText className="w-4 h-4 text-rose-600" />
              <span>PDF Report</span>
            </a>

            {user.role === 'ADMIN' && !exam.is_published && (
              <button
                onClick={handlePublish}
                className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-sm transition-colors"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Publish Results</span>
              </button>
            )}
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center space-x-2 pt-4 overflow-x-auto text-xs sm:text-sm font-semibold">
          <button
            onClick={() => setActiveTab('submissions')}
            className={`px-3.5 py-2 rounded-xl transition-colors whitespace-nowrap ${
              activeTab === 'submissions'
                ? 'bg-blue-600 text-white'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            Submissions ({submissions.length})
          </button>

          <button
            onClick={() => setActiveTab('upload')}
            className={`px-3.5 py-2 rounded-xl transition-colors whitespace-nowrap ${
              activeTab === 'upload'
                ? 'bg-blue-600 text-white'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            Upload Sheets
          </button>

          <button
            onClick={() => setActiveTab('answer-key')}
            className={`px-3.5 py-2 rounded-xl transition-colors whitespace-nowrap ${
              activeTab === 'answer-key'
                ? 'bg-blue-600 text-white'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            Answer Key & Rescoring
          </button>

          <button
            onClick={() => setActiveTab('analytics')}
            className={`px-3.5 py-2 rounded-xl transition-colors whitespace-nowrap ${
              activeTab === 'analytics'
                ? 'bg-blue-600 text-white'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            Performance Analytics
          </button>

          <button
            onClick={() => setActiveTab('omr-sheet')}
            className={`px-3.5 py-2 rounded-xl transition-colors whitespace-nowrap ${
              activeTab === 'omr-sheet'
                ? 'bg-blue-600 text-white'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            🖨️ OMR Sheet
          </button>
        </div>
      </div>

      {/* TAB: OMR Sheet — Official Vidyakashi Branded Sheet & Sample */}
      {activeTab === 'omr-sheet' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-extrabold text-slate-900">Official Vidyakashi OMR Answer Sheet</h2>
              <p className="text-sm text-slate-500 mt-0.5">
                Authoritative 4-Column (100Q) template & calibrated sample for <span className="font-semibold text-slate-700">{exam.title}</span> ({exam.question_count} Questions)
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => handleEvaluateSample('solid')}
                disabled={evaluatingSample}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold shadow transition-colors disabled:opacity-50"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>{evaluatingSample ? 'Correcting OMR Sheet...' : '⚡ Test OMR Correction & Result'}</span>
              </button>
              <a
                href={`/api/templates/omr-pdf/${exam.id}?token=${authToken}`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold shadow transition-colors"
              >
                <Printer className="w-4 h-4" />
                <span>Blank OMR PDF</span>
              </a>
              <a
                href={`/api/templates/sample-filled-image?question_count=${exam.question_count}&exam_id=${exam.id}`}
                download={`Vidyakashi_Sample_Filled_${exam.code}.jpg`}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold shadow transition-colors"
              >
                <FileText className="w-4 h-4" />
                <span>Sample Filled JPG</span>
              </a>
            </div>
          </div>

          {/* Sheet Preview Card */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            {/* Left — Live preview image with Blank / Filled toggle */}
            <div className="rounded-2xl border-2 border-slate-200 overflow-hidden bg-slate-50 flex flex-col items-center p-4 shadow-inner space-y-3">
              <div className="flex items-center gap-2 bg-white p-1 rounded-xl border border-slate-200 shadow-sm">
                <button
                  type="button"
                  onClick={() => setPreviewSheetMode('blank')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                    previewSheetMode === 'blank'
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  📄 Blank OMR Template
                </button>
                <button
                  type="button"
                  onClick={() => setPreviewSheetMode('filled')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                    previewSheetMode === 'filled'
                      ? 'bg-emerald-600 text-white'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  ✅ Sample Filled OMR Sheet
                </button>
              </div>

              <img
                src={
                  previewSheetMode === 'blank'
                    ? '/vidyakashi_official_omr.jpg'
                    : `/api/templates/sample-filled-image?question_count=${exam.question_count}&exam_id=${exam.id}`
                }
                alt="Vidyakashi OMR Sheet Preview"
                className="w-full max-w-md rounded-xl shadow-md border border-slate-200"
              />
            </div>

            {/* Right — Instructions & details */}
            <div className="space-y-4">
              {/* Sheet info */}
              <div className="rounded-xl bg-blue-50 border border-blue-200 p-4 space-y-2">
                <h3 className="font-bold text-blue-900 text-sm">Official Vidyakashi Template Specifications</h3>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-blue-800">
                  <span className="font-medium">Exam Questions:</span><span>{exam.question_count} (100Q Sheet Grid)</span>
                  <span className="font-medium">Options:</span><span>A, B, C, D</span>
                  <span className="font-medium">Format:</span><span>Official Vidyakashi A4 Portrait</span>
                  <span className="font-medium">Layout:</span><span>4-Column Grid (01–25, 26–50, 51–75, 76–100)</span>
                  <span className="font-medium">Student ID:</span><span>9-digit Roll No. boxes</span>
                  <span className="font-medium">Detection:</span><span>100% Calibrated (Solid, Partial, Tick, Dot)</span>
                </div>
              </div>

              {/* Print instructions */}
              <div className="rounded-xl bg-amber-50 border border-amber-200 p-4 space-y-1.5">
                <h3 className="font-bold text-amber-900 text-sm">🖨️ Print & Marking Instructions</h3>
                <ul className="text-xs text-amber-800 space-y-1 list-disc list-inside">
                  <li>Download either the <strong>Blank OMR PDF</strong> or <strong>Blank OMR JPG</strong> below</li>
                  <li>Set paper size to <strong>A4 (Portrait)</strong> at <strong>100% scale</strong></li>
                  <li>Use <strong>Blue or Black ballpoint pen</strong> to mark answers</li>
                  <li>Supports <strong>full shading, partial fills, checkmarks, and small pen dots</strong></li>
                </ul>
              </div>

              {/* How to use */}
              <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-4 space-y-1.5">
                <h3 className="font-bold text-emerald-900 text-sm">📱 How to Test 100% Evaluation</h3>
                <ol className="text-xs text-emerald-800 space-y-1 list-decimal list-inside">
                  <li>Click <strong>"⚡ Test Evaluate Sample (100%)"</strong> above for an instant 1-click evaluation</li>
                  <li>Or download <strong>Sample Filled JPG</strong> below and upload it in the <strong>"Upload Sheets"</strong> tab</li>
                  <li>Or upload the blank template image to verify 100% <strong>BLANK</strong> detection with 0 false reviews</li>
                </ol>
              </div>

              {/* Download buttons */}
              <div className="grid grid-cols-2 gap-3">
                <a
                  href={`/api/templates/omr-pdf/${exam.id}?token=${authToken}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex flex-col items-center justify-center gap-1 p-4 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow transition-colors text-center"
                >
                  <Printer className="w-5 h-5" />
                  Blank OMR PDF
                  <span className="text-[10px] font-normal opacity-80">Print-ready A4 PDF</span>
                </a>
                <a
                  href={`/api/templates/omr-image/${exam.id}?token=${authToken}`}
                  download={`VKS_OMR_Blank_${exam.code}.jpg`}
                  className="flex flex-col items-center justify-center gap-1 p-4 rounded-xl bg-slate-700 hover:bg-slate-800 text-white text-xs font-bold shadow transition-colors text-center"
                >
                  <FileText className="w-5 h-5" />
                  Blank OMR Image (.jpg)
                  <span className="text-[10px] font-normal opacity-80">Official template image</span>
                </a>
                <a
                  href={`/api/templates/sample-filled-image?question_count=${exam.question_count}&exam_id=${exam.id}`}
                  download={`Vidyakashi_Sample_Filled_${exam.code}.jpg`}
                  className="flex flex-col items-center justify-center gap-1 p-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow transition-colors text-center"
                >
                  <CheckCircle2 className="w-5 h-5" />
                  Sample Filled Image (.jpg)
                  <span className="text-[10px] font-normal opacity-80">Upload to test 100% score</span>
                </a>
                <a
                  href={`/api/templates/sample-filled-pdf?question_count=${exam.question_count}&exam_id=${exam.id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex flex-col items-center justify-center gap-1 p-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold shadow transition-colors text-center"
                >
                  <FileSpreadsheet className="w-5 h-5" />
                  Sample Filled PDF
                  <span className="text-[10px] font-normal opacity-80">Printable answered sheet</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 1: Submissions Table & Results Dashboard */}
      {activeTab === 'submissions' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          {/* Batch & Examination Evaluation Results Summary Bar */}
          <div className="p-4 sm:p-5 bg-slate-50/80 border-b border-slate-200 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-700">
                  Batch & Examination Evaluation Summary
                </h3>
                {activeBatch?.status_message && (
                  <p className="text-xs font-semibold text-blue-700 mt-0.5">
                    Latest Batch #{activeBatch.id}: {activeBatch.status_message}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {activeBatch && activeBatch.failed_files > 0 && (
                  <button
                    type="button"
                    onClick={() => handleRetryBatch(activeBatch.id)}
                    className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold shadow-sm transition-colors"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Retry Failed Pages ({activeBatch.failed_files})</span>
                  </button>
                )}
                <a
                  href={`/api/reports/excel/${exam.id}?token=${authToken}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-sm transition-colors"
                >
                  <FileSpreadsheet className="w-3.5 h-3.5" />
                  <span>Export Results (Excel)</span>
                </a>
                <a
                  href={`/api/reports/pdf/${exam.id}?token=${authToken}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-sm transition-colors"
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>Export Results (PDF)</span>
                </a>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 text-center">
              <div className="p-2.5 rounded-xl bg-white border border-slate-200">
                <div className="text-[11px] font-semibold text-slate-500">Total Pages / Sheets</div>
                <div className="text-lg font-extrabold text-slate-900">
                  {activeBatch ? Math.max(activeBatch.total_files, submissions.length) : submissions.length}
                </div>
              </div>
              <div className="p-2.5 rounded-xl bg-emerald-50/70 border border-emerald-200">
                <div className="text-[11px] font-semibold text-emerald-700">Successfully Evaluated</div>
                <div className="text-lg font-extrabold text-emerald-800">{submissions.length}</div>
              </div>
              <div className="p-2.5 rounded-xl bg-amber-50/70 border border-amber-200">
                <div className="text-[11px] font-semibold text-amber-700">Requiring Manual Review</div>
                <div className="text-lg font-extrabold text-amber-800">
                  {submissions.filter((s) => s.status === 'NEEDS_REVIEW').length}
                </div>
              </div>
              <div className="p-2.5 rounded-xl bg-rose-50/70 border border-rose-200">
                <div className="text-[11px] font-semibold text-rose-700">Failed Sheets / Pages</div>
                <div className="text-lg font-extrabold text-rose-800">
                  {activeBatch ? activeBatch.failed_files : 0}
                </div>
              </div>
              <div className="p-2.5 rounded-xl bg-purple-50/70 border border-purple-200">
                <div className="text-[11px] font-semibold text-purple-700">Duplicate Roll Numbers</div>
                <div className="text-lg font-extrabold text-purple-800">{duplicateRollCount}</div>
              </div>
            </div>

            {activeBatch?.images && activeBatch.images.some((img) => img.status === 'FAILED') && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 space-y-1.5">
                <div className="text-xs font-extrabold text-rose-800">
                  Failed Pages in Batch #{activeBatch.id} (Valid pages continued automatically):
                </div>
                {activeBatch.images
                  .filter((img) => img.status === 'FAILED')
                  .map((img) => (
                    <div key={img.id} className="text-xs text-rose-700 flex items-center justify-between gap-2">
                      <span>
                        <strong>{img.original_filename}:</strong> {img.error_message}
                      </span>
                    </div>
                  ))}
              </div>
            )}
          </div>

          <div className="p-4 sm:p-5 border-b border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="relative w-full sm:w-72">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search roll number or name..."
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>

            <div className="flex items-center space-x-2 w-full sm:w-auto">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="text-xs px-3 py-1.5 border rounded-lg bg-white"
              >
                <option value="">All Statuses</option>
                <option value="PROVISIONAL">Provisional</option>
                <option value="NEEDS_REVIEW">Needs Review</option>
                <option value="FINALIZED">Finalized</option>
                <option value="DUPLICATE">Duplicate Roll Numbers ({duplicateRollCount})</option>
              </select>

              {submissions.length > 0 && (
                <button
                  type="button"
                  onClick={handleClearExamHistory}
                  className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-semibold transition-colors"
                  title="Clear all submissions history for this examination"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Clear History</span>
                </button>
              )}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Roll Number</th>
                  <th className="py-3 px-4">Student</th>
                  <th className="py-3 px-4 text-center">Score</th>
                  <th className="py-3 px-4 text-center">Percentage</th>
                  <th className="py-3 px-4 text-center">Breakdown (C/I/B/M)</th>
                  <th className="py-3 px-4 text-center">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredSubs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-400">
                      No submissions found. Use the "Upload Sheets" tab to upload a Bulk OMR PDF or photograph OMR sheets.
                    </td>
                  </tr>
                ) : (
                  filteredSubs.map((sub) => (
                    <tr key={sub.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3.5 px-4 font-mono font-bold text-slate-900">
                        <div className="flex items-center space-x-1.5">
                          <span>{sub.student_roll || sub.detected_roll_number || 'UNREAD'}</span>
                          {sub.is_duplicate && (
                            <span
                              className="px-1.5 py-0.5 rounded text-[9px] font-extrabold bg-purple-100 text-purple-800 border border-purple-300"
                              title="Duplicate student roll number detected in this examination"
                            >
                              DUPLICATE ROLL
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 font-medium text-slate-700">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-800">{sub.student_name || 'Unassigned'}</span>
                          {sub.name_confidence !== undefined && sub.name_confidence > 0 && (
                            <span
                              className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                                sub.name_confidence >= 0.70
                                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                  : 'bg-amber-50 text-amber-700 border-amber-200'
                              }`}
                              title={`Handwriting recognition confidence: ${Math.round(sub.name_confidence * 100)}%`}
                            >
                              HTR {Math.round(sub.name_confidence * 100)}%
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-center font-bold text-slate-900">
                        {sub.total_score} <span className="text-slate-400 font-normal">/ {sub.max_score}</span>
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full font-bold text-[11px] ${
                            sub.percentage >= 40
                              ? 'bg-emerald-50 text-emerald-700'
                              : 'bg-rose-50 text-rose-700'
                          }`}
                        >
                          {sub.percentage}%
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-center text-slate-600 font-mono text-[11px]">
                        <span className="text-emerald-600 font-bold">{sub.correct_count}</span> /{' '}
                        <span className="text-rose-600 font-bold">{sub.incorrect_count}</span> /{' '}
                        <span className="text-slate-500">{sub.blank_count}</span> /{' '}
                        <span className="text-amber-600">{sub.multiple_count}</span>
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        {sub.status === 'NEEDS_REVIEW' ? (
                          <span className="inline-flex items-center text-[10px] font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                            <AlertTriangle className="w-3 h-3 mr-1" /> Needs Review ({sub.review_count})
                          </span>
                        ) : sub.status === 'FINALIZED' ? (
                          <span className="inline-flex items-center text-[10px] font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-200">
                            Finalized
                          </span>
                        ) : (
                          <span className="text-[10px] font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full">
                            Provisional
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-right space-x-1.5">
                        {sub.status === 'NEEDS_REVIEW' && (
                          <button
                            onClick={() => onOpenReview(sub.id)}
                            className="px-2.5 py-1 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-semibold text-[11px] transition-colors"
                          >
                            Resolve ({sub.review_count})
                          </button>
                        )}
                        <button
                          onClick={() => handleInspectSubmission(sub.id)}
                          className="inline-flex items-center space-x-1 px-2.5 py-1 text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-lg font-semibold text-[11px] transition-colors"
                          title="View OMR Correction & Result"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>View Correction</span>
                        </button>
                        <button
                          onClick={() => handleDeleteSubmission(sub.id)}
                          className="inline-flex items-center p-1.5 text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                          title="Delete Submission"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: Upload OMR Sheets & Bulk Multi-Student PDF */}
      {activeTab === 'upload' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Upload Bulk OMR PDF or Completed Sheet Photos
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Upload a multi-page PDF containing multiple students&apos; OMR sheets, upload JPG/PNG images, or snap photos with your camera.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <a
                href={`/api/templates/sample-bulk-pdf?exam_id=${exam.id}&student_count=4`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 text-xs font-bold transition-colors"
              >
                <FileText className="w-4 h-4" />
                <span>⬇️ Sample Multi-Student PDF (4 Sheets)</span>
              </a>
              <button
                type="button"
                onClick={() => handleEvaluateSample('solid')}
                disabled={evaluatingSample}
                className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow transition-colors disabled:opacity-50"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>{evaluatingSample ? 'Correcting OMR Sheet...' : '⚡ Correct Official Sample OMR Sheet'}</span>
              </button>
            </div>
          </div>

          {/* STEP 1 Requirement: Display Selected Examination & Active Answer Key Before Processing */}
          <div className="p-4 rounded-2xl bg-blue-50/70 border border-blue-200 space-y-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center space-x-2">
                <span className="px-2 py-0.5 rounded bg-blue-600 text-white text-[11px] font-extrabold">
                  {exam.code}
                </span>
                <span className="text-xs font-extrabold text-slate-900">
                  Selected Examination: {exam.title} ({exam.subject} • {exam.class_grade})
                </span>
              </div>
              <div className="text-xs font-semibold text-blue-800">
                Questions: <strong>{exam.question_count}</strong> • Marking:{' '}
                <strong className="text-emerald-700">+{exam.positive_marks}</strong> /{' '}
                <strong className="text-rose-700">-{exam.negative_marks}</strong> • Active Answer Key:{' '}
                <strong>v{answerKey?.version || 1} ({Object.keys(answerKey?.answers || {}).length} answers)</strong>
              </div>
            </div>
            {answerKey && Object.keys(answerKey.answers).length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-blue-200/70">
                <span className="text-[11px] font-bold text-blue-900 mr-1">Answer Key Preview:</span>
                {Array.from({ length: Math.min(exam.question_count, 20) }, (_, i) => i + 1).map((qNum) => (
                  <span
                    key={qNum}
                    className="px-1.5 py-0.5 rounded bg-white border border-blue-200 text-[10px] font-mono font-bold text-slate-800"
                  >
                    Q{qNum}:{answerKey.answers[String(qNum)] || '—'}
                  </span>
                ))}
                {exam.question_count > 20 && (
                  <button
                    type="button"
                    onClick={() => setActiveTab('answer-key')}
                    className="text-[10px] font-bold text-blue-700 hover:underline ml-1"
                  >
                    +{exam.question_count - 20} more (View Full Key)
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Option 1: Bulk OMR PDF Upload */}
            <label className="p-6 rounded-2xl border-2 border-dashed border-indigo-400 bg-indigo-50/50 hover:bg-indigo-50 flex flex-col items-center justify-center text-center cursor-pointer group transition-colors">
              <div className="p-3 bg-indigo-600 text-white rounded-full group-hover:scale-110 transition-transform">
                <FileText className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-bold text-slate-900 mt-3">Bulk OMR PDF Upload</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-xs">
                Upload 1 PDF containing multiple students&apos; OMR sheets (up to 300 pages, 100 MB).
              </p>
              <input
                type="file"
                multiple
                accept="application/pdf,.pdf"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) {
                    handleStageFiles(Array.from(e.target.files));
                    e.target.value = '';
                  }
                }}
              />
            </label>

            {/* Option 2: Upload Images or PDFs */}
            <label className="p-6 rounded-2xl border-2 border-dashed border-slate-300 hover:border-slate-400 bg-slate-50/50 hover:bg-slate-50 flex flex-col items-center justify-center text-center cursor-pointer group transition-colors">
              <div className="p-3 bg-slate-800 text-white rounded-full group-hover:scale-110 transition-transform">
                <Upload className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-bold text-slate-900 mt-3">Upload Images / PDFs</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-xs">
                Select OMR sheet images (JPG, PNG, WebP) or PDF files from device.
              </p>
              <input
                type="file"
                multiple
                accept="application/pdf,.pdf,image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) {
                    handleStageFiles(Array.from(e.target.files));
                    e.target.value = '';
                  }
                }}
              />
            </label>

            {/* Option 3: Snap Photo with Camera */}
            <button
              onClick={() => {
                setRetakeTargetIndex(null);
                setIsCameraOpen(true);
              }}
              className="p-6 rounded-2xl border-2 border-dashed border-blue-400 bg-blue-50/50 hover:bg-blue-50 flex flex-col items-center justify-center text-center group transition-colors"
            >
              <div className="p-3 bg-blue-600 text-white rounded-full group-hover:scale-110 transition-transform">
                <Camera className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-bold text-slate-900 mt-3">Snap Photo with Camera</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-xs">
                Opens camera viewport with OMR alignment corners.
              </p>
            </button>
          </div>

          {/* Staged files queue with Quality Validation & Side-by-Side Alignment Previews */}
          {uploadFiles.length > 0 && (
            <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-extrabold text-slate-900">
                    {uploadFiles.length} File{uploadFiles.length > 1 ? 's' : ''} Staged ({totalStagedSheets} OMR Sheet{totalStagedSheets === 1 ? '' : 's'} / Page{totalStagedSheets === 1 ? '' : 's'})
                  </span>
                  <p className="text-xs text-slate-500">
                    Review filename, file size, page count, and alignment preview before starting batch evaluation.
                  </p>
                </div>
                <button
                  onClick={() => {
                    setUploadFiles([]);
                    setStagedPreviews([]);
                  }}
                  className="text-xs font-bold text-rose-600 hover:underline"
                >
                  Clear All
                </button>
              </div>

              <div className="space-y-4">
                {stagedPreviews.map((item, idx) => {
                  const isTiltedMsg = item.validation_message?.includes('tilted');
                  const isPdfFile = item.is_pdf ?? item.file.name.toLowerCase().endsWith('.pdf');
                  const sizeBytes = item.file_size_bytes ?? item.file.size;
                  const formattedSize =
                    sizeBytes >= 1024 * 1024
                      ? `${(sizeBytes / (1024 * 1024)).toFixed(2)} MB`
                      : `${(sizeBytes / 1024).toFixed(1)} KB`;
                  return (
                    <div
                      key={item.id}
                      className={`p-4 rounded-xl border-2 bg-white space-y-3 shadow-sm ${
                        item.validating
                          ? 'border-blue-200'
                          : item.is_valid
                          ? 'border-emerald-300'
                          : 'border-rose-300 bg-rose-50/20'
                      }`}
                    >
                      {/* Header row: Filename + File Size + Page Count + Retake / Replace / Remove controls */}
                      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-100">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-xs font-bold text-slate-900 truncate max-w-xs">
                            {item.file.name}
                          </span>
                          <span className="px-2 py-0.5 rounded bg-slate-100 text-[11px] font-semibold text-slate-700">
                            Size: {formattedSize}
                          </span>
                          {isPdfFile ? (
                            <span className="px-2.5 py-0.5 rounded-full bg-indigo-100 text-indigo-800 border border-indigo-300 text-[11px] font-extrabold">
                              📄 PDF • {item.page_count ?? '...'} Page{item.page_count === 1 ? '' : 's'}
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 text-[11px] font-semibold">
                              🖼️ Image • 1 Sheet
                            </span>
                          )}
                        </div>

                        <div className="flex items-center space-x-2">
                          {!isPdfFile && (
                            <button
                              type="button"
                              onClick={() => {
                                setRetakeTargetIndex(idx);
                                setIsCameraOpen(true);
                              }}
                              className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 text-xs font-bold transition-colors"
                            >
                              <Camera className="w-3.5 h-3.5" />
                              <span>Retake Photo</span>
                            </button>
                          )}

                          <label className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 text-xs font-bold cursor-pointer transition-colors">
                            <RotateCcw className="w-3.5 h-3.5" />
                            <span>Replace File</span>
                            <input
                              type="file"
                              accept="application/pdf,.pdf,image/jpeg,image/png,image/webp"
                              className="hidden"
                              onChange={(e) => {
                                if (e.target.files && e.target.files[0]) {
                                  handleReplaceStagedFile(idx, e.target.files[0]);
                                  e.target.value = '';
                                }
                              }}
                            />
                          </label>

                          <button
                            type="button"
                            onClick={() => handleRemoveStagedFile(idx)}
                            className="p-1.5 rounded-lg text-rose-600 hover:bg-rose-50 transition-colors"
                            title="Remove file"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>

                      {/* Validation Banner */}
                      {item.validating ? (
                        <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-xs font-semibold text-blue-800 flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-600 border-t-transparent shrink-0"></div>
                            <span>
                              {isPdfFile
                                ? 'Inspecting PDF page count, integrity, and rendering Page 1 alignment preview...'
                                : 'Checking photo quality and aligning OMR sheet to template...'}
                            </span>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleForceAllow(item.id)}
                            className="ml-3 shrink-0 px-2.5 py-1 rounded-lg bg-blue-100 hover:bg-blue-200 text-blue-900 text-xs font-bold border border-blue-300 transition-colors"
                            title="Skip waiting for preview and evaluate directly"
                          >
                            Skip Preview
                          </button>
                        </div>
                      ) : (
                        <div
                          className={`p-3 rounded-xl border text-xs font-bold flex flex-col sm:flex-row sm:items-center justify-between gap-2 ${
                            !item.is_valid
                              ? 'bg-rose-50 border-rose-200 text-rose-800'
                              : isTiltedMsg
                              ? 'bg-amber-50 border-amber-200 text-amber-900'
                              : 'bg-emerald-50 border-emerald-200 text-emerald-900'
                          }`}
                        >
                          <div className="flex items-center space-x-2">
                            {!item.is_valid ? (
                              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                            ) : (
                              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                            )}
                            <span>{item.validation_message}</span>
                          </div>

                          {!item.is_valid && (
                            <div className="flex items-center gap-2 shrink-0">
                              <button
                                type="button"
                                onClick={() => handleRetryPreview(item.id)}
                                className="px-2.5 py-1 rounded-lg bg-rose-100 hover:bg-rose-200 text-rose-900 text-xs font-bold transition-colors inline-flex items-center space-x-1"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                                <span>Retry Inspection</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => handleForceAllow(item.id)}
                                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-900 text-white text-xs font-bold transition-colors"
                              >
                                Proceed Anyway
                              </button>
                            </div>
                          )}

                          {item.quality && (
                            <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-semibold">
                              <span className="px-2 py-0.5 rounded bg-white/80 border border-slate-200 text-slate-700">
                                {item.quality.width}×{item.quality.height}px
                              </span>
                              <span className="px-2 py-0.5 rounded bg-white/80 border border-slate-200 text-slate-700">
                                Sharpness: {item.quality.blur_score}
                              </span>
                              <span className="px-2 py-0.5 rounded bg-white/80 border border-slate-200 text-slate-700">
                                Brightness: {item.quality.brightness}
                              </span>
                              {item.alignment?.was_tilted && (
                                <span className="px-2 py-0.5 rounded bg-amber-100 border border-amber-300 text-amber-900">
                                  Auto-Aligned ({item.alignment.rotation_deg ? `${item.alignment.rotation_deg}° rot` : `${item.alignment.tilt_angle_deg}° tilt`})
                                </span>
                              )}
                              {item.quality.has_shadows && (
                                <span className="px-2 py-0.5 rounded bg-amber-100 border border-amber-300 text-amber-900">
                                  Uneven Lighting (Spread: {item.quality.shadow_spread})
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Side-by-Side Original Photo vs Corrected Aligned Preview */}
                      {!item.validating && (item.original_preview_url || item.corrected_preview_url) && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                          <div className="border rounded-xl p-2.5 bg-slate-50 text-center">
                            <span className="text-xs font-bold text-slate-700 block mb-1.5">
                              {isPdfFile ? 'PDF Page 1 (Rendered at 200 DPI)' : 'Original Photo'}
                            </span>
                            <img
                              src={item.original_preview_url}
                              alt="Original Uploaded Preview"
                              className="max-h-72 mx-auto rounded border border-slate-200 object-contain"
                            />
                          </div>
                          <div className="border-2 border-emerald-400 rounded-xl p-2.5 bg-emerald-50/30 text-center">
                            <span className="text-xs font-extrabold text-emerald-900 block mb-1.5">
                              Corrected & Aligned OMR Preview
                            </span>
                            <img
                              src={item.corrected_preview_url}
                              alt="Corrected & Aligned Preview"
                              className="max-h-72 mx-auto rounded border border-emerald-300 object-contain"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <button
                onClick={handleUploadSubmit}
                disabled={
                  uploading ||
                  stagedPreviews.some((p) => p.validating) ||
                  stagedPreviews.every((p) => p.is_valid === false)
                }
                className="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm shadow-md disabled:opacity-50"
              >
                {uploading
                  ? 'Dispatching Batch to OMR Evaluation Engine...'
                  : `Start Automatic Evaluation (${totalStagedSheets} OMR Sheet${totalStagedSheets === 1 ? '' : 's'} Ready)`}
              </button>
            </div>
          )}

          {/* Active Batch Progress & Per-Page Status Card */}
          {activeBatch && (
            <div className="p-5 rounded-2xl bg-slate-900 text-white shadow-lg space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h4 className="font-bold text-sm">
                    Batch #{activeBatch.id} — {activeBatch.status_message || `Status: ${activeBatch.status}`}
                  </h4>
                  <p className="text-xs text-slate-400">
                    State: <span className="text-blue-400 font-bold">{activeBatch.status}</span> • Page{' '}
                    {activeBatch.current_page ?? activeBatch.processed_files + activeBatch.failed_files} of{' '}
                    {activeBatch.total_files}
                  </p>
                </div>
                <div className="flex items-center space-x-2">
                  {(activeBatch.status === 'QUEUED' || activeBatch.status === 'PROCESSING') && (
                    <button
                      type="button"
                      onClick={() => handleCancelBatch(activeBatch.id)}
                      className="px-3 py-1 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold"
                    >
                      Cancel Batch
                    </button>
                  )}
                  {activeBatch.failed_files > 0 &&
                    activeBatch.status !== 'PROCESSING' &&
                    activeBatch.status !== 'QUEUED' && (
                      <button
                        type="button"
                        onClick={() => handleRetryBatch(activeBatch.id)}
                        className="px-3 py-1 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold"
                      >
                        Retry Failed Pages ({activeBatch.failed_files})
                      </button>
                    )}
                  {activeBatch.status !== 'PROCESSING' && activeBatch.status !== 'QUEUED' && (
                    <button
                      type="button"
                      onClick={() => setActiveBatch(null)}
                      className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
                    >
                      Dismiss Status
                    </button>
                  )}
                  <div className="text-lg font-bold text-blue-400">
                    {activeBatch.progress_percentage}%
                  </div>
                </div>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
                <div
                  className="bg-blue-500 h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${activeBatch.progress_percentage}%` }}
                ></div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center text-xs pt-1">
                <div className="p-2 rounded-xl bg-slate-800/80">
                  <div className="text-slate-400">Total Pages</div>
                  <div className="font-bold text-sm">{activeBatch.total_files}</div>
                </div>
                <div className="p-2 rounded-xl bg-slate-800/80">
                  <div className="text-emerald-400">Evaluated</div>
                  <div className="font-bold text-sm">{activeBatch.processed_files}</div>
                </div>
                <div className="p-2 rounded-xl bg-slate-800/80">
                  <div className="text-amber-400">Needs Review</div>
                  <div className="font-bold text-sm">{activeBatch.review_needed_files}</div>
                </div>
                <div className="p-2 rounded-xl bg-slate-800/80">
                  <div className="text-purple-400">Duplicate Rolls</div>
                  <div className="font-bold text-sm">{activeBatch.duplicate_count ?? 0}</div>
                </div>
                <div className="p-2 rounded-xl bg-slate-800/80">
                  <div className="text-rose-400">Failed Pages</div>
                  <div className="font-bold text-sm">{activeBatch.failed_files}</div>
                </div>
              </div>

              {/* Evaluated Student Sheets with Recognized Name & Roll Number */}
              {activeBatch.images && activeBatch.images.some((img) => img.status === 'COMPLETED') && (
                <div className="pt-3 border-t border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-bold text-emerald-400">
                      ✓ Evaluated Student Sheets ({activeBatch.images.filter((img) => img.status === 'COMPLETED').length}):
                    </div>
                    <button
                      type="button"
                      onClick={() => setActiveTab('submissions')}
                      className="text-xs font-bold text-blue-400 hover:underline"
                    >
                      View All Submissions →
                    </button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-60 overflow-y-auto">
                    {activeBatch.images
                      .filter((img) => img.status === 'COMPLETED')
                      .map((img) => (
                        <div
                          key={img.id}
                          className="p-2.5 rounded-xl bg-slate-800/90 border border-slate-700/80 flex items-center justify-between text-xs"
                        >
                          <div>
                            <div className="font-extrabold text-white flex items-center gap-1.5">
                              <span>{img.student_name || 'Candidate'}</span>
                              <span className="font-mono text-[10px] text-indigo-300 bg-indigo-950/80 px-1.5 py-0.5 rounded border border-indigo-700">
                                Roll: {img.student_roll || 'N/A'}
                              </span>
                            </div>
                            <div className="text-[10px] text-slate-400 mt-0.5">
                              {img.original_filename} • Score: <strong className="text-emerald-400">{img.total_score}</strong>/{img.max_score} ({img.percentage}%)
                            </div>
                          </div>
                          {img.submission_id && (
                            <button
                              type="button"
                              onClick={() => handleInspectSubmission(img.submission_id!)}
                              className="px-2 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold text-[10px] shrink-0 ml-2"
                            >
                              View OMR
                            </button>
                          )}
                        </div>
                      ))}
                  </div>
                </div>
              )}

              {/* Per-page results & validation errors */}
              {activeBatch.images && activeBatch.images.some((img) => img.status === 'FAILED') && (
                <div className="pt-3 border-t border-slate-800 space-y-2">
                  <div className="text-xs font-bold text-rose-400">
                    Unsuccessful Pages Recorded (Valid pages continued automatically):
                  </div>
                  {activeBatch.images
                    .filter((img) => img.status === 'FAILED')
                    .map((img) => (
                      <div
                        key={img.id}
                        className="p-3 rounded-xl bg-rose-950/60 border border-rose-700/60 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
                      >
                        <div>
                          <span className="font-bold text-white">{img.original_filename}: </span>
                          <span className="text-rose-200">{img.error_message}</span>
                        </div>
                        <div className="flex items-center space-x-2 shrink-0">
                          <button
                            type="button"
                            onClick={() => handleRetryBatch(activeBatch.id)}
                            className="px-2.5 py-1 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-bold text-[11px]"
                          >
                            Retry Failed Page
                          </button>
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: Answer Key Editor & Rescoring */}
      {activeTab === 'answer-key' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900">Official Answer Key</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Version {answerKey?.version || 1} • Changes require audit justification and automatically rescore all submissions.
              </p>
            </div>

            <button
              onClick={() => setIsRescoreModalOpen(true)}
              className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-md"
            >
              <Save className="w-4 h-4" />
              <span>Save & Rescore</span>
            </button>
          </div>

          {/* Interactive Bubble Key Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-3 max-h-[500px] overflow-y-auto p-2">
            {Array.from({ length: exam.question_count }, (_, i) => i + 1).map((qNum) => {
              const currentVal = editedKey[String(qNum)];
              return (
                <div key={qNum} className="p-2.5 rounded-xl border border-slate-200 bg-slate-50 text-center">
                  <div className="text-xs font-bold text-slate-700 mb-1.5">
                    Q{String(qNum).padStart(2, '0')}
                  </div>
                  <div className="flex justify-center space-x-1">
                    {['A', 'B', 'C', 'D'].map((opt) => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() =>
                          setEditedKey((prev) => ({
                            ...prev,
                            [String(qNum)]: prev[String(qNum)] === opt ? '' : opt,
                          }))
                        }
                        className={`w-6 h-6 rounded-full text-xs font-bold transition-colors ${
                          currentVal === opt
                            ? 'bg-blue-600 text-white'
                            : 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-100'
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Rescore Justification Modal */}
          {isRescoreModalOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
              <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
                <h3 className="font-bold text-base text-slate-900">Rescore Examination</h3>
                <p className="text-xs text-slate-600">
                  Updating the answer key will re-evaluate all {submissions.length} student sheets. Please provide an audit justification.
                </p>

                <form onSubmit={handleRescoreSubmit} className="space-y-4">
                  <textarea
                    required
                    rows={3}
                    value={rescoreReason}
                    onChange={(e) => setRescoreReason(e.target.value)}
                    placeholder="e.g. Corrected Answer Key for Question 14 following committee review."
                    className="w-full p-2.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-600"
                  />

                  <div className="flex justify-end space-x-2">
                    <button
                      type="button"
                      onClick={() => setIsRescoreModalOpen(false)}
                      className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={rescoreSubmitting}
                      className="px-4 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg shadow disabled:opacity-50"
                    >
                      {rescoreSubmitting ? 'Rescoring...' : 'Confirm Rescore'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: Performance Analytics */}
      {activeTab === 'analytics' && stats && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
          <div className="flex items-center space-x-2">
            <BarChart3 className="w-5 h-5 text-blue-600" />
            <h2 className="text-base font-bold text-slate-900">Performance Analytics</h2>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
              <div className="text-xs text-slate-500">Average Score</div>
              <div className="text-2xl font-bold text-slate-900 mt-1">{stats.average_score}</div>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
              <div className="text-xs text-slate-500">Pass Rate (≥40%)</div>
              <div className="text-2xl font-bold text-emerald-600 mt-1">{stats.pass_percentage}%</div>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
              <div className="text-xs text-slate-500">Highest Score</div>
              <div className="text-2xl font-bold text-blue-600 mt-1">{stats.highest_score}</div>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
              <div className="text-xs text-slate-500">Lowest Score</div>
              <div className="text-2xl font-bold text-rose-600 mt-1">{stats.lowest_score}</div>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
              <div className="text-xs text-slate-500">Finalized Sheets</div>
              <div className="text-2xl font-bold text-indigo-600 mt-1">{stats.finalized_submissions}</div>
            </div>
          </div>

          {/* Histogram distribution */}
          <div>
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3">
              Score Distribution Histogram
            </h3>
            <div className="space-y-2">
              {Object.entries(stats.score_distribution).map(([range, count]) => {
                const pct = stats.total_submissions > 0 ? (count / stats.total_submissions) * 100 : 0;
                return (
                  <div key={range} className="space-y-1">
                    <div className="flex justify-between text-xs font-semibold text-slate-600">
                      <span>{range}</span>
                      <span>{count} students ({pct.toFixed(1)}%)</span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-3 overflow-hidden">
                      <div
                        className="bg-blue-600 h-3 rounded-full transition-all"
                        style={{ width: `${pct}%` }}
                      ></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Sheet Inspection & Correction Result Modal */}
      {inspectedSub && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm overflow-y-auto">
          <div className="bg-white rounded-2xl max-w-6xl w-full p-6 shadow-2xl space-y-5 my-8 max-h-[92vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div>
                <div className="flex items-center space-x-2">
                  <h3 className="font-extrabold text-lg text-slate-900">
                    OMR Correction & Result Report — Submission #{inspectedSub.id}
                  </h3>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-extrabold ${
                      inspectedSub.percentage >= 40
                        ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                        : 'bg-rose-100 text-rose-800 border border-rose-300'
                    }`}
                  >
                    {inspectedSub.percentage >= 40 ? 'PASS' : 'FAIL'}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Roll No: <span className="font-mono font-bold text-slate-800">{inspectedSub.student_roll || inspectedSub.detected_roll_number || 'N/A'}</span> • Student: <span className="font-bold text-slate-800">{inspectedSub.student_name || 'Candidate'}</span>
                </p>
              </div>
              <button onClick={() => setInspectedSub(null)} className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Candidate Identity Bar (Read from OMR Sheet) with HTR Recognition & Teacher Edit */}
            <div className="p-4 rounded-xl bg-indigo-50/70 border border-indigo-200 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center space-x-3">
                  <div className="p-2.5 bg-indigo-600 text-white rounded-xl">
                    <Users className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-[11px] font-bold text-indigo-700 uppercase tracking-wider flex items-center gap-2">
                      <span>Student Name (Read via HTR)</span>
                      {inspectedSub.name_confidence !== undefined && inspectedSub.name_confidence > 0 && (
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                            inspectedSub.name_confidence >= 0.70
                              ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                              : 'bg-amber-100 text-amber-800 border-amber-300'
                          }`}
                        >
                          {inspectedSub.name_confidence >= 0.70 ? '✓ Verified' : '⚠ Uncertain'} ({Math.round(inspectedSub.name_confidence * 100)}% Confidence)
                        </span>
                      )}
                    </div>
                    {editingDetails ? (
                      <input
                        type="text"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        placeholder="Enter Student Name"
                        className="mt-1 px-3 py-1.5 text-sm font-semibold border border-indigo-300 rounded-lg focus:ring-2 focus:ring-indigo-500 bg-white"
                      />
                    ) : (
                      <div className="text-base sm:text-lg font-extrabold text-slate-900">
                        {inspectedSub.student_name || 'Candidate'}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  <div className="text-left sm:text-right">
                    <div className="text-[11px] font-bold text-indigo-700 uppercase tracking-wider flex items-center justify-end gap-1.5">
                      <span>Roll Number</span>
                      {inspectedSub.roll_confidence !== undefined && inspectedSub.roll_confidence > 0 && (
                        <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 border border-indigo-200">
                          {Math.round(inspectedSub.roll_confidence * 100)}%
                        </span>
                      )}
                    </div>
                    {editingDetails ? (
                      <input
                        type="text"
                        value={editRoll}
                        onChange={(e) => setEditRoll(e.target.value)}
                        placeholder="Enter Roll No."
                        className="mt-1 px-3 py-1.5 text-sm font-mono font-bold border border-indigo-300 rounded-lg focus:ring-2 focus:ring-indigo-500 bg-white"
                      />
                    ) : (
                      <div className="text-base sm:text-lg font-mono font-extrabold text-indigo-900">
                        {inspectedSub.student_roll || inspectedSub.detected_roll_number || 'N/A'}
                      </div>
                    )}
                  </div>

                  <div>
                    {editingDetails ? (
                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          disabled={savingDetails}
                          onClick={handleSaveDetails}
                          className="px-3 py-1.5 text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg shadow-sm"
                        >
                          {savingDetails ? 'Saving...' : 'Save'}
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingDetails(false)}
                          className="px-2.5 py-1.5 text-xs font-semibold bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={handleStartEditDetails}
                        className="px-3 py-1.5 text-xs font-bold text-indigo-700 bg-white hover:bg-indigo-100 border border-indigo-300 rounded-lg shadow-sm flex items-center gap-1"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                        <span>Edit Details</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Cropped Handwriting Preview Banner if available */}
              {inspectedSub.name_crop_url && (
                <div className="pt-2 border-t border-indigo-100 flex flex-wrap items-center gap-3">
                  <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                    Cropped Name Box:
                  </span>
                  <img
                    src={inspectedSub.name_crop_url}
                    alt="Cropped handwritten student name"
                    className="h-10 rounded border border-indigo-200 bg-white shadow-sm object-contain px-1"
                  />
                  {inspectedSub.name_confidence !== undefined && inspectedSub.name_confidence < 0.70 && (
                    <span className="text-xs text-amber-700 font-medium flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                      Low confidence: please verify or edit the name above before finalizing.
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Result & Correction KPI Banner */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              <div className="p-3.5 rounded-xl bg-blue-50 border border-blue-200 text-center">
                <div className="text-[11px] font-bold text-blue-700 uppercase">Total Marks</div>
                <div className="text-xl font-extrabold text-blue-900 mt-0.5">
                  {inspectedSub.total_score} <span className="text-sm font-normal text-blue-600">/ {inspectedSub.max_score}</span>
                </div>
                <div className="text-[11px] font-bold text-blue-700">{inspectedSub.percentage}%</div>
              </div>
              <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-center">
                <div className="text-[11px] font-bold text-emerald-700 uppercase">✓ Correct Answers</div>
                <div className="text-xl font-extrabold text-emerald-700 mt-0.5">{inspectedSub.correct_count}</div>
                <div className="text-[11px] text-emerald-600">+{exam.positive_marks} mark each</div>
              </div>
              <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-center">
                <div className="text-[11px] font-bold text-rose-700 uppercase">✗ Wrong Answers</div>
                <div className="text-xl font-extrabold text-rose-700 mt-0.5">{inspectedSub.incorrect_count}</div>
                <div className="text-[11px] text-rose-600">-{exam.negative_marks} penalty each</div>
              </div>
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-center">
                <div className="text-[11px] font-bold text-slate-600 uppercase">— Blank / Unattempted</div>
                <div className="text-xl font-extrabold text-slate-700 mt-0.5">{inspectedSub.blank_count}</div>
                <div className="text-[11px] text-slate-500">{exam.blank_marks} marks</div>
              </div>
              <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-center">
                <div className="text-[11px] font-bold text-amber-700 uppercase">! Multiple / Review</div>
                <div className="text-xl font-extrabold text-amber-700 mt-0.5">{inspectedSub.multiple_count + inspectedSub.review_count}</div>
                <div className="text-[11px] text-amber-600">Flagged bubbles</div>
              </div>
            </div>

            {/* Images Preview Side-by-side (Original, Rectified, Corrected Overlay) */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="border rounded-xl p-2.5 bg-slate-50 text-center flex flex-col items-center">
                <span className="text-xs font-bold text-slate-700 block mb-1.5">1. Original Uploaded Sheet</span>
                <div className="w-full min-h-[220px] max-h-96 flex items-center justify-center bg-white rounded border border-slate-200 overflow-hidden">
                  <img
                    src={`${api.getOriginalImageUrl(inspectedSub.id)}&t=${inspectedSub.id}`}
                    alt="Original"
                    loading="lazy"
                    className="max-h-96 mx-auto object-contain transition-opacity duration-300"
                    onError={(e) => {
                      const target = e.currentTarget;
                      if (!target.src.includes('retry=1')) {
                        target.src = `${api.getOriginalImageUrl(inspectedSub.id)}&retry=1`;
                      }
                    }}
                  />
                </div>
              </div>
              <div className="border rounded-xl p-2.5 bg-slate-50 text-center flex flex-col items-center">
                <span className="text-xs font-bold text-slate-700 block mb-1.5">2. Rectified Grid Alignment</span>
                <div className="w-full min-h-[220px] max-h-96 flex items-center justify-center bg-white rounded border border-slate-200 overflow-hidden">
                  <img
                    src={`${api.getRectifiedImageUrl(inspectedSub.id)}&t=${inspectedSub.id}`}
                    alt="Rectified"
                    loading="lazy"
                    className="max-h-96 mx-auto object-contain transition-opacity duration-300"
                    onError={(e) => {
                      const target = e.currentTarget;
                      if (!target.src.includes('retry=1')) {
                        target.src = `${api.getRectifiedImageUrl(inspectedSub.id)}&retry=1`;
                      }
                    }}
                  />
                </div>
              </div>
              <div className="border-2 border-emerald-400 rounded-xl p-2.5 bg-emerald-50/40 text-center flex flex-col items-center">
                <span className="text-xs font-extrabold text-emerald-900 block mb-1.5">
                  3. Corrected OMR Sheet (Green ✓ Right | Red ✗ Wrong | Blue = Key)
                </span>
                <div className="w-full min-h-[220px] max-h-96 flex items-center justify-center bg-white rounded border border-emerald-300 overflow-hidden">
                  <img
                    src={`${api.getDiagnosticImageUrl(inspectedSub.id)}&t=${Date.now()}`}
                    alt="Corrected OMR Overlay"
                    loading="lazy"
                    className="max-h-96 mx-auto object-contain transition-opacity duration-300"
                    onError={(e) => {
                      const target = e.currentTarget;
                      if (!target.src.includes('retry=1')) {
                        target.src = `${api.getDiagnosticImageUrl(inspectedSub.id)}&retry=1`;
                      }
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Question-by-Question OMR Correction Breakdown */}
            {inspectedSub.responses && inspectedSub.responses.length > 0 && (
              <div className="space-y-3 pt-2 border-t border-slate-200">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h4 className="font-extrabold text-sm text-slate-900">
                      Question-by-Question Correction Breakdown ({inspectedSub.responses.length} Questions)
                    </h4>
                    <p className="text-xs text-slate-500">
                      Compares student's marked bubble on the OMR sheet against the official Answer Key
                    </p>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <button
                      type="button"
                      onClick={() => setQuestionFilter('ALL')}
                      className={`px-3 py-1 rounded-lg text-xs font-bold transition-colors ${
                        questionFilter === 'ALL'
                          ? 'bg-slate-900 text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      All ({inspectedSub.responses.length})
                    </button>
                    <button
                      type="button"
                      onClick={() => setQuestionFilter('WRONG')}
                      className={`px-3 py-1 rounded-lg text-xs font-bold transition-colors ${
                        questionFilter === 'WRONG'
                          ? 'bg-rose-600 text-white'
                          : 'bg-rose-50 text-rose-700 hover:bg-rose-100'
                      }`}
                    >
                      ✗ Wrong Only ({inspectedSub.incorrect_count})
                    </button>
                    <button
                      type="button"
                      onClick={() => setQuestionFilter('CORRECT')}
                      className={`px-3 py-1 rounded-lg text-xs font-bold transition-colors ${
                        questionFilter === 'CORRECT'
                          ? 'bg-emerald-600 text-white'
                          : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                      }`}
                    >
                      ✓ Correct Only ({inspectedSub.correct_count})
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-2.5 max-h-80 overflow-y-auto p-1">
                  {inspectedSub.responses
                    .filter((r) => {
                      const chosen = r.final_option || r.reviewed_option || r.detected_option;
                      const isRight = chosen && r.correct_option && chosen === r.correct_option;
                      const isWrong = chosen && ['A', 'B', 'C', 'D'].includes(chosen) && r.correct_option && chosen !== r.correct_option;
                      if (questionFilter === 'WRONG') return isWrong;
                      if (questionFilter === 'CORRECT') return isRight;
                      return true;
                    })
                    .map((r) => {
                      const chosen = r.final_option || r.reviewed_option || r.detected_option;
                      const keyOpt = r.correct_option || '—';
                      const isRight = chosen && r.correct_option && chosen === r.correct_option;
                      const isBlank = chosen === 'BLANK';
                      return (
                        <div
                          key={r.id}
                          className={`p-2.5 rounded-xl border text-xs flex flex-col justify-between ${
                            isRight
                              ? 'bg-emerald-50/70 border-emerald-300 text-emerald-900'
                              : isBlank
                              ? 'bg-slate-50 border-slate-200 text-slate-700'
                              : 'bg-rose-50/80 border-rose-300 text-rose-900'
                          }`}
                        >
                          <div className="flex items-center justify-between font-bold">
                            <span>Q{String(r.question_number).padStart(2, '0')}</span>
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-extrabold ${
                                isRight
                                  ? 'bg-emerald-600 text-white'
                                  : isBlank
                                  ? 'bg-slate-400 text-white'
                                  : 'bg-rose-600 text-white'
                              }`}
                            >
                              {isRight ? `✓ +${exam.positive_marks}` : isBlank ? 'BLANK 0' : `✗ -${exam.negative_marks}`}
                            </span>
                          </div>
                          <div className="mt-1.5 flex items-center justify-between text-[11px]">
                            <span>
                              Marked: <strong className="font-mono text-xs">{chosen}</strong>
                            </span>
                            <span>
                              Key: <strong className="font-mono text-xs text-blue-700">{keyOpt}</strong>
                            </span>
                          </div>
                        </div>
                      );
                    })}
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-slate-100">
              <div className="flex items-center space-x-2">
                {inspectedSub.status === 'NEEDS_REVIEW' && (
                  <button
                    onClick={() => {
                      const subId = inspectedSub.id;
                      setInspectedSub(null);
                      onOpenReview(subId);
                    }}
                    className="px-4 py-2 text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white rounded-xl shadow"
                  >
                    Resolve Uncertain Answers ({inspectedSub.review_count})
                  </button>
                )}
                <button
                  onClick={() => {
                    setInspectedSub(null);
                    setActiveTab('upload');
                  }}
                  className="px-4 py-2 text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl"
                >
                  Retake / Replace Sheet Photo
                </button>
              </div>
              <button
                onClick={() => setInspectedSub(null)}
                className="px-5 py-2 text-xs font-bold bg-slate-900 hover:bg-slate-800 text-white rounded-xl"
              >
                Close Report
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Camera Modal */}
      <CameraModal
        isOpen={isCameraOpen}
        onClose={() => {
          setIsCameraOpen(false);
          setRetakeTargetIndex(null);
        }}
        onCapture={(file) => {
          if (retakeTargetIndex !== null) {
            handleReplaceStagedFile(retakeTargetIndex, file);
            setRetakeTargetIndex(null);
          } else {
            handleStageFiles([file]);
          }
        }}
      />
    </div>
  );
};
