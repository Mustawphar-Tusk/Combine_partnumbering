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
