import { useState, useEffect } from 'react';
import { AbstractCRMProvider } from './AbstractCRMProvider';

export interface HubSpotProviderProps extends CRMProviderProps {
  apiKey: string;
  workspaceId: string;
}

export class HubSpotProvider extends AbstractCRMProvider {
  private readonly workspaceId: string;

  constructor(props: HubSpotProviderProps) {
    super(props);
    this.workspaceId = props.workspaceId;
  }

  async create(data: Record<string, any>): Promise<{ id: string }> {
    const response = await fetch(`https://api.hubapi.com/crm/v3/objects/contacts`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.api.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        properties: data
      })
    });
    
    if (!response.ok) throw new Error('HubSpot create failed');
    
    const result = await response.json();
    return { id: result.object.id };
  }

  async read(id: string): Promise<Record<string, any>> {
    const response = await fetch(`https://api.hubapi.com/crm/v3/objects/contacts/${id}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${this.api.apiKey}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) throw new Error('HubSpot read failed');
    
    return await response.json();
  }

  async update(id: string, data: Record<string, any>): Promise<void> {
    const response = await fetch(`https://api.hubapi.com/crm/v3/objects/contacts/${id}`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${this.api.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        properties: data
      })
    });
    
    if (!response.ok) throw new Error('HubSpot update failed');
  }

  async delete(id: string): Promise<void> {
    const response = await fetch(`https://api.hubapi.com/crm/v3/objects/contacts/${id}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${this.api.apiKey}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) throw new Error('HubSpot delete failed');
  }
}
