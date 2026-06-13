export type CalendarEvent = {
  id: string;
  patient_label: string;
  title: string;
  start: string;
  end: string;
  duration_minutes: number;
  status: string;
};

export type PreferredTimeWindow = {
  date: string | null;
  start_time: string | null;
  end_time: string | null;
};

export type AppointmentIntent = {
  visit_reason: string;
  procedure_hint: string | null;
  preferred_time: string | null;
  preferred_days: string[];
  preferred_time_windows: PreferredTimeWindow[];
  excluded_days: string[];
  specific_datetime: string | null;
  urgency: string;
  duration_minutes: number;
  confidence: number;
  requires_human_callback: boolean;
  explanation: string;
};

export type AppointmentResponse = {
  status: "scheduled" | "needs_callback" | "failed";
  transcript: string;
  intent: AppointmentIntent;
  event: CalendarEvent | null;
  sms_text: string;
  scheduling_explanation: string;
};
