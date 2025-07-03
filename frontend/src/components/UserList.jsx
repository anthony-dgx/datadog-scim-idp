import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { 
  Plus, 
  Edit2, 
  Trash2, 
  RefreshCw, 
  X,
  Users,
  Clock,
  CheckCircle,
  AlertCircle,
  UserX,
  RotateCcw
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

const UserList = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [syncing, setSyncing] = useState({});
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    title: '',
    active: true
  });

  const fetchUsers = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/users`);
      setUsers(response.data);
    } catch (error) {
      toast.error('Failed to fetch users');
      console.error('Error fetching users:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      if (editingUser) {
        const response = await axios.put(`${API_BASE_URL}/api/users/${editingUser.id}`, formData);
        setUsers(users.map(user => user.id === editingUser.id ? response.data : user));
        toast.success('User updated successfully');
      } else {
        const response = await axios.post(`${API_BASE_URL}/api/users`, formData);
        setUsers([...users, response.data]);
        toast.success('User created successfully');
      }
      
      handleCloseModal();
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to save user';
      toast.error(message);
      console.error('Error saving user:', error);
    }
  };

  const handleEdit = (user) => {
    setEditingUser(user);
    setFormData({
      username: user.username,
      email: user.email,
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      title: user.title || '',
      active: user.active
    });
    setShowModal(true);
  };

  const handleDelete = async (userId) => {
    if (!window.confirm('Are you sure you want to delete this user?')) {
      return;
    }

    try {
      await axios.delete(`${API_BASE_URL}/api/users/${userId}`);
      setUsers(users.filter(user => user.id !== userId));
      toast.success('User deleted successfully');
    } catch (error) {
      toast.error('Failed to delete user');
      console.error('Error deleting user:', error);
    }
  };

  const handleDeactivate = async (userId) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/users/${userId}/deactivate`);
      setUsers(users.map(user => user.id === userId ? response.data : user));
      toast.success('User deactivated successfully');
    } catch (error) {
      toast.error('Failed to deactivate user');
      console.error('Error deactivating user:', error);
    }
  };

  const handleSync = async (userId) => {
    setSyncing(prev => ({ ...prev, [userId]: true }));
    
    try {
      const response = await axios.post(`${API_BASE_URL}/api/users/${userId}/sync`);
      
      if (response.data.success) {
        toast.success(response.data.message);
        // Refresh user data to get updated sync status
        fetchUsers();
      } else {
        toast.error(response.data.message);
      }
    } catch (error) {
      toast.error('Failed to sync user to Datadog');
      console.error('Error syncing user:', error);
    } finally {
      setSyncing(prev => ({ ...prev, [userId]: false }));
    }
  };

  const handleSyncDeactivate = async (userId) => {
    setSyncing(prev => ({ ...prev, [userId]: true }));
    
    try {
      const response = await axios.post(`${API_BASE_URL}/api/users/${userId}/sync-deactivate`);
      
      if (response.data.success) {
        toast.success(response.data.message);
        fetchUsers();
      } else {
        toast.error(response.data.message);
      }
    } catch (error) {
      toast.error('Failed to deactivate user in Datadog');
      console.error('Error syncing deactivation:', error);
    } finally {
      setSyncing(prev => ({ ...prev, [userId]: false }));
    }
  };

  const handleBulkSync = async () => {
    setSyncing(prev => ({ ...prev, bulk: true }));
    
    try {
      const response = await axios.post(`${API_BASE_URL}/api/users/bulk-sync`);
      
      if (response.data.success) {
        toast.success(response.data.message);
        fetchUsers();
      } else {
        toast.error(response.data.message);
      }
    } catch (error) {
      toast.error('Failed to bulk sync users');
      console.error('Error bulk syncing users:', error);
    } finally {
      setSyncing(prev => ({ ...prev, bulk: false }));
    }
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditingUser(null);
    setFormData({
      username: '',
      email: '',
      first_name: '',
      last_name: '',
      title: '',
      active: true
    });
  };

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const getSyncStatusBadge = (user) => {
    const status = user.sync_status;
    const iconProps = { size: 12 };

    switch (status) {
      case 'synced':
        return (
          <span className="status-badge synced">
            <CheckCircle {...iconProps} />
            Synced
          </span>
        );
      case 'failed':
        return (
          <span className="status-badge failed" title={user.sync_error}>
            <AlertCircle {...iconProps} />
            Failed
          </span>
        );
      case 'warning':
        return (
          <span className="status-badge warning" title={user.sync_error}>
            <AlertCircle {...iconProps} />
            Warning
          </span>
        );
      case 'pending':
      default:
        return (
          <span className="status-badge pending">
            <Clock {...iconProps} />
            Pending
          </span>
        );
    }
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
        Loading users...
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2 className="card-title">Users</h2>
          <p style={{ color: '#8b949e', marginTop: '4px' }}>
            Manage user accounts - automatically syncs with Datadog on updates
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button 
            onClick={handleBulkSync}
            className="btn btn-secondary"
            disabled={syncing.bulk}
            title="Force sync all pending users to Datadog"
          >
            {syncing.bulk ? (
              <div className="spinner" style={{ width: '16px', height: '16px', margin: 0 }}></div>
            ) : (
              <RefreshCw size={16} />
            )}
            Force Sync All
          </button>
          <button 
            onClick={() => setShowModal(true)}
            className="btn btn-primary"
          >
            <Plus size={16} />
            Add User
          </button>
        </div>
      </div>

      {users.length === 0 ? (
        <div className="empty-state">
          <Users className="empty-state-icon" />
          <h3 className="empty-state-title">No Users Found</h3>
          <p className="empty-state-description">
            Get started by creating your first user account. Users will automatically sync to Datadog when updated.
          </p>
          <button 
            onClick={() => setShowModal(true)}
            className="btn btn-primary"
          >
            <Plus size={16} />
            Create User
          </button>
        </div>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>User</th>
                <th>Email</th>
                <th>Title</th>
                <th>Status</th>
                <th>Sync Status</th>
                <th>Last Synced</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map(user => (
                <tr key={user.id}>
                  <td>
                    <div>
                      <div style={{ fontWeight: '500', color: '#f0f6fc' }}>
                        {user.formatted_name || user.username}
                      </div>
                      <div style={{ fontSize: '13px', color: '#8b949e' }}>
                        @{user.username}
                      </div>
                    </div>
                  </td>
                  <td>{user.email}</td>
                  <td>{user.title || '-'}</td>
                  <td>
                    <span className={`status-badge ${user.active ? 'active' : 'inactive'}`}>
                      {user.active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>{getSyncStatusBadge(user)}</td>
                  <td>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                      {user.last_synced ? (
                        <span style={{ fontSize: '13px', color: '#8b949e' }}>
                          {formatDistanceToNow(new Date(user.last_synced), { addSuffix: true })}
                        </span>
                      ) : (
                        <span style={{ fontSize: '13px', color: '#8b949e' }}>Never</span>
                      )}
                      {user.datadog_user_id && (
                        <span style={{ fontSize: '11px', color: '#7c3aed' }}>
                          Auto-sync enabled
                        </span>
                      )}
                    </div>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <button
                        onClick={() => handleSync(user.id)}
                        className="btn btn-success btn-sm"
                        disabled={syncing[user.id]}
                        title="Force sync to Datadog (updates happen automatically)"
                      >
                        {syncing[user.id] ? (
                          <div className="spinner" style={{ width: '12px', height: '12px', margin: 0 }}></div>
                        ) : (
                          <RotateCcw size={14} />
                        )}
                      </button>
                      
                      <button
                        onClick={() => handleEdit(user)}
                        className="btn btn-secondary btn-sm"
                        title="Edit user (will auto-sync to Datadog)"
                      >
                        <Edit2 size={14} />
                      </button>
                      
                      {user.active ? (
                        <button
                          onClick={() => handleSyncDeactivate(user.id)}
                          className="btn btn-warning btn-sm"
                          disabled={syncing[user.id]}
                          title="Deactivate in Datadog"
                        >
                          <UserX size={14} />
                        </button>
                      ) : null}
                      
                      <button
                        onClick={() => handleDelete(user.id)}
                        className="btn btn-danger btn-sm"
                        title="Delete user"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={handleCloseModal}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                {editingUser ? 'Edit User' : 'Create User'}
              </h3>
              <button onClick={handleCloseModal} className="modal-close">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Username *</label>
                <input
                  type="text"
                  name="username"
                  value={formData.username}
                  onChange={handleInputChange}
                  className="form-input"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Email *</label>
                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  className="form-input"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">First Name</label>
                <input
                  type="text"
                  name="first_name"
                  value={formData.first_name}
                  onChange={handleInputChange}
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Last Name</label>
                <input
                  type="text"
                  name="last_name"
                  value={formData.last_name}
                  onChange={handleInputChange}
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Title</label>
                <input
                  type="text"
                  name="title"
                  value={formData.title}
                  onChange={handleInputChange}
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label className="form-label">
                  <input
                    type="checkbox"
                    name="active"
                    checked={formData.active}
                    onChange={handleInputChange}
                    className="form-checkbox"
                  />
                  Active
                </label>
              </div>

              <div className="modal-footer">
                <button type="button" onClick={handleCloseModal} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingUser ? 'Update User' : 'Create User'}
                </button>
              </div>
              
              {editingUser && (
                <div style={{ marginTop: '12px', padding: '12px', background: 'rgba(124, 58, 237, 0.1)', borderRadius: '6px', border: '1px solid rgba(124, 58, 237, 0.3)' }}>
                  <div style={{ fontSize: '13px', color: '#a855f7', fontWeight: '500' }}>
                    ✨ Auto-sync enabled
                  </div>
                  <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>
                    Changes will automatically sync to Datadog when you save
                  </div>
                </div>
              )}
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserList; 