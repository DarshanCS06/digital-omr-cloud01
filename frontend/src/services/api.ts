import {
  User,
  Examination,
  UploadBatch,
  Submission,
  AnswerKey,
  DashboardStats,
  ExamStats,
  OptionClassification,
} from '../types';

const API_BASE = '/api';

class ApiService {
  /** Exposed so components can build authenticated fetch calls directly. */
  readonly baseUrl = API_BASE;

  private getToken(): string | null {
    return localStorage.getItem('omr_access_token');
  }

  /** Returns the current JWT token — used by components to append ?token= to download links. */
  getAuthToken(): string {
    return this.getToken() || '';
  }

  setToken(token: string) {
    localStorage.setItem('omr_access_token', token);
  }

  clearToken() {
    localStorage.removeItem('omr_access_token');
    localStorage.removeItem('omr_user');
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      this.clearToken();
      window.location.href = '/login';
      throw new Error('Session expired. Please log in again.');
    }

    if (!response.ok) {
      let errorMsg = `HTTP Error ${response.status}`;
      try {
        const errJson = await response.json();
        errorMsg = errJson.detail || errorMsg;
      } catch {}
      throw new Error(errorMsg);
    }

    return response.json();
  }

  // Auth
  async login(email: string, password: string): Promise<{ access_token: string; user: User }> {
    const res = await this.request<{ access_token: string; user: User }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    this.setToken(res.access_token);
    localStorage.setItem('omr_user', JSON.stringify(res.user));
    return res;
  }

  async getProfile(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  // Users (Admin)
  async getUsers(): Promise<User[]> {
    return this.request<User[]>('/users');
  }

  async createUser(data: { email: string; full_name: string; password: string; role: string }): Promise<User> {
    return this.request<User>('/users', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateUser(id: number, data: Partial<User & { password?: string }>): Promise<User> {
    return this.request<User>(`/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deactivateUser(id: number): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/users/${id}`, {
      method: 'DELETE',
    });
  }

  // Examinations
  async getExaminations(): Promise<Examination[]> {
    return this.request<Examination[]>('/examinations');
  }

  async createExamination(data: any): Promise<Examination> {
    return this.request<Examination>('/examinations', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getExamination(id: number): Promise<Examination> {
    return this.request<Examination>(`/examinations/${id}`);
  }

  async updateExamination(id: number, data: Partial<Examination>): Promise<Examination> {
    return this.request<Examination>(`/examinations/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async assignTeachers(examId: number, teacherIds: number[]): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/examinations/${examId}/assign`, {
      method: 'POST',
      body: JSON.stringify({ teacher_ids: teacherIds }),
    });
  }

  async getAnswerKey(examId: number): Promise<AnswerKey | null> {
    return this.request<AnswerKey | null>(`/examinations/${examId}/answer-key`);
  }

  async rescoreExam(examId: number, newAnswers: Record<string, string>, reason: string): Promise<any> {
    return this.request(`/examinations/${examId}/rescore`, {
      method: 'POST',
      body: JSON.stringify({ new_answers: newAnswers, reason }),
    });
  }

  async publishExam(examId: number): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/examinations/${examId}/publish`, {
      method: 'POST',
    });
  }

  // Batches
  async uploadBatch(examId: number, files: File[]): Promise<{ batch_id: number; message: string }> {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));

    return this.request<{ batch_id: number; message: string }>(`/batches/upload/${examId}`, {
      method: 'POST',
      body: formData,
    });
  }

  async validateSheetPreview(examId: number, file: File): Promise<{
    filename: string;
    is_pdf?: boolean;
    page_count?: number;
    file_size_bytes?: number;
    exam_title?: string;
    exam_code?: string;
    question_count?: number;
    answer_key_count?: number;
    is_valid: boolean;
    validation_message: string;
    quality: Record<string, any>;
    alignment: Record<string, any>;
    original_preview_url: string;
    corrected_preview_url: string;
  }> {
    const formData = new FormData();
    formData.append('file', file);
    return this.request(`/batches/validate-preview/${examId}`, {
      method: 'POST',
      body: formData,
    });
  }

  async getBatchStatus(batchId: number): Promise<UploadBatch> {
    return this.request<UploadBatch>(`/batches/${batchId}`);
  }

  async getLatestExamBatch(examId: number): Promise<UploadBatch | null> {
    return this.request<UploadBatch | null>(`/batches/exam/${examId}/latest`);
  }

  async cancelBatch(batchId: number): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/batches/${batchId}/cancel`, {
      method: 'POST',
    });
  }

  async retryBatch(batchId: number): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/batches/${batchId}/retry`, {
      method: 'POST',
    });
  }

  // Submissions
  async getSubmissions(examId: number, status?: string, search?: string): Promise<Submission[]> {
    let url = `/submissions/exam/${examId}?limit=100`;
    if (status) url += `&status_filter=${status}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    return this.request<Submission[]>(url);
  }

  async getSubmissionDetail(id: number): Promise<Submission> {
    return this.request<Submission>(`/submissions/${id}`);
  }

  async finalizeSubmission(id: number): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/submissions/${id}/finalize`, {
      method: 'POST',
    });
  }

  getOriginalImageUrl(submissionId: number): string {
    const token = this.getToken();
    return `${API_BASE}/submissions/${submissionId}/images/original?token=${token}`;
  }

  getRectifiedImageUrl(submissionId: number): string {
    const token = this.getToken();
    return `${API_BASE}/submissions/${submissionId}/images/rectified?token=${token}`;
  }

  getDiagnosticImageUrl(submissionId: number): string {
    const token = this.getToken();
    return `${API_BASE}/submissions/${submissionId}/images/diagnostic?token=${token}`;
  }

  // Reviews
  async getReviewQueue(examId: number): Promise<Submission[]> {
    return this.request<Submission[]>(`/reviews/exam/${examId}`);
  }

  async overrideResponse(
    submissionId: number,
    questionNumber: number,
    selectedOption: OptionClassification,
    reason: string
  ): Promise<any> {
    return this.request(`/reviews/override/${submissionId}`, {
      method: 'POST',
      body: JSON.stringify({
        question_number: questionNumber,
        selected_option: selectedOption,
        reason,
      }),
    });
  }

  // Exports
  getExportCsvUrl(examId: number): string {
    return `${API_BASE}/reports/csv/${examId}`;
  }

  getExportExcelUrl(examId: number): string {
    return `${API_BASE}/reports/excel/${examId}`;
  }

  getExportPdfUrl(examId: number, batchId?: number): string {
    return batchId
      ? `${API_BASE}/reports/pdf/${examId}?batch_id=${batchId}`
      : `${API_BASE}/reports/pdf/${examId}`;
  }

  getOMRPdfUrl(examId: number): string {
    return `${API_BASE}/templates/omr-pdf/${examId}`;
  }

  async evaluateSampleSheet(examId: number, markStyle: string = 'solid'): Promise<any> {
    return this.request(`/templates/evaluate-sample/${examId}?mark_style=${encodeURIComponent(markStyle)}`, {
      method: 'POST',
    });
  }

  // Dashboard
  async getDashboardStats(): Promise<DashboardStats> {
    return this.request<DashboardStats>('/dashboard/stats');
  }

  async getExamStats(examId: number): Promise<ExamStats> {
    return this.request<ExamStats>(`/dashboard/exam-stats/${examId}`);
  }

  async clearHistory(scope: 'audit' | 'all' | 'everything' = 'all'): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/dashboard/clear-history?scope=${scope}`, {
      method: 'DELETE',
    });
  }

  async clearExamSubmissions(examId: number): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/submissions/exam/${examId}/clear`, {
      method: 'DELETE',
    });
  }

  async deleteSubmission(subId: number): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/submissions/${subId}`, {
      method: 'DELETE',
    });
  }

  async deleteExamination(examId: number): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/examinations/${examId}`, {
      method: 'DELETE',
    });
  }
}

export const api = new ApiService();
