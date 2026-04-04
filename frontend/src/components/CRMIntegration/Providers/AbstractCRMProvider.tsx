import { useState, useEffect } from 'react';

export interface CRMProviderProps {
  apiKey: string;
  endpoint: string;
  onDataSync?: () => void;
}

export abstract class AbstractCRMProvider {
  protected readonly api: {
    endpoint: string;
    auth: {
      apiKey: string;
      token?: string;
    };
  };

  protected constructor(props: CRMProviderProps) {
    this.api = {
      endpoint: props.endpoint,
      auth: {
        apiKey: props.apiKey,
        token: props.endpoint.includes('hubspot') ? undefined : props.apiKey
      }
    };
  }

  abstract create(data: Record<string, any>): Promise<{ id: string }>;
  abstract read(id: string): Promise<Record<string, any>>;
  abstract update(id: string, data: Record<string, any>): Promise<void>;
  abstract delete(id: string): Promise<void>;
}
