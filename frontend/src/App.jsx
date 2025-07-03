import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { Users, UserPlus, Shield, Settings, Activity, Database } from 'lucide-react';
import UserList from './components/UserList';
import GroupList from './components/GroupList';
import SAMLConfig from './components/SAMLConfig';
import './App.css';

const Navigation = () => {
  const location = useLocation();
  
  const isActive = (path) => location.pathname === path;
  
  return (
    <nav className="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <Database className="logo-icon" />
          <span className="logo-text">SCIM Demo</span>
        </div>
        <div className="subtitle">Datadog Provisioning</div>
      </div>
      
      <div className="nav-section">
        <div className="nav-section-title">Management</div>
        <Link 
          to="/users" 
          className={`nav-item ${isActive('/users') || isActive('/') ? 'active' : ''}`}
        >
          <Users className="nav-icon" />
          <span>Users</span>
        </Link>
        <Link 
          to="/groups" 
          className={`nav-item ${isActive('/groups') ? 'active' : ''}`}
        >
          <UserPlus className="nav-icon" />
          <span>Groups</span>
        </Link>
      </div>
      
      <div className="nav-section">
        <div className="nav-section-title">Configuration</div>
        <Link 
          to="/saml" 
          className={`nav-item ${isActive('/saml') ? 'active' : ''}`}
        >
          <Shield className="nav-icon" />
          <span>SAML Config</span>
        </Link>
      </div>
      
      <div className="nav-section">
        <div className="nav-section-title">System</div>
        <div className="nav-item disabled">
          <Settings className="nav-icon" />
          <span>Settings</span>
        </div>
        <div className="nav-item disabled">
          <Activity className="nav-icon" />
          <span>Activity</span>
        </div>
      </div>
    </nav>
  );
};

const Header = () => {
  return (
    <header className="header">
      <div className="header-content">
        <div className="header-left">
          <h1 className="header-title">Identity Provider Demo</h1>
          <p className="header-subtitle">Manage users and groups with Datadog SCIM integration</p>
        </div>
        <div className="header-right">
          <div className="status-indicator">
            <div className="status-dot"></div>
            <span>Connected to Datadog</span>
          </div>
        </div>
      </div>
    </header>
  );
};

function App() {
  return (
    <Router>
      <div className="app">
        <Navigation />
        <div className="main-content">
          <Header />
          <div className="content-area">
            <Routes>
              <Route path="/" element={<UserList />} />
              <Route path="/users" element={<UserList />} />
              <Route path="/groups" element={<GroupList />} />
              <Route path="/saml" element={<SAMLConfig />} />
            </Routes>
          </div>
        </div>
        <Toaster 
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: '#ffffff',
              color: '#111827',
              border: '1px solid #e5e7eb',
              boxShadow: '0 10px 25px rgba(0, 0, 0, 0.1)',
            },
            success: {
              style: {
                background: '#f0fdf4',
                color: '#166534',
                border: '1px solid #bbf7d0',
              },
              iconTheme: {
                primary: '#16a34a',
                secondary: '#ffffff',
              },
            },
            error: {
              style: {
                background: '#fef2f2',
                color: '#991b1b',
                border: '1px solid #fecaca',
              },
              iconTheme: {
                primary: '#dc2626',
                secondary: '#ffffff',
              },
            },
          }}
        />
      </div>
    </Router>
  );
}

export default App; 