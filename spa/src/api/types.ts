// Typed shapes for the acct (U1) API. Kept hand-written and small; mirrors the
// FastAPI responses in src/api/acct_routes.py.

export type ApplicationStatus =
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "CHANGES_REQUESTED"
  | "REJECTED";

export type AccountStatus =
  | "DRAFT"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "CHANGES_REQUESTED"
  | "REJECTED"
  | "SUSPENDED";

export interface Capabilities {
  is_admin: boolean;
  is_distributor: boolean;
  submit_application: boolean;
  view_own_account: boolean;
  review_applications: boolean;
  configure: boolean;
  create_quote: boolean;
  account_status: AccountStatus | null;
}

export interface MyAccount {
  DistributorAccountId: number;
  CompanyName: string;
  Status: AccountStatus;
  LoyaltyTierCode: string | null;
  CreatedAt: string;
  ApplicationId: number | null;
  ApplicationStatus: ApplicationStatus | null;
  ReviewOutcome: string | null;
  ReviewReason: string | null;
  ReviewedAt: string | null;
}

export interface Me {
  user: {
    app_user_id: number;
    email: string | null;
    display_name: string | null;
    roles: string[];
  };
  capabilities: Capabilities;
  account: MyAccount | null;
}

export interface AddressInput {
  first_name?: string;
  last_name?: string;
  address1: string;
  address2?: string;
  city: string;
  state?: string;
  postal_code: string;
  country: string;
  phone?: string;
}

export interface SubmitApplicationInput {
  idempotency_key: string;
  company_name: string;
  contact: AddressInput;
  ship_to: AddressInput;
}

export interface SubmitApplicationResult {
  application_id: number;
  distributor_account_id: number;
  status: ApplicationStatus;
  was_duplicate: boolean;
}

export interface ApplicationListItem {
  ApplicationId: number;
  DistributorAccountId: number;
  CompanyName: string;
  Status: ApplicationStatus;
  SubmittedAt: string;
  SubmittedByEmail: string | null;
  ReviewOutcome: string | null;
  ReviewReason: string | null;
  AssignedLoyaltyTier: string | null;
  ReviewedAt: string | null;
  LoyaltyTierCode: string | null;
}

export interface ApplicationAddress {
  AddressId: number;
  Kind: "CONTACT" | "SHIP_TO";
  FirstName: string | null;
  LastName: string | null;
  Address1: string | null;
  Address2: string | null;
  City: string | null;
  State: string | null;
  PostalCode: string | null;
  Country: string | null;
  Phone: string | null;
}

export interface ApplicationDetail {
  application: ApplicationListItem & { SubmittedByAppUserId: number };
  addresses: ApplicationAddress[];
}

export interface ReviewInput {
  outcome: "APPROVED" | "CHANGES_REQUESTED" | "REJECTED";
  reason?: string;
  loyalty_tier_code?: string;
}

export interface Notification {
  NotificationId: number;
  EventType: string;
  ResourceType: string | null;
  ResourceId: string | null;
  Message: string;
  CreatedAt: string;
  ReadAt: string | null;
  RecipientAppUserId: number | null;
  RecipientRole: string | null;
}

// ---------------------------------------------------------------------------
// U2 — Configurator / resolve / quotes / loyalty pricing
// ---------------------------------------------------------------------------

export type FamilyCode = "DEAN" | "FYBROC";

export interface FieldGroupField {
  field: string;
  placeholder?: boolean;
}

export interface FieldGroup {
  group: string;
  fields: FieldGroupField[];
}

export interface ConfigConflict {
  field: string;
  value: string;
  conflicts_with: string[];
  recommended: string[];
}

export interface ResolveStateResponse {
  family: string;
  series: string;
  valid: boolean;
  selections: Record<string, string>;
  allowable_options: Record<string, string[]>;
  standard_defaults: Record<string, string>;
  reset_fields: Record<string, string>;
  dropped_fields: string[];
  conflicts: ConfigConflict[];
  ordered_fields: string[];
  field_groups: FieldGroup[];
  resolved_codes: Record<string, string | null>;
  errors: string[];
}

export interface ComponentPrice {
  component: string;
  selection: string | null;
  amount: number | null;
  status: "found" | "C/F";
  detail?: unknown;
}

export interface ResolveResponse {
  family: string;
  part_number: string;
  sku: string;
  configuration_signature: string;
  existing_configuration: boolean;
  configured_product_id: number | null;
  pricing: { component: string; amount: number; detail?: string }[];
  component_pricing: ComponentPrice[];
  total_price: number;
  motor_cpq_conversion?: string | null;
}

export interface SkuLookupResponse {
  found: boolean;
  sku: string;
  family: string | null;
  series: string | null;
  part_number: string | null;
  configuration_signature: string | null;
  configured_product_id: number | null;
  created_at: string | null;
  selections: Record<string, string>;
  field_groups: FieldGroup[];
  errors: string[];
}

export interface QuoteListItem {
  quote_header_id: number;
  quote_number: string;
  customer_name: string | null;
  customer_account: string | null;
  site_code: string;
  currency_code: string;
  status: string;
  created_at: string | null;
  created_by: string | null;
  line_count: number;
  total_price: number;
}

export interface QuoteLine {
  quote_line_id: number;
  line_number: number;
  part_number: string;
  sku: string;
  family: string;
  quantity: number;
  unit_price: number;
  extended_price: number;
  pricing_status: "found" | "partial" | "call_for_price";
  bom_signature: string;
  publication_version: string;
}

export interface QuoteDocument {
  quote_number: string;
  customer_name: string | null;
  customer_account: string | null;
  site_code: string;
  currency: string;
  status: string;
  lines: QuoteLine[];
  total_price: number;
  line_count: number;
  rendered_text: string;
}

export interface CreateQuoteInput {
  site_code: string;
  customer_name?: string;
  customer_account?: string;
  currency_code?: string;
  created_by?: string;
  quote_number?: string;
}

export interface AddQuoteLineInput {
  series: string;
  selections: Record<string, string>;
  segment_codes?: Record<string, string>;
  quantity?: number;
  requested_by?: string;
}

export interface QuotePricing {
  quote_header_id: number;
  currency: string;
  loyalty_tier_code: string | null;
  discount_rate_bp: number;
  list_total: number;
  merchandise_subtotal: number;
  discount_amount: number;
  net_total: number;
  unpriced_line_count: number;
  unpriced_line_total: number;
  line_count: number;
}

// ---------------------------------------------------------------------------
// U3 — Engineering review queue
// ---------------------------------------------------------------------------

export type ReviewStatus =
  | "PENDING_REVIEW"
  | "CLAIMED"
  | "CHANGES_REQUESTED"
  | "COMPLETED"
  | "CANCELLED"
  | "ROUTING_EXCEPTION";

export interface SubmitForReviewResult {
  review_case_id: number;
  quote_header_id: number;
  brand: string;
  responsible_site_code: string;
  status: ReviewStatus;
  routing_exception: boolean;
  was_existing: boolean;
}

export interface ReviewCaseListItem {
  ReviewCaseId: number;
  QuoteHeaderId: number;
  Brand: string;
  ResponsibleSiteCode: string;
  Status: ReviewStatus;
  RoutingException: boolean;
  SubmittedAt: string;
  AssignedToAppUserId: number | null;
  LeadTimeDays: number | null;
  RevisionNo: number;
  QuoteNumber: string | null;
  CustomerName: string | null;
  AssignedToEmail: string | null;
}

export interface ReviewCaseLine {
  ReviewCaseLineId: number;
  QuoteLineId: number;
  LineNumber: number;
  PartNumber: string | null;
  PricingStatus: string | null;
  ResolvedUnitPrice: number | null;
  CustomSpec: string | null;
  EngineerNote: string | null;
  ResolvedAt: string | null;
}

export interface ReviewCaseDetail {
  case: {
    ReviewCaseId: number;
    QuoteHeaderId: number;
    Brand: string;
    ResponsibleSiteCode: string;
    Status: ReviewStatus;
    RoutingException: boolean;
    SubmittedAt: string;
    AssignedToAppUserId: number | null;
    ClaimedAt: string | null;
    CompletedAt: string | null;
    RevisionNo: number;
    LeadTimeDays: number | null;
    ReviewNotes: string | null;
    QuoteNumber: string | null;
    CustomerName: string | null;
  };
  lines: ReviewCaseLine[];
}

export interface ResolveReviewLineInput {
  resolved_unit_price?: number | null;
  custom_spec?: string;
  engineer_note?: string;
}

export interface CompleteReviewInput {
  lead_time_days?: number | null;
  notes?: string;
}
