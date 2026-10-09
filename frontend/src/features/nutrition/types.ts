import { type AIError } from "@/lib/types";
// --- Nutrition. A null nutrient means "not available"; it is never shown or summed as zero. ---
export const NUTRIENT_KEYS = [
  "energy_kcal",
  "protein_g",
  "sodium_mg",
  "potassium_mg",
  "phosphorus_mg",
  "calcium_mg",
  "fluid_ml",
] as const;

export type NutrientKey = (typeof NUTRIENT_KEYS)[number];

export type Nutrients = Record<NutrientKey, number | null>;

export interface Food {
  id: string;
  canonical_name: string;
  localized_names: Record<string, string>;
  portion_grams: Record<string, number>;
  allergens: string[];
}

interface Recipe {
  id: string;
  name: string;
  localized_names: Record<string, string>;
  meal_type: string;
  preparation_method: string[];
  allergens: string[];
}

export interface MealPart {
  id?: string;
  food_item: string | null;
  food_name?: string | null;
  name: string;
  quantity: string | number;
  unit: string;
  estimated_grams?: string | null;
  portion_verified: boolean;
}

export interface Meal {
  id: string;
  patient: string;
  meal_type: string;
  consumed_at: string;
  entry_method: string;
  confirmation_status: "confirmed" | "needs_review";
  components: MealPart[];
  estimate: Nutrients | null;
  created_by_name: string;
  description?: string;
}

export interface DiarySummary {
  days_in_period: number;
  days_recorded: number;
  missing_days: string[];
  meals_recorded: number;
  daily_average_on_complete_days: Nutrients;
  days_with_complete_data: Record<NutrientKey, number>;
  most_recorded_foods: string[];
}

export interface NutritionPlan {
  id: string;
  version: number;
  prescribed_targets: Record<string, number>;
  guidance: string;
  dietary_preferences: string[];
  allergies: string[];
  approved_by_name: string;
  approved_at: string;
  active: boolean;
}

export interface NutritionOverview {
  photo_recognition_available?: boolean;
  patient: string;
  patient_name: string;
  today: DiarySummary;
  last_7_days: DiarySummary;
  active_plan: NutritionPlan | null;
  can_log: boolean;
}

export interface NutritionRow {
  patient: string;
  patient_name: string;
  has_active_plan: boolean;
  days_recorded_last_7: number;
  pending_recommendations?: number;
  pending_lab_reviews?: number;
  draft_reports?: number;
  referrals?: number;
}

export interface Recommendation {
  id: string;
  recipe: Recipe;
  category: string;
  personalized: boolean;
  /** Ordered by the latest laboratory report: only a doctor may approve it. */
  lab_based: boolean;
  reasoning_summary: string;
  nutrient_estimates: Nutrients;
  limitations: string[];
  review_status: string;
  reviewed_by_name: string | null;
}

export interface LabFact {
  id: string;
  report_id: string;
  analyte: string;
  value: number;
  unit: string;
  reference_low: number | null;
  reference_high: number | null;
  collected_at: string;
}

export interface FoodLabReview {
  id: string;
  date_from: string;
  date_to: string;
  possible_associations: { text: string; nutrient: string; lab_result_ids: string[] }[];
  limitations: string[];
  questions: string[];
  ai_error: AIError[];
  review_status: string;
  reviewed_by_name: string | null;
  review_notes: string;
}

export interface LabTrendsData {
  diary: DiarySummary;
  laboratory_results: LabFact[];
  reviews: FoodLabReview[];
}

export interface NutritionReport {
  id: string;
  patient_name: string;
  period_start: string;
  period_end: string;
  version: number;
  meal_summary: Omit<DiarySummary, "daily_average_on_complete_days">;
  nutrient_summary: { daily_average_on_complete_days: Nutrients };
  laboratory_summary: LabFact[];
  dialysis_summary: {
    id: string;
    date: string;
    status: string;
    duration_minutes: number | null;
    uf_volume_ml: number | null;
  }[];
  ai_draft: {
    overview: string;
    observations: string[];
    questions_for_care_team: string[];
    limitations: string[];
  } | null;
  ai_error: AIError[];
  clinician_review: string;
  reviewed_by_name: string | null;
  release_status: "draft" | "released";
  released_at: string | null;
}

export interface NutritionObservation {
  id: string;
  author_name: string;
  kind: string;
  text: string;
  referred: boolean;
  created_at: string;
}

interface RecognizedItem {
  name: string;
  quantity: number;
  unit: string;
  confidence: number;
  food_item: string | null;
}

export interface Recognition {
  ai_unavailable: boolean;
  items: RecognizedItem[];
  uncertainties: string[];
}
