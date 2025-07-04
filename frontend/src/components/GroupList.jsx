import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { 
  Plus, 
  Edit2, 
  Trash2, 
  RefreshCw, 
  X,
  UserPlus,
  Users,
  Clock,
  CheckCircle,
  AlertCircle,
  UserMinus,
  RotateCcw,
  Search,
  ChevronDown,
  ChevronUp,
  Database
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

const GroupList = () => {
  const [groups, setGroups] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingGroup, setEditingGroup] = useState(null);
  const [syncing, setSyncing] = useState({});
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedGroups, setExpandedGroups] = useState({});
  const [formData, setFormData] = useState({
    display_name: '',
    description: '',
    member_ids: []
  });

  const fetchGroups = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/groups`);
      setGroups(response.data);
    } catch (error) {
      toast.error('Failed to fetch groups');
      console.error('Error fetching groups:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchUsers = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/users`);
      setUsers(response.data);
    } catch (error) {
      console.error('Error fetching users:', error);
    }
  };

  useEffect(() => {
    fetchGroups();
    fetchUsers();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      if (editingGroup) {
        const response = await axios.put(`${API_BASE_URL}/api/groups/${editingGroup.id}`, formData);
        setGroups(groups.map(group => group.id === editingGroup.id ? response.data : group));
        toast.success('Group updated successfully');
      } else {
        const response = await axios.post(`${API_BASE_URL}/api/groups`, formData);
        setGroups([...groups, response.data]);
        toast.success('Group created successfully');
      }
      
      handleCloseModal();
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to save group';
      toast.error(message);
      console.error('Error saving group:', error);
    }
  };

  const handleEdit = (group) => {
    setEditingGroup(group);
    setFormData({
      display_name: group.display_name,
      description: group.description || '',
      member_ids: group.members.map(member => member.id)
    });
    setShowModal(true);
  };

  const handleDelete = async (groupId) => {
    if (!window.confirm('Are you sure you want to delete this group?')) {
      return;
    }

    try {
      await axios.delete(`${API_BASE_URL}/api/groups/${groupId}`);
      setGroups(groups.filter(group => group.id !== groupId));
      toast.success('Group deleted successfully');
    } catch (error) {
      toast.error('Failed to delete group');
      console.error('Error deleting group:', error);
    }
  };

  const handleAddMember = async (groupId, userId) => {
    try {
      await axios.post(`${API_BASE_URL}/api/groups/${groupId}/members/${userId}`);
      // Refresh groups to get updated member list
      fetchGroups();
      toast.success('Member added to group');
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to add member to group';
      toast.error(message);
      console.error('Error adding member to group:', error);
    }
  };

  const handleRemoveMember = async (groupId, userId) => {
    try {
      await axios.delete(`${API_BASE_URL}/api/groups/${groupId}/members/${userId}`);
      // Refresh groups to get updated member list
      fetchGroups();
      toast.success('Member removed from group');
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to remove member from group';
      toast.error(message);
      console.error('Error removing member from group:', error);
    }
  };

  const handleSync = async (groupId) => {
    setSyncing(prev => ({ ...prev, [groupId]: true }));
    
    try {
      const response = await axios.post(`${API_BASE_URL}/api/groups/${groupId}/sync`);
      
      if (response.data.success) {
        toast.success(response.data.message);
        // Refresh group data to get updated sync status
        fetchGroups();
      } else {
        toast.error(response.data.message);
      }
    } catch (error) {
      toast.error('Failed to sync group to Datadog');
      console.error('Error syncing group:', error);
    } finally {
      setSyncing(prev => ({ ...prev, [groupId]: false }));
    }
  };

  const handleBulkSync = async () => {
    setSyncing(prev => ({ ...prev, bulk: true }));
    
    try {
      const response = await axios.post(`${API_BASE_URL}/api/groups/bulk-sync`);
      
      if (response.data.success) {
        toast.success(response.data.message);
        fetchGroups();
      } else {
        toast.error(response.data.message);
      }
    } catch (error) {
      toast.error('Failed to bulk sync groups');
      console.error('Error bulk syncing groups:', error);
    } finally {
      setSyncing(prev => ({ ...prev, bulk: false }));
    }
  };

  const handleClearAll = async () => {
    const groupCount = groups.length;
    if (groupCount === 0) {
      toast.info('No groups to clear');
      return;
    }

    const confirmed = window.confirm(
      `⚠️ WARNING: This will permanently delete ALL ${groupCount} groups from the local database.\n\n` +
      'This action cannot be undone. Are you sure you want to continue?'
    );
    
    if (!confirmed) return;

    // Double confirmation for destructive action
    const doubleConfirmed = window.confirm(
      `🚨 FINAL CONFIRMATION: You are about to delete ALL ${groupCount} groups.\n\n` +
      'Type "DELETE ALL GROUPS" and click OK to proceed.'
    );
    
    if (!doubleConfirmed) return;

    setSyncing(prev => ({ ...prev, clearAll: true }));
    
    try {
      const response = await axios.delete(`${API_BASE_URL}/api/groups/clear-all`);
      
      if (response.data.success) {
        toast.success(response.data.message);
        setGroups([]);
        setExpandedGroups({});
      } else {
        toast.error('Failed to clear groups');
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to clear groups';
      toast.error(message);
      console.error('Error clearing groups:', error);
    } finally {
      setSyncing(prev => ({ ...prev, clearAll: false }));
    }
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditingGroup(null);
    setFormData({
      display_name: '',
      description: '',
      member_ids: []
    });
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleMemberSelect = (userId) => {
    setFormData(prev => ({
      ...prev,
      member_ids: prev.member_ids.includes(userId)
        ? prev.member_ids.filter(id => id !== userId)
        : [...prev.member_ids, userId]
    }));
  };

  const getSyncStatusBadge = (group) => {
    const status = group.sync_status;
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
          <span className="status-badge failed" title={group.sync_error}>
            <AlertCircle {...iconProps} />
            Failed
          </span>
        );
      case 'warning':
        return (
          <span className="status-badge warning" title={group.sync_error}>
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

  const getAvailableUsers = (group) => {
    const memberIds = group.members.map(member => member.id);
    return users.filter(user => !memberIds.includes(user.id));
  };

  const toggleExpandGroup = (groupId) => {
    setExpandedGroups(prev => ({
      ...prev,
      [groupId]: !prev[groupId]
    }));
  };

  const filteredGroups = groups.filter(group => 
    group.display_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    group.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
        Loading groups...
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2 className="card-title">Groups</h2>
          <p style={{ color: '#8b949e', marginTop: '4px' }}>
            Manage groups and team memberships - automatically syncs with Datadog on updates
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          {groups.length > 0 && (
            <button 
              onClick={handleClearAll}
              className="btn btn-danger"
              disabled={syncing.clearAll}
              title="Clear all groups from local database (for testing/development)"
            >
              {syncing.clearAll ? (
                <div className="spinner" style={{ width: '16px', height: '16px', margin: 0 }}></div>
              ) : (
                <Database size={16} />
              )}
              Clear All
            </button>
          )}
          <button 
            onClick={handleBulkSync}
            className="btn btn-secondary"
            disabled={syncing.bulk}
            title="Force sync all pending groups to Datadog"
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
            Add Group
          </button>
        </div>
      </div>

      {/* Search Bar */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ position: 'relative' }}>
          <Search size={20} style={{ 
            position: 'absolute', 
            left: '12px', 
            top: '50%', 
            transform: 'translateY(-50%)', 
            color: '#8b949e' 
          }} />
          <input
            type="text"
            placeholder="Search groups by name or description..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="form-input"
            style={{ 
              paddingLeft: '44px',
              fontSize: '14px',
              height: '40px'
            }}
          />
        </div>
      </div>

      {filteredGroups.length === 0 ? (
        <div className="empty-state">
          {searchTerm ? (
            <>
              <Search className="empty-state-icon" />
              <h3 className="empty-state-title">No Groups Found</h3>
              <p className="empty-state-description">
                No groups match your search criteria. Try adjusting your search terms.
              </p>
              <button 
                onClick={() => setSearchTerm('')}
                className="btn btn-secondary"
              >
                Clear Search
              </button>
            </>
          ) : (
            <>
              <UserPlus className="empty-state-icon" />
              <h3 className="empty-state-title">No Groups Found</h3>
              <p className="empty-state-description">
                Get started by creating your first group. Groups automatically sync to Datadog when updated.
              </p>
              <button 
                onClick={() => setShowModal(true)}
                className="btn btn-primary"
              >
                <Plus size={16} />
                Create Group
              </button>
            </>
          )}
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '24px' }}>
          {filteredGroups.map(group => (
            <div key={group.id} className="card" style={{ margin: 0 }}>
              <div className="card-header">
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#f0f6fc', margin: 0 }}>
                    {group.display_name}
                  </h3>
                  {group.description && (
                    <p style={{ color: '#8b949e', margin: '4px 0 0', fontSize: '14px' }}>
                      {group.description}
                    </p>
                  )}
                  <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginTop: '8px' }}>
                    {getSyncStatusBadge(group)}
                    <span style={{ fontSize: '13px', color: '#8b949e' }}>
                      {group.last_synced ? (
                        `Last synced ${formatDistanceToNow(new Date(group.last_synced), { addSuffix: true })}`
                      ) : (
                        'Never synced'
                      )}
                    </span>
                    {group.datadog_group_id && (
                      <span style={{ fontSize: '11px', color: '#7c3aed', padding: '2px 6px', background: 'rgba(124, 58, 237, 0.1)', borderRadius: '4px' }}>
                        Auto-sync enabled
                      </span>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => handleSync(group.id)}
                    className="btn btn-success btn-sm"
                    disabled={syncing[group.id]}
                    title="Force sync to Datadog (updates happen automatically)"
                  >
                    {syncing[group.id] ? (
                      <div className="spinner" style={{ width: '12px', height: '12px', margin: 0 }}></div>
                    ) : (
                      <RotateCcw size={14} />
                    )}
                  </button>
                  
                  <button
                    onClick={() => handleEdit(group)}
                    className="btn btn-secondary btn-sm"
                    title="Edit group (will auto-sync to Datadog)"
                  >
                    <Edit2 size={14} />
                  </button>
                  
                  <button
                    onClick={() => handleDelete(group.id)}
                    className="btn btn-danger btn-sm"
                    title="Delete group"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              <div>
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#f0f6fc', margin: 0 }}>
                      Members ({group.members.length})
                    </h4>
                    {getAvailableUsers(group).length > 0 && (
                      <button
                        onClick={() => toggleExpandGroup(group.id)}
                        className="btn btn-secondary btn-sm"
                        title={expandedGroups[group.id] ? "Hide add members" : "Show add members"}
                      >
                        {expandedGroups[group.id] ? (
                          <>
                            <ChevronUp size={14} />
                            Hide Add Members
                          </>
                        ) : (
                          <>
                            <ChevronDown size={14} />
                            Add Members
                          </>
                        )}
                      </button>
                    )}
                  </div>
                  
                  {group.members.length === 0 ? (
                    <p style={{ color: '#8b949e', fontSize: '14px', fontStyle: 'italic' }}>
                      No members in this group
                    </p>
                  ) : (
                    <div style={{ display: 'grid', gap: '8px' }}>
                      {group.members.map(member => (
                        <div key={member.id} style={{ 
                          display: 'flex', 
                          justifyContent: 'space-between', 
                          alignItems: 'center',
                          padding: '8px 12px',
                          background: 'rgba(177, 186, 196, 0.05)',
                          borderRadius: '6px',
                          border: '1px solid #30363d'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <div style={{ 
                              width: '32px', 
                              height: '32px', 
                              borderRadius: '50%', 
                              background: 'linear-gradient(135deg, #632ca6 0%, #7c3aed 100%)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: 'white',
                              fontSize: '12px',
                              fontWeight: '600'
                            }}>
                              {(member.formatted_name || member.username).charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <div style={{ fontWeight: '500', color: '#f0f6fc', fontSize: '14px' }}>
                                {member.formatted_name || member.username}
                              </div>
                              <div style={{ color: '#8b949e', fontSize: '12px' }}>
                                {member.email}
                              </div>
                            </div>
                          </div>
                          <button
                            onClick={() => handleRemoveMember(group.id, member.id)}
                            className="btn btn-danger btn-sm"
                            title="Remove from group (will auto-sync to Datadog)"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Collapsible Add Members Section */}
                {expandedGroups[group.id] && getAvailableUsers(group).length > 0 && (
                  <div style={{ marginTop: '16px', padding: '16px', background: 'rgba(177, 186, 196, 0.02)', borderRadius: '8px', border: '1px solid #30363d' }}>
                    <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#f0f6fc', marginBottom: '12px' }}>
                      Available Users ({getAvailableUsers(group).length})
                    </h4>
                    <div style={{ display: 'grid', gap: '8px' }}>
                      {getAvailableUsers(group).map(user => (
                        <div key={user.id} style={{ 
                          display: 'flex', 
                          justifyContent: 'space-between', 
                          alignItems: 'center',
                          padding: '8px 12px',
                          background: 'rgba(177, 186, 196, 0.03)',
                          borderRadius: '6px',
                          border: '1px solid #30363d'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <div style={{ 
                              width: '32px', 
                              height: '32px', 
                              borderRadius: '50%', 
                              background: 'linear-gradient(135deg, #0d1117 0%, #21262d 100%)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: '#8b949e',
                              fontSize: '12px',
                              fontWeight: '600',
                              border: '1px solid #30363d'
                            }}>
                              {(user.formatted_name || user.username).charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <div style={{ fontWeight: '500', color: '#f0f6fc', fontSize: '14px' }}>
                                {user.formatted_name || user.username}
                              </div>
                              <div style={{ color: '#8b949e', fontSize: '12px' }}>
                                {user.email}
                              </div>
                            </div>
                          </div>
                          <button
                            onClick={() => handleAddMember(group.id, user.id)}
                            className="btn btn-primary btn-sm"
                            title="Add to group (will auto-sync to Datadog)"
                          >
                            <Plus size={14} />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={handleCloseModal}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                {editingGroup ? 'Edit Group' : 'Create Group'}
              </h3>
              <button onClick={handleCloseModal} className="modal-close">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Display Name *</label>
                <input
                  type="text"
                  name="display_name"
                  value={formData.display_name}
                  onChange={handleInputChange}
                  className="form-input"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea
                  name="description"
                  value={formData.description}
                  onChange={handleInputChange}
                  className="form-input"
                  rows="3"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Members</label>
                <div style={{ 
                  maxHeight: '200px', 
                  overflowY: 'auto',
                  border: '1px solid #30363d',
                  borderRadius: '6px',
                  padding: '8px'
                }}>
                  {users.map(user => (
                    <label key={user.id} className="form-label" style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: '8px',
                      padding: '4px 8px',
                      margin: 0,
                      cursor: 'pointer'
                    }}>
                      <input
                        type="checkbox"
                        checked={formData.member_ids.includes(user.id)}
                        onChange={() => handleMemberSelect(user.id)}
                        className="form-checkbox"
                      />
                      <span style={{ color: '#f0f6fc' }}>
                        {user.formatted_name || user.username} ({user.email})
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" onClick={handleCloseModal} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingGroup ? 'Update Group' : 'Create Group'}
                </button>
              </div>
              
              {editingGroup && (
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

export default GroupList; 