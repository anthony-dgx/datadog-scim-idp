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
  RotateCcw
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
            Manage groups and team memberships with Datadog sync
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button 
            onClick={handleBulkSync}
            className="btn btn-secondary"
            disabled={syncing.bulk}
          >
            {syncing.bulk ? (
              <div className="spinner" style={{ width: '16px', height: '16px', margin: 0 }}></div>
            ) : (
              <RefreshCw size={16} />
            )}
            Bulk Sync
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

      {groups.length === 0 ? (
        <div className="empty-state">
          <UserPlus className="empty-state-icon" />
          <h3 className="empty-state-title">No Groups Found</h3>
          <p className="empty-state-description">
            Get started by creating your first group.
          </p>
          <button 
            onClick={() => setShowModal(true)}
            className="btn btn-primary"
          >
            <Plus size={16} />
            Create Group
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '24px' }}>
          {groups.map(group => (
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
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => handleSync(group.id)}
                    className="btn btn-success btn-sm"
                    disabled={syncing[group.id]}
                    title="Sync to Datadog"
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
                    title="Edit group"
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
                  <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#f0f6fc', marginBottom: '8px' }}>
                    Members ({group.members.length})
                  </h4>
                  
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
                            title="Remove from group"
                          >
                            <UserMinus size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {getAvailableUsers(group).length > 0 && (
                  <div>
                    <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#f0f6fc', marginBottom: '8px' }}>
                      Add Members
                    </h4>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {getAvailableUsers(group).slice(0, 5).map(user => (
                        <button
                          key={user.id}
                          onClick={() => handleAddMember(group.id, user.id)}
                          className="btn btn-secondary btn-sm"
                          style={{ fontSize: '12px' }}
                          title={`Add ${user.formatted_name || user.username} to group`}
                        >
                          <UserPlus size={12} />
                          {user.formatted_name || user.username}
                        </button>
                      ))}
                      {getAvailableUsers(group).length > 5 && (
                        <span style={{ color: '#8b949e', fontSize: '12px', alignSelf: 'center' }}>
                          +{getAvailableUsers(group).length - 5} more
                        </span>
                      )}
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
                <label className="form-label">Group Name *</label>
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
                  className="form-input form-textarea"
                  placeholder="Optional group description"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Members</label>
                <div style={{ 
                  maxHeight: '200px', 
                  overflowY: 'auto', 
                  border: '1px solid #30363d', 
                  borderRadius: '8px',
                  padding: '8px'
                }}>
                  {users.length === 0 ? (
                    <p style={{ color: '#8b949e', fontSize: '14px', textAlign: 'center', padding: '20px' }}>
                      No users available
                    </p>
                  ) : (
                    users.map(user => (
                      <label 
                        key={user.id}
                        style={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          gap: '8px', 
                          padding: '8px',
                          cursor: 'pointer',
                          borderRadius: '4px'
                        }}
                        onMouseEnter={e => e.target.style.background = 'rgba(177, 186, 196, 0.05)'}
                        onMouseLeave={e => e.target.style.background = 'transparent'}
                      >
                        <input
                          type="checkbox"
                          checked={formData.member_ids.includes(user.id)}
                          onChange={() => handleMemberSelect(user.id)}
                          style={{ margin: 0 }}
                        />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: '500', color: '#f0f6fc', fontSize: '14px' }}>
                            {user.formatted_name || user.username}
                          </div>
                          <div style={{ color: '#8b949e', fontSize: '12px' }}>
                            {user.email}
                          </div>
                        </div>
                      </label>
                    ))
                  )}
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
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default GroupList; 