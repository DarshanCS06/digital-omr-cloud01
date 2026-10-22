export type UserRole = 'ADMIN' | 'TEACHER';

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
}

export interface Examination {
  id: number;
  code: string;
  title: string;
  subject: string;
  class_grade: string;
  exam_date: string;
  question_count: number;
  options_per_question: number;
  positive_marks: number;
  negative_marks: number;
  blank_marks: number;
  multiple_penalty: number;
  allow_teacher_override: boolean;
  is_published: boolean;
  created_by_id: number;
  created_at: string;
  updated_at: string;
  submissions_count?: number;
  pending_review_count?: number;
}

export type BatchStatus = 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'PARTIALLY_FAILED' | 'FAILED' | 'CANCELLED';
export type ImageStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'DUPLICATE';

export interface UploadedImage {
  id: number;
  batch_id: number;
  examination_id: number;
  original_filename: string;
  file_size_bytes: number;
  status: ImageStatus;
  error_message?: string;
  created_at: string;
  submission_id?: number;
  student_name?: string;
  student_roll?: string;
  total_score?: number;
  max_score?: number;
  percentage?: number;
  correct_count?: number;
  incorrect_count?: number;
  blank_count?: number;
  submission_status?: string;
  is_duplicate?: boolean;
}

export interface UploadBatch {
  id: number;
  examination_id: number;
  user_id: number;
  status: BatchStatus;
  total_files: number;
  processed_files: number;
  failed_files: number;
  review_needed_files: number;
  duplicate_count?: number;
  current_page?: number;
  status_message?: string;
  progress_percentage: number;
  error_summary?: string;
  created_at: string;
  completed_at?: string;
  images?: UploadedImage[];
}

export type SubmissionStatus = 'PROVISIONAL' | 'NEEDS_REVIEW' | 'FINALIZED';
export type OptionClassification = 'A' | 'B' | 'C' | 'D' | 'BLANK' | 'MULTIPLE' | 'REVIEW';

export interface DetectedResponse {
  id: number;
  question_number: number;
  detected_option: OptionClassification;
  final_option: string;
  confidence_score: number;
  ink_density_a: number;
  ink_density_b: number;
  ink_density_c: number;
  ink_density_d: number;
  is_reviewed: boolean;
  reviewed_option?: OptionClassification;
  reviewed_by_id?: number;
  review_timestamp?: string;
  review_reason?: string;
  correct_option?: string;
}

export interface Submission {
  id: number;
  examination_id: number;
  student_id?: number;
  student_name?: string;
  student_roll?: string;
  detected_roll_number?: string;
  sheet_identifier?: string;
  status: SubmissionStatus;
  total_score: number;
  max_score: number;
  percentage: number;
  correct_count: number;
  incorrect_count: number;
  blank_count: number;
  multiple_count: number;
  review_count: number;
  is_duplicate: boolean;
  submitted_at: string;
  finalized_at?: string;
  responses?: DetectedResponse[];
  has_original_image?: boolean;
  has_rectified_image?: boolean;
  has_diagnostic_image?: boolean;
}

export interface AnswerKey {
  id: number;
  examination_id: number;
  version: number;
  answers: Record<string, string>;
  is_active: boolean;
  rescore_reason?: string;
}

export interface DashboardStats {
  total_examinations: number;
  total_students_evaluated: number;
  pending_batches: number;
  failed_images: number;
  sheets_awaiting_review: number;
  published_results: number;
  recent_activity: Array<{
    id: number;
    action: string;
    resource_type: string;
    resource_id?: string;
    timestamp: string;
  }>;
}

export interface ExamStats {
  examination_id: number;
  code: string;
  title: string;
  total_submissions: number;
  finalized_submissions: number;
  pending_review: number;
  average_score: number;
  highest_score: number;
  lowest_score: number;
  average_percentage: number;
  pass_percentage: number;
  score_distribution: Record<string, number>;
}
