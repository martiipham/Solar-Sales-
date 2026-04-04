export interface EmailTemplate {
  id: string;
  subject: string;
  body: string;
  createdAt: Date;
}

export interface CRMIntegrationSettings {
  enabled: boolean;
  apiKey: string;
}

export interface Proposal {
  id: string;
  title: string;
  description: string;
  clientId: string;
  createdAt: Date;
}
