import React, { useState, useEffect, useRef } from 'react';
import { Submission, DetectedResponse, OptionClassification } from '../types';
import { api } from '../services/api';
import {
  ArrowLeft,
  AlertTriangle,
  CheckCircle2,
  ZoomIn,
  ZoomOut,
  Save,
  ArrowRight,
  RotateCcw,
  Check,
  ImageOff,
  Layers,
  FileCheck2,
  Camera,
  Edit2,
  Users,
} from 'lucide-react';

/** Fetches a private authenticated image endpoint and returns an object URL. */
function useAuthenticatedImage(url: string | null) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const prevUrl = useRef<string | null>(null);

  useEffect(() => {
    if (!url) {
      setObjectUrl(null);
      setLoading(false);
      setError(false);
      return;
    }
    if (url === prevUrl.current) return;
    prevUrl.current = url;

    let revoked = false;
    setError(false);
    setLoading(true);

    const token = localStorage.getItem('omr_access_token');
    const separator = url.includes('?') ? '&' : '?';
    const fetchUrl = token ? `${url}${separator}token=${encodeURIComponent(token)}` : url;

    fetch(fetchUrl, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.blob();
      })
      .then((blob) => {
        if (revoked) return;
        const objUrl = URL.createObjectURL(blob);
        setObjectUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return objUrl;
        });
        setLoading(false);
      })
      .catch((err) => {
        console.warn('Image fetch failed for URL:', url, err);
        if (!revoked) {
          setError(true);
          setLoading(false);
        }
      });

    return () => {
      revoked = true;
    };
  }, [url]);

  return { objectUrl, error, loading };
}

interface ReviewQueuePageProps {
  examId: number;
  initialSubmissionId?: number;
  onBack: () => void;
}

export const ReviewQueuePage: React.FC<ReviewQueuePageProps> = ({
  examId,
  initialSubmissionId,
  onBack,
}) => {
  const [queue, setQueue] = useState<Submission[]>([]);
  const [currentSubIndex, setCurrentSubIndex] = useState(0);
  const [currentDetail, setCurrentDetail] = useState<Submission | null>(null);
  const [selectedQuestion, setSelectedQuestion] = useState<number | null>(null);
  const [overrideOption, setOverrideOption] = useState<OptionClassification | null>(null);
  const [overrideReason, setOverrideReason] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1);

  // View mode switcher: diagnostic overlay | rectified sheet | original photo
  const [viewMode, setViewMode] = useState<'diagnostic' | 'rectified' | 'original'>('diagnostic');
  const [editingDetails, setEditingDetails] = useState(false);
  const [editName, setEditName] = useState('');
  const [editRoll, setEditRoll] = useState('');
  const [savingDetails, setSavingDetails] = useState(false);

  // Build authenticated image URL based on selected view mode
  const currentImageUrl = currentDetail?.id
    ? `${api.baseUrl}/submissions/${currentDetail.id}/images/${viewMode}`
    : null;
  const { objectUrl, error: imageError, loading: imageLoading } = useAuthenticatedImage(currentImageUrl);

  useEffect(() => {
    loadReviewQueue();
  }, [examId]);

  const loadReviewQueue = async () => {
    try {
      setLoading(true);
      const items = await api.getReviewQueue(examId);
      setQueue(items);

      if (items.length > 0) {
        let targetIdx = 0;
        if (initialSubmissionId) {
          const foundIdx = items.findIndex((s) => s.id === initialSubmissionId);
          if (foundIdx !== -1) targetIdx = foundIdx;
        }
        setCurrentSubIndex(targetIdx);
        await loadSubmissionDetail(items[targetIdx].id);
      }
    } catch (err) {
      console.error('Failed to load review queue:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadSubmissionDetail = async (subId: number) => {
    try {
      const detail = await api.getSubmissionDetail(subId);
      setCurrentDetail(detail);

      // Automatically select the first question flagged for REVIEW
      const firstUncertain = detail.responses?.find(
        (r) => r.detected_option === 'REVIEW' && !r.is_reviewed
      );
      if (firstUncertain) {
        setSelectedQuestion(firstUncertain.question_number);
      } else if (detail.responses && detail.responses.length > 0) {
        setSelectedQuestion(detail.responses[0].question_number);
      }
    } catch (err) {
      console.error('Failed to load detail:', err);
    }
  };

  const handleStartEditDetails = () => {
    if (!currentDetail) return;
    setEditName(currentDetail.student_name || '');
    setEditRoll(currentDetail.student_roll || currentDetail.detected_roll_number || '');
    setEditingDetails(true);
  };

  const handleSaveDetails = async () => {
    if (!currentDetail) return;
    setSavingDetails(true);
    try {
      const updated = await api.updateStudentDetails(currentDetail.id, {
        student_name: editName.trim() || undefined,
        student_roll: editRoll.trim() || undefined,
      });
      setCurrentDetail(updated);
      setEditingDetails(false);
      setQueue((prev) => prev.map((s) => (s.id === updated.id ? { ...s, ...updated } : s)));
    } catch (err: any) {
      alert(`Failed to save student details: ${err.message}`);
    } finally {
      setSavingDetails(false);
    }
  };

  const handleSelectSubmission = async (index: number) => {
    setCurrentSubIndex(index);
    await loadSubmissionDetail(queue[index].id);
  };

  const handleSaveOverride = async () => {
    if (!currentDetail || !selectedQuestion || !overrideOption || !overrideReason.trim()) {
      alert('Please select an answer option and provide an audit reason for the override.');
      return;
    }

    try {
      setSaving(true);
      await api.overrideResponse(
        currentDetail.id,
        selectedQuestion,
        overrideOption,
        overrideReason
      );

      // Refresh detail
      const updated = await api.getSubmissionDetail(currentDetail.id);
      setCurrentDetail(updated);
      setOverrideOption(null);
      setOverrideReason('');

      // If no more reviews in this sheet, prompt or move next
      if (updated.review_count === 0) {
        alert('All uncertain questions for this sheet have been resolved!');
      } else {
        // Move to next uncertain question in sheet
        const nextUncertain = updated.responses?.find(
          (r) => r.detected_option === 'REVIEW' && !r.is_reviewed
        );
        if (nextUncertain) {
          setSelectedQuestion(nextUncertain.question_number);
        }
      }
    } catch (err: any) {
      alert(`Override error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="py-24 text-center text-slate-500">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-600 border-t-transparent mb-2"></div>
        <p className="text-sm">Loading review queue...</p>
      </div>
    );
  }

  if (queue.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-12 text-center max-w-lg mx-auto">
        <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
        <h2 className="text-lg font-bold text-slate-900">Review Queue is Clear!</h2>
        <p className="text-xs text-slate-500 mt-1 mb-6">
          There are no flagged or ambiguous answers requiring human teacher verification in this examination.
        </p>
        <button
          onClick={onBack}
          className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-semibold"
        >
          Return to Examination Console
        </button>
      </div>
    );
  }

  const activeResponse = currentDetail?.responses?.find(
    (r) => r.question_number === selectedQuestion
  );

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4 sm:p-5 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="p-2 rounded-xl text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-lg font-bold text-slate-900">Human Verification Queue</h1>
            <p className="text-xs text-slate-500">
              Sheet {currentSubIndex + 1} of {queue.length} • Roll Number:{' '}
              <span className="font-mono font-bold text-slate-800">
                {currentDetail?.student_roll || currentDetail?.detected_roll_number || 'UNASSIGNED'}
              </span>
            </p>
          </div>
        </div>

        {/* Sheet navigation */}
        <div className="flex items-center space-x-2">
          <button
            disabled={currentSubIndex === 0}
            onClick={() => handleSelectSubmission(currentSubIndex - 1)}
            className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40"
          >
            Previous Sheet
          </button>
          <button
            disabled={currentSubIndex === queue.length - 1}
            onClick={() => handleSelectSubmission(currentSubIndex + 1)}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 shadow-sm"
          >
            Next Sheet
          </button>
        </div>
      </div>

      {/* Candidate Details & HTR Verification Card */}
      {currentDetail && (
        <div className="bg-white rounded-2xl border border-indigo-100 shadow-sm p-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-indigo-50 text-indigo-700 rounded-xl border border-indigo-200">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
                <span>Student Name (HTR)</span>
                {currentDetail.name_confidence !== undefined && currentDetail.name_confidence > 0 && (
                  <span
                    className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                      currentDetail.name_confidence >= 0.70
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-amber-50 text-amber-700 border-amber-200'
                    }`}
                  >
                    HTR {Math.round(currentDetail.name_confidence * 100)}%
                  </span>
                )}
              </div>
              {editingDetails ? (
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder="Enter Student Name"
                  className="mt-1 px-2.5 py-1 text-sm font-semibold border border-indigo-300 rounded-lg focus:ring-2 focus:ring-indigo-500 bg-white"
                />
              ) : (
                <div className="text-base font-bold text-slate-900">
                  {currentDetail.student_name || 'Unassigned'}
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div>
              <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center justify-end gap-1.5">
                <span>Roll Number</span>
                {currentDetail.roll_confidence !== undefined && currentDetail.roll_confidence > 0 && (
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                    {Math.round(currentDetail.roll_confidence * 100)}%
                  </span>
                )}
              </div>
              {editingDetails ? (
                <input
                  type="text"
                  value={editRoll}
                  onChange={(e) => setEditRoll(e.target.value)}
                  placeholder="Enter Roll No."
                  className="mt-1 px-2.5 py-1 text-sm font-mono font-bold border border-indigo-300 rounded-lg focus:ring-2 focus:ring-indigo-500 bg-white"
                />
              ) : (
                <div className="text-base font-mono font-bold text-indigo-900">
                  {currentDetail.student_roll || currentDetail.detected_roll_number || 'UNASSIGNED'}
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
                  className="px-3 py-1.5 text-xs font-bold text-indigo-700 bg-white hover:bg-indigo-50 border border-indigo-200 rounded-lg shadow-sm flex items-center gap-1"
                >
                  <Edit2 className="w-3.5 h-3.5" />
                  <span>Edit Name/Roll</span>
                </button>
              )}
            </div>
          </div>

          {currentDetail.name_crop_url && (
            <div className="w-full pt-2 border-t border-slate-100 flex flex-wrap items-center gap-3">
              <span className="text-[10px] font-bold text-slate-500 uppercase">Crop Preview:</span>
              <img
                src={currentDetail.name_crop_url}
                alt="Cropped name"
                className="h-8 rounded border border-slate-200 bg-white object-contain px-1"
              />
              {currentDetail.name_confidence !== undefined && currentDetail.name_confidence < 0.70 && (
                <span className="text-xs text-amber-700 font-medium flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                  Please verify or correct student name before finalizing.
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Main Review Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Image Canvas with Zoom & View Mode Switcher (7 cols) */}
        <div className="lg:col-span-7 bg-white rounded-2xl border border-slate-200 shadow-sm p-4 flex flex-col">
          <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-100">
            {/* View Mode Switcher Pills */}
            <div className="flex items-center bg-slate-100 p-0.5 rounded-lg text-xs font-semibold">
              <button
                onClick={() => setViewMode('diagnostic')}
                className={`flex items-center space-x-1 px-2.5 py-1 rounded-md transition-colors ${
                  viewMode === 'diagnostic'
                    ? 'bg-white text-blue-700 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
                title="View detected bubbles and ink densities overlay"
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Diagnostic Overlay</span>
              </button>

              <button
                onClick={() => setViewMode('rectified')}
                className={`flex items-center space-x-1 px-2.5 py-1 rounded-md transition-colors ${
                  viewMode === 'rectified'
                    ? 'bg-white text-blue-700 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
                title="View perspective-corrected sheet"
              >
                <FileCheck2 className="w-3.5 h-3.5" />
                <span>Rectified Sheet</span>
              </button>

              <button
                onClick={() => setViewMode('original')}
                className={`flex items-center space-x-1 px-2.5 py-1 rounded-md transition-colors ${
                  viewMode === 'original'
                    ? 'bg-white text-blue-700 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
                title="View raw uploaded mobile photo"
              >
                <Camera className="w-3.5 h-3.5" />
                <span>Original Photo</span>
              </button>
            </div>

            {/* Zoom Controls */}
            <div className="flex items-center space-x-1">
              <button
                onClick={() => setZoomLevel((z) => Math.max(0.5, z - 0.2))}
                className="p-1.5 rounded-lg border text-slate-600 hover:bg-slate-100"
                title="Zoom Out"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <span className="text-xs font-mono px-2 text-slate-500">
                {Math.round(zoomLevel * 100)}%
              </span>
              <button
                onClick={() => setZoomLevel((z) => Math.min(3.0, z + 0.2))}
                className="p-1.5 rounded-lg border text-slate-600 hover:bg-slate-100"
                title="Zoom In"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                onClick={() => setZoomLevel(1)}
                className="p-1.5 rounded-lg border text-slate-600 hover:bg-slate-100 text-xs font-medium"
              >
                Reset
              </button>
            </div>
          </div>

          {/* Canvas Display */}
          <div className="flex-1 overflow-auto bg-slate-950 rounded-xl min-h-[480px] max-h-[660px] flex items-center justify-center p-3 relative">
            {imageLoading ? (
              <div className="flex flex-col items-center space-y-2 text-slate-400">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent" />
                <p className="text-xs">Loading {viewMode} image...</p>
              </div>
            ) : imageError ? (
              <div className="flex flex-col items-center space-y-2 text-slate-400 text-center p-6">
                <ImageOff className="w-10 h-10 text-slate-500" />
                <p className="text-xs font-semibold text-slate-300">
                  {viewMode === 'diagnostic'
                    ? 'Diagnostic view not generated yet'
                    : viewMode === 'rectified'
                    ? 'Rectified image not available'
                    : 'Original image unavailable'}
                </p>
                <p className="text-[11px] text-slate-500 max-w-xs">
                  {viewMode !== 'original' && (
                    <button
                      onClick={() => setViewMode('original')}
                      className="text-blue-400 hover:underline mt-1 block mx-auto"
                    >
                      Click here to switch to Original Photo
                    </button>
                  )}
                </p>
              </div>
            ) : objectUrl ? (
              <img
                src={objectUrl}
                alt={`${viewMode} view`}
                style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'top center' }}
                className="transition-transform duration-150 max-w-full rounded shadow-2xl"
              />
            ) : null}
          </div>
        </div>

        {/* Right Column: Question Diagnostic & Override Controls (5 cols) */}
        <div className="lg:col-span-5 bg-white rounded-2xl border border-slate-200 shadow-sm p-5 flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-900">Questions in this Sheet</h3>
              <span className="text-xs font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">
                {currentDetail?.review_count || 0} unresolved
              </span>
            </div>

            {/* Questions chips list */}
            <div className="flex flex-wrap gap-1.5 my-3 max-h-28 overflow-y-auto p-1">
              {currentDetail?.responses?.map((r) => (
                <button
                  key={r.question_number}
                  onClick={() => setSelectedQuestion(r.question_number)}
                  className={`px-2 py-1 rounded text-xs font-bold transition-all ${
                    selectedQuestion === r.question_number
                      ? 'bg-blue-600 text-white shadow-sm ring-2 ring-blue-300'
                      : r.detected_option === 'REVIEW' && !r.is_reviewed
                      ? 'bg-amber-100 text-amber-800 border border-amber-300'
                      : r.is_reviewed
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  Q{r.question_number}
                  {r.detected_option === 'REVIEW' && !r.is_reviewed && '!'}
                </button>
              ))}
            </div>

            {/* Active Question Diagnostics Panel */}
            {activeResponse && (
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-extrabold text-slate-900">
                    Question #{activeResponse.question_number}
                  </div>
                  <div className="text-xs">
                    Answer Key: <span className="font-bold text-blue-600">{activeResponse.correct_option || 'N/A'}</span>
                  </div>
                </div>

                <div className="text-xs text-slate-600">
                  Detector Classification:{' '}
                  <span
                    className={`font-bold px-1.5 py-0.5 rounded ${
                      activeResponse.detected_option === 'REVIEW'
                        ? 'bg-amber-100 text-amber-800'
                        : activeResponse.detected_option === 'MULTIPLE'
                        ? 'bg-red-100 text-red-800'
                        : activeResponse.detected_option === 'BLANK'
                        ? 'bg-slate-200 text-slate-700'
                        : 'bg-blue-100 text-blue-800'
                    }`}
                  >
                    {activeResponse.detected_option}
                  </span>
                  <span className="ml-2 text-slate-400">
                    (Confidence: {Math.round(activeResponse.confidence_score * 100)}%)
                  </span>
                </div>

                {/* Bubble Ink Density Bars */}
                <div className="space-y-1.5 pt-1">
                  <div className="text-[11px] font-semibold text-slate-500">
                    Measured Ink Densities (Inner 65% Circle):
                  </div>
                  {[
                    { opt: 'A', val: activeResponse.ink_density_a },
                    { opt: 'B', val: activeResponse.ink_density_b },
                    { opt: 'C', val: activeResponse.ink_density_c },
                    { opt: 'D', val: activeResponse.ink_density_d },
                  ].map(({ opt, val }) => (
                    <div key={opt} className="flex items-center space-x-2 text-xs">
                      <span className="font-bold w-4">{opt}:</span>
                      <div className="flex-1 bg-slate-200 rounded-full h-2 overflow-hidden">
                        <div
                          className={`h-2 rounded-full ${
                            val >= 0.38 ? 'bg-blue-600' : val >= 0.20 ? 'bg-amber-400' : 'bg-slate-300'
                          }`}
                          style={{ width: `${Math.min(100, val * 100)}%` }}
                        ></div>
                      </div>
                      <span className="font-mono text-[11px] text-slate-500 w-10 text-right">
                        {(val * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>

                {/* Teacher Override Selector */}
                <div className="pt-2 border-t border-slate-200">
                  <label className="block text-xs font-bold text-slate-700 mb-1.5">
                    Teacher Verdict Override:
                  </label>
                  <div className="grid grid-cols-6 gap-1 text-center">
                    {(['A', 'B', 'C', 'D', 'BLANK', 'MULTIPLE'] as OptionClassification[]).map((opt) => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => setOverrideOption(opt)}
                        className={`py-1.5 text-xs font-bold rounded-lg transition-colors ${
                          (overrideOption || activeResponse.final_option) === opt
                            ? 'bg-blue-600 text-white shadow-sm'
                            : 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-100'
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">
                    Audit Explanation *
                  </label>
                  <input
                    type="text"
                    required
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                    placeholder="e.g. Verified handwritten smudge; student clearly shaded B"
                    className="w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-600"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Action button */}
          <button
            onClick={handleSaveOverride}
            disabled={saving || !overrideOption || !overrideReason.trim()}
            className="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-md disabled:opacity-40 transition-colors flex items-center justify-center space-x-1.5"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? 'Saving Verdict...' : 'Save Verdict & Recalculate'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
