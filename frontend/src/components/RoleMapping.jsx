import React, { useState, useEffect } from 'react';
import './RoleMapping.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const RoleMapping = () => {
  const [roles, setRoles] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showBulkForm, setShowBulkForm] = useState(false);
  const [showUserAssignment, setShowUserAssignment] = useState(false);
  const [selectedRole, setSelectedRole] = useState(null);
  const [selectedUser, setSelectedUser] = useState(null);

  // Form states
  const [newRole, setNewRole] = useState({
    name: '',
    description: '',
    idp_role_value: '',
    active: true,
    is_default: false
  });

  const [bulkMappings, setBulkMappings] = useState([
    { idp_role_value: '', role_name: '', description: '', active: true }
  ]);

  useEffect(() => {
    fetchRoles();
    fetchUsers();
  }, []);

  const fetchRoles = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/roles`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch roles');
      }
      
      const data = await response.json();
      setRoles(data);
    } catch (error) {
      setError('Failed to load roles: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchUsers = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/users`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch users');
      }
      
      const data = await response.json();
      setUsers(data);
    } catch (error) {
      setError('Failed to load users: ' + error.message);
    }
  };

  const handleCreateRole = async (e) => {
    e.preventDefault();
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/roles`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newRole)
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create role');
      }
      
      const createdRole = await response.json();
      setRoles([...roles, createdRole]);
      setNewRole({
        name: '',
        description: '',
        idp_role_value: '',
        active: true,
        is_default: false
      });
      setShowCreateForm(false);
      setSuccess('Role created successfully!');
      
      setTimeout(() => setSuccess(''), 3000);
    } catch (error) {
      setError('Failed to create role: ' + error.message);
      setTimeout(() => setError(''), 5000);
    }
  };

  const handleBulkMappings = async (e) => {
    e.preventDefault();
    
    try {
      const validMappings = bulkMappings.filter(mapping => 
        mapping.idp_role_value.trim() && mapping.role_name.trim()
      );
      
      if (validMappings.length === 0) {
        throw new Error('Please provide at least one valid mapping');
      }
      
      const response = await fetch(`${API_BASE_URL}/api/roles/mappings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(validMappings)
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create mappings');
      }
      
      const result = await response.json();
      
      // Refresh roles list
      await fetchRoles();
      
      setBulkMappings([
        { idp_role_value: '', role_name: '', description: '', active: true }
      ]);
      setShowBulkForm(false);
      
      setSuccess(`Bulk mappings completed: ${result.created.length} created, ${result.updated.length} updated`);
      
      if (result.errors.length > 0) {
        setError(`Some mappings failed: ${result.errors.map(e => e.error).join(', ')}`);
      }
      
      setTimeout(() => {
        setSuccess('');
        setError('');
      }, 5000);
    } catch (error) {
      setError('Failed to create bulk mappings: ' + error.message);
      setTimeout(() => setError(''), 5000);
    }
  };

  const handleDeleteRole = async (roleId) => {
    if (!window.confirm('Are you sure you want to delete this role?')) {
      return;
    }
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/roles/${roleId}`, {
        method: 'DELETE'
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to delete role');
      }
      
      setRoles(roles.filter(role => role.id !== roleId));
      setSuccess('Role deleted successfully!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (error) {
      setError('Failed to delete role: ' + error.message);
      setTimeout(() => setError(''), 5000);
    }
  };

  const handleToggleRole = async (roleId, currentActive) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/roles/${roleId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ active: !currentActive })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to update role');
      }
      
      const updatedRole = await response.json();
      setRoles(roles.map(role => 
        role.id === roleId ? updatedRole : role
      ));
      
      setSuccess(`Role ${!currentActive ? 'activated' : 'deactivated'} successfully!`);
      setTimeout(() => setSuccess(''), 3000);
    } catch (error) {
      setError('Failed to update role: ' + error.message);
      setTimeout(() => setError(''), 5000);
    }
  };

  const addBulkMappingRow = () => {
    setBulkMappings([...bulkMappings, { idp_role_value: '', role_name: '', description: '', active: true }]);
  };

  const removeBulkMappingRow = (index) => {
    setBulkMappings(bulkMappings.filter((_, i) => i !== index));
  };

  const updateBulkMapping = (index, field, value) => {
    const updated = [...bulkMappings];
    updated[index][field] = value;
    setBulkMappings(updated);
  };

  const assignRoleToUser = async (roleId, userId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/roles/${roleId}/users/${userId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to assign role');
      }
      
      const result = await response.json();
      setSuccess(result.message);
      
      // Refresh roles to update user counts
      await fetchRoles();
      await fetchUsers();
      
      setTimeout(() => setSuccess(''), 3000);
    } catch (error) {
      setError('Failed to assign role: ' + error.message);
      setTimeout(() => setError(''), 5000);
    }
  };

  const removeRoleFromUser = async (roleId, userId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/roles/${roleId}/users/${userId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to remove role');
      }
      
      const result = await response.json();
      setSuccess(result.message);
      
      // Refresh roles to update user counts
      await fetchRoles();
      await fetchUsers();
      
      setTimeout(() => setSuccess(''), 3000);
    } catch (error) {
      setError('Failed to remove role: ' + error.message);
      setTimeout(() => setError(''), 5000);
    }
  };

  const handleShowUserAssignment = (role) => {
    setSelectedRole(role);
    setShowUserAssignment(true);
  };

  if (loading) {
    return <div className="loading">Loading roles...</div>;
  }

  return (
    <div className="role-mapping-container">
      <div className="role-mapping-header">
        <h2>🔐 SAML Role Mapping</h2>
        <p>Configure how roles from your Identity Provider map to local roles.</p>
      </div>

      {error && <div className="error-message">{error}</div>}
      {success && <div className="success-message">{success}</div>}

      <div className="role-mapping-actions">
        <button 
          className="btn btn-primary" 
          onClick={() => setShowCreateForm(!showCreateForm)}
        >
          {showCreateForm ? 'Cancel' : 'Create New Role'}
        </button>
        
        <button 
          className="btn btn-secondary" 
          onClick={() => setShowBulkForm(!showBulkForm)}
        >
          {showBulkForm ? 'Cancel' : 'Bulk Create Mappings'}
        </button>
        
        <button 
          className="btn btn-tertiary" 
          onClick={fetchRoles}
        >
          Refresh
        </button>
      </div>

      {/* Create Role Form */}
      {showCreateForm && (
        <div className="role-form-container">
          <h3>Create New Role</h3>
          <form onSubmit={handleCreateRole} className="role-form">
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="role-name">Role Name *</label>
                <input
                  type="text"
                  id="role-name"
                  value={newRole.name}
                  onChange={(e) => setNewRole({...newRole, name: e.target.value})}
                  required
                  placeholder="e.g., Administrator"
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="idp-role-value">IdP Role Value *</label>
                <input
                  type="text"
                  id="idp-role-value"
                  value={newRole.idp_role_value}
                  onChange={(e) => setNewRole({...newRole, idp_role_value: e.target.value})}
                  required
                  placeholder="e.g., admin"
                />
              </div>
            </div>
            
            <div className="form-group">
              <label htmlFor="role-description">Description</label>
              <textarea
                id="role-description"
                value={newRole.description}
                onChange={(e) => setNewRole({...newRole, description: e.target.value})}
                placeholder="Optional description of the role"
                rows="2"
              />
            </div>
            
            <div className="form-row">
              <div className="form-group checkbox-group">
                <label>
                  <input
                    type="checkbox"
                    checked={newRole.active}
                    onChange={(e) => setNewRole({...newRole, active: e.target.checked})}
                  />
                  Active
                </label>
              </div>
              
              <div className="form-group checkbox-group">
                <label>
                  <input
                    type="checkbox"
                    checked={newRole.is_default}
                    onChange={(e) => setNewRole({...newRole, is_default: e.target.checked})}
                  />
                  Default Role (assigned to new users)
                </label>
              </div>
            </div>
            
            <div className="form-actions">
              <button type="submit" className="btn btn-primary">Create Role</button>
              <button 
                type="button" 
                className="btn btn-secondary"
                onClick={() => setShowCreateForm(false)}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Bulk Mappings Form */}
      {showBulkForm && (
        <div className="bulk-form-container">
          <h3>Bulk Create Role Mappings</h3>
          <form onSubmit={handleBulkMappings} className="bulk-form">
            <div className="bulk-mappings-header">
              <div className="bulk-header-item">IdP Role Value</div>
              <div className="bulk-header-item">Local Role Name</div>
              <div className="bulk-header-item">Description</div>
              <div className="bulk-header-item">Active</div>
              <div className="bulk-header-item">Actions</div>
            </div>
            
            {bulkMappings.map((mapping, index) => (
              <div key={index} className="bulk-mapping-row">
                <div className="bulk-item">
                  <input
                    type="text"
                    value={mapping.idp_role_value}
                    onChange={(e) => updateBulkMapping(index, 'idp_role_value', e.target.value)}
                    placeholder="e.g., admin"
                    required
                  />
                </div>
                <div className="bulk-item">
                  <input
                    type="text"
                    value={mapping.role_name}
                    onChange={(e) => updateBulkMapping(index, 'role_name', e.target.value)}
                    placeholder="e.g., Administrator"
                    required
                  />
                </div>
                <div className="bulk-item">
                  <input
                    type="text"
                    value={mapping.description}
                    onChange={(e) => updateBulkMapping(index, 'description', e.target.value)}
                    placeholder="Optional description"
                  />
                </div>
                <div className="bulk-item checkbox-center">
                  <input
                    type="checkbox"
                    checked={mapping.active}
                    onChange={(e) => updateBulkMapping(index, 'active', e.target.checked)}
                  />
                </div>
                <div className="bulk-item">
                  <button
                    type="button"
                    className="btn btn-danger btn-small"
                    onClick={() => removeBulkMappingRow(index)}
                    disabled={bulkMappings.length === 1}
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
            
            <div className="bulk-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={addBulkMappingRow}
              >
                Add Another Mapping
              </button>
              
              <div className="bulk-submit-actions">
                <button type="submit" className="btn btn-primary">
                  Create Mappings
                </button>
                <button 
                  type="button" 
                  className="btn btn-secondary"
                  onClick={() => setShowBulkForm(false)}
                >
                  Cancel
                </button>
              </div>
            </div>
          </form>
        </div>
      )}

      {/* User Assignment Modal */}
      {showUserAssignment && selectedRole && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Assign Users to Role: {selectedRole.name}</h3>
              <button 
                className="btn btn-close"
                onClick={() => setShowUserAssignment(false)}
              >
                ×
              </button>
            </div>
            
            <div className="modal-body">
              <div className="role-info">
                <p><strong>IdP Role Value:</strong> <code>{selectedRole.idp_role_value}</code></p>
                <p><strong>Description:</strong> {selectedRole.description || 'No description'}</p>
                <p><strong>Current Users:</strong> {selectedRole.user_count}</p>
              </div>
              
              <div className="user-assignment-list">
                <h4>Users</h4>
                {users.length === 0 ? (
                  <p>No users found in the system.</p>
                ) : (
                  <div className="user-list">
                    {users.map((user) => {
                      const hasRole = user.roles && user.roles.some(role => role.id === selectedRole.id);
                      return (
                        <div key={user.id} className="user-item">
                          <div className="user-info">
                            <div className="user-name">{user.formatted_name || user.username}</div>
                            <div className="user-email">{user.email}</div>
                            <div className="user-status">
                              {user.active ? 'Active' : 'Inactive'}
                              {user.sync_status && (
                                <span className={`sync-status ${user.sync_status}`}>
                                  {user.sync_status}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="user-actions">
                            {hasRole ? (
                              <button
                                className="btn btn-small btn-danger"
                                onClick={() => removeRoleFromUser(selectedRole.id, user.id)}
                              >
                                Remove Role
                              </button>
                            ) : (
                              <button
                                className="btn btn-small btn-primary"
                                onClick={() => assignRoleToUser(selectedRole.id, user.id)}
                              >
                                Assign Role
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
            
            <div className="modal-footer">
              <button 
                className="btn btn-secondary"
                onClick={() => setShowUserAssignment(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Roles List */}
      <div className="roles-list">
        <h3>Existing Roles ({roles.length})</h3>
        
        {roles.length === 0 ? (
          <div className="empty-state">
            <p>No roles configured yet. Create your first role to get started with SAML role mapping.</p>
          </div>
        ) : (
          <div className="roles-table">
            <div className="table-header">
              <div className="table-cell">Role Name</div>
              <div className="table-cell">IdP Role Value</div>
              <div className="table-cell">Description</div>
              <div className="table-cell">Users</div>
              <div className="table-cell">Status</div>
              <div className="table-cell">Actions</div>
            </div>
            
            {roles.map((role) => (
              <div key={role.id} className="table-row">
                <div className="table-cell">
                  <div className="role-name">
                    {role.name}
                    {role.is_default && <span className="default-badge">Default</span>}
                  </div>
                </div>
                <div className="table-cell">
                  <code className="idp-value">{role.idp_role_value || 'Not set'}</code>
                </div>
                <div className="table-cell">
                  <span className="description">{role.description || 'No description'}</span>
                </div>
                <div className="table-cell">
                  <span className="user-count">{role.user_count}</span>
                </div>
                <div className="table-cell">
                  <span className={`status ${role.active ? 'active' : 'inactive'}`}>
                    {role.active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <div className="table-cell">
                  <div className="action-buttons">
                    <button
                      className="btn btn-small btn-primary"
                      onClick={() => handleShowUserAssignment(role)}
                    >
                      Assign Users
                    </button>
                    <button
                      className="btn btn-small btn-secondary"
                      onClick={() => handleToggleRole(role.id, role.active)}
                    >
                      {role.active ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      className="btn btn-small btn-danger"
                      onClick={() => handleDeleteRole(role.id)}
                      disabled={role.user_count > 0}
                      title={role.user_count > 0 ? 'Remove users from role first' : 'Delete role'}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Role Mapping Information */}
      <div className="role-mapping-info">
        <h3>📋 SAML Role Mapping Information</h3>
        <div className="info-content">
          <p><strong>How it works:</strong></p>
          <ul>
            <li>Configure roles here that map to roles in your Identity Provider</li>
            <li>During SAML authentication, the IdP sends role information in the <code>idp_role</code> attribute</li>
            <li>Users are automatically assigned roles based on their IdP roles</li>
            <li>These roles are then sent to Datadog for role mapping in their system</li>
          </ul>
          
          <p><strong>Configuration in Datadog:</strong></p>
          <ul>
            <li>Go to Organization Settings → SAML Group Mappings</li>
            <li>Create mappings from <code>idp_role</code> attribute values to Datadog roles</li>
            <li>Enable mappings to activate role-based access control</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default RoleMapping; 