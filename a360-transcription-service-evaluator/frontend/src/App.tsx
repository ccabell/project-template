/**
 * Main App component for transcription evaluator frontend.
 */

import React from 'react';
import { Toaster } from 'react-hot-toast';
import { RoleBasedRouter } from './components/RoleBasedRouter';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import ProtectedRoute from './components/auth/ProtectedRoute';
import './aws-config';
import './App.css';

const AppContent: React.FC = () => {
  const { signOut } = useAuth();

  return <RoleBasedRouter onSignOut={signOut} />;
};

function App() {
  return (
    <AuthProvider>
      <ProtectedRoute>
        <AppContent />
      </ProtectedRoute>
      <Toaster position="top-right" />
    </AuthProvider>
  );
}

export default App;