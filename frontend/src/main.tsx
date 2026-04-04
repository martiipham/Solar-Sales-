import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { initTokenLifecycle, setAuthFailureHandler } from './lib/api-client';

setAuthFailureHandler(() => {
  window.location.href = '/login';
});

initTokenLifecycle();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
