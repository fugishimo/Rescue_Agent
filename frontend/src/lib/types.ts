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
