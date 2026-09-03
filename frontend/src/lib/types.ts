export type RescueTarget = "renter" | "lister" | null;

export interface Renter {
  id: string;
  name: string;
  phone_demo_id: string | null;
}

export interface Lister {
  id: string;
  name: string;
  phone_demo_id: string | null;
  average_response_minutes: number;
}

export interface Listing {
  id: string;
  lister_id: string;
  name: string;
  market: string;
  monthly_price: number;
  availability_status: string;
}

export interface Booking {
  id: string;
  renter_id: string;
  lister_id: string;
  listing_id: string;
  move_in: string;
  move_out: string;
  booking_value: number;
  status: string;
  rescue_score: number;
  risk_level: string;
  rescue_target: RescueTarget;
  created_at: string;
  last_activity_at: string;
  at_risk_at: string | null;
  rescued_at: string | null;
  completed_at: string | null;
}

export interface ScoreReason {
  code: string;
  label: string;
  points: number;
}

export interface RescueScore {
  score: number;
  raw_score: number;
  risk_level: string;
  target: RescueTarget;
  explanation: string;
  reasons: ScoreReason[];
  recommended_intervention: string | null;
  trigger_code: string | null;
}

export interface MarketplaceEvent {
  id: string;
  booking_id: string;
  event_type: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface RescueAction {
  id: string;
  booking_id: string;
  intervention_type: string;
  target_type: Exclude<RescueTarget, null>;
  target_id: string;
  reason_summary: string;
  message_text: string | null;
  message_source: "openai" | "fallback_template" | null;
  status: string;
  score_at_trigger: number;
  sent_at: string | null;
  response_text: string | null;
  response_at: string | null;
  outcome: string;
}

export interface SimulationSnapshot {
  run_id: string | null;
  seed: number | null;
  status: "idle" | "running" | "completed" | string;
  duration_seconds: number;
  speed_multiplier: number;
  autopilot_enabled: boolean;
  started_at: string | null;
  completed_at: string | null;
  elapsed_seconds: number;
  progress_percent: number;
  total_planned_events: number;
  processed_planned_events: number;
  bookings: Booking[];
  events: MarketplaceEvent[];
  scores: Record<string, RescueScore>;
  rescue_actions: RescueAction[];
  analytics: RescueAnalytics;
}

export interface RescueAnalytics {
  baseline_gmv_rescued: number;
  baseline_bookings_rescued: number;
  run_gmv_rescued: number;
  run_bookings_rescued: number;
  monthly_gmv_rescued: number;
  monthly_bookings_rescued: number;
  rescue_success_rate: number;
  active_rescue_cases: number;
  total_demo_sms_sent: number;
}

export interface ActivityScoreReason {
  code: string;
  label: string;
  points: number;
}

export interface ActivityRecord {
  id: string;
  action_id: string;
  timestamp: string;
  booking_id: string;
  booking_label: string;
  renter_name: string;
  listing_name: string;
  target_type: string;
  target_name: string;
  trigger: string;
  triggering_events: string[];
  score: number;
  score_reasons: ActivityScoreReason[];
  agent_explanation: string;
  intervention: string;
  message_text: string | null;
  message_source: string | null;
  message_status: string;
  sent_at: string | null;
  response_text: string | null;
  response_at: string | null;
  outcome: string;
  resulting_booking_state: string;
  gmv_attributed: number;
}

export interface ActivityResponse {
  analytics: RescueAnalytics;
  records: ActivityRecord[];
}

export interface MarketplaceSeed {
  reference_time: string;
  renters: Renter[];
  listers: Lister[];
  listings: Listing[];
  bookings: Booking[];
  events: MarketplaceEvent[];
  rescue_actions: RescueAction[];
}
