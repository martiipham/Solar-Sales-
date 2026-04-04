/**
 * CRM utility — all operations proxy through the backend API.
 *
 * API keys are NEVER embedded in frontend code. The backend's
 * crm_router handles authentication with Salesforce, HubSpot, and GHL.
 */

interface CRMContact {
  id?: string;
  name: string;
  email: string;
  phone?: string;
  company?: string;
}

/**
 * Get the JWT token from local storage for authenticated API calls.
 */
function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('token');
  if (!token) {
    throw new Error('Not authenticated — please log in');
  }
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
  };
}

/**
 * CRM Integration — all calls routed through backend /api/crm/*
 */
export class CRM {
  static async createContact(contact: CRMContact): Promise<CRMContact> {
    const response = await fetch('/api/crm/contacts', {
      method: 'POST',
      headers: getAuthHeader(),
      body: JSON.stringify(contact),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || `CRM API error ${response.status}`);
    }

    return await response.json();
  }

  static async getContact(contactId: string): Promise<CRMContact> {
    const response = await fetch(`/api/crm/contacts/${contactId}`, {
      method: 'GET',
      headers: getAuthHeader(),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || `CRM API error ${response.status}`);
    }

    return await response.json();
  }

  static async status(): Promise<{ active: string; ghl: boolean; hubspot: boolean; salesforce: boolean }> {
    const response = await fetch('/api/crm/status', {
      method: 'GET',
      headers: getAuthHeader(),
    });

    if (!response.ok) {
      throw new Error(`CRM status check failed: ${response.status}`);
    }

    return await response.json();
  }
}
