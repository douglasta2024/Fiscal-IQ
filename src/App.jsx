import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import Dashboard from './pages/Dashboard';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ProfilePage from './pages/ProfilePage';
import SettingsPage from './pages/SettingsPage';
import TemplatesPage from './pages/TemplatesPage';
import LearnMorePage from './pages/LearnMorePage';
import ContactUsPage from './pages/ContactUsPage';
import ProtectedRoute from './components/ProtectedRoute';
import NavigationMenu from './components/NavigationMenu';
import './pages/HomePage.css';

function App() {
  return (
    <Router>
      <NavigationMenu />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/learn-more" element={<LearnMorePage />} />
        <Route path="/contact-us" element={<ContactUsPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <SettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/templates"
          element={
            <ProtectedRoute>
              <TemplatesPage />
            </ProtectedRoute>
          }
        />
      </Routes>
    </Router>
  );
}

export default App;