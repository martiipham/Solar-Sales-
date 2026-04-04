import React, { useState } from 'react';
import { useRouter } from 'next/router';

const CRMWizard = () => {
  const router = useRouter();
  const [crmProvider, setCrmProvider] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [mappedFields, setMappedFields] = useState({});
  const [testResults, setTestResults] = useState(null);

  const handleNextStep = () => {
    switch (router.query.step) {
      case '2':
        // Step 2: Enter API credentials
        return <div>Enter API Credentials</div>;
      case '3':
        // Step 3: Map fields
        return <div>Map Fields</div>;
      case '4':
        // Step 4: Test connection
        setTestResults('Connection Test Results');
        router.push('/CRMWizard?step=5');
        return null;
      default:
        // Step 1: Select CRM provider
        return (
          <div>
            <input
              type="text"
              value={crmProvider}
              onChange={(e) => setCrmProvider(e.target.value)}
              placeholder="Select CRM Provider"
            />
            <button onClick={() => router.push('/CRMWizard?step=2')}>Next</button>
          </div>
        );
    }
  };

  return (
    <div className="container mx-auto p-4">
      {handleNextStep()}
      {testResults && <div>Tes
