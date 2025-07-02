import React, { useState, useEffect } from 'react';
import './SAMLConfig.css';

const SAMLConfig = () => {
  const [metadata, setMetadata] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState('');
  const [showIdPMetadata, setShowIdPMetadata] = useState(false);

  useEffect(() => {
    fetchMetadata();
  }, []);

  const fetchMetadata = async () => {
    try {
      const response = await fetch('/api/saml/metadata-list');
      if (response.ok) {
        const data = await response.json();
        setMetadata(data);
      }
    } catch (error) {
      console.error('Failed to fetch metadata:', error);
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    setSelectedFile(file);
    setUploadStatus('');
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setUploadStatus('Please select a file first');
      return;
    }

    if (!selectedFile.name.endsWith('.xml')) {
      setUploadStatus('Please select an XML file');
      return;
    }

    setUploading(true);
    setUploadStatus('');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await fetch('/api/saml/metadata', {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const result = await response.json();
        setUploadStatus(`✅ Successfully uploaded metadata for ${result.entity_id}`);
        setSelectedFile(null);
        // Reset file input
        const fileInput = document.getElementById('metadata-file');
        if (fileInput) fileInput.value = '';
        // Refresh metadata list
        fetchMetadata();
      } else {
        const error = await response.json();
        setUploadStatus(`❌ Upload failed: ${error.detail}`);
      }
    } catch (error) {
      setUploadStatus(`❌ Upload failed: ${error.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDownloadIdPMetadata = async () => {
    try {
      const response = await fetch('/saml/metadata');
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = 'idp-metadata.xml';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
      } else {
        alert('Failed to download IdP metadata');
      }
    } catch (error) {
      alert(`Failed to download IdP metadata: ${error.message}`);
    }
  };

  const handleDeleteMetadata = async (metadataId, entityId) => {
    // eslint-disable-next-line no-restricted-globals
    if (!confirm(`Are you sure you want to delete metadata for ${entityId}?`)) {
      return;
    }

    try {
      const response = await fetch(`/api/saml/metadata/${metadataId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        setUploadStatus(`✅ Deleted metadata for ${entityId}`);
        fetchMetadata();
      } else {
        const error = await response.json();
        setUploadStatus(`❌ Delete failed: ${error.detail}`);
      }
    } catch (error) {
      setUploadStatus(`❌ Delete failed: ${error.message}`);
    }
  };

  const toggleIdPMetadata = () => {
    setShowIdPMetadata(!showIdPMetadata);
  };

  return (
    <div className="saml-config">
      <div className="header">
        <h2>🔐 SAML Identity Provider Configuration</h2>
        <p>Configure SAML SSO for Datadog authentication</p>
      </div>

      {/* IdP Metadata Section */}
      <div className="card">
        <h3>📄 Identity Provider Metadata</h3>
        <p>Download this metadata XML file to configure SAML in Datadog</p>
        
        <div className="metadata-actions">
          <button 
            onClick={handleDownloadIdPMetadata}
            className="btn btn-primary"
          >
            📥 Download IdP Metadata XML
          </button>
          
          <button 
            onClick={toggleIdPMetadata}
            className="btn btn-secondary"
          >
            {showIdPMetadata ? 'Hide' : 'Show'} Metadata URL
          </button>
        </div>

        {showIdPMetadata && (
          <div className="metadata-info">
            <p><strong>Metadata URL:</strong></p>
            <code>{window.location.origin}/saml/metadata</code>
            <p className="info-text">
              Use this URL in Datadog's SAML configuration or download the XML file above.
            </p>
          </div>
        )}
      </div>

      {/* SP Metadata Upload Section */}
      <div className="card">
        <h3>📤 Upload Datadog Service Provider Metadata</h3>
        <p>Upload the SP metadata XML file downloaded from Datadog's SAML configuration page</p>
        
        <div className="upload-section">
          <div className="file-input-group">
            <input
              type="file"
              id="metadata-file"
              accept=".xml"
              onChange={handleFileSelect}
              className="file-input"
            />
            <label htmlFor="metadata-file" className="file-label">
              {selectedFile ? selectedFile.name : 'Choose XML file...'}
            </label>
          </div>
          
          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            className="btn btn-primary"
          >
            {uploading ? '⏳ Uploading...' : '📤 Upload Metadata'}
          </button>
        </div>

        {uploadStatus && (
          <div className={`status-message ${uploadStatus.includes('❌') ? 'error' : 'success'}`}>
            {uploadStatus}
          </div>
        )}
      </div>

      {/* Current SP Metadata Section */}
      <div className="card">
        <h3>📋 Configured Service Provider Metadata</h3>
        
        {metadata.length === 0 ? (
          <div className="no-metadata">
            <p>No Service Provider metadata configured yet.</p>
            <p>Upload Datadog's SP metadata XML file above to configure SAML SSO.</p>
          </div>
        ) : (
          <div className="metadata-list">
            {metadata.map((item) => (
              <div key={item.id} className="metadata-item">
                <div className="metadata-header">
                  <h4>{item.entity_id}</h4>
                  <span className={`status ${item.active ? 'active' : 'inactive'}`}>
                    {item.active ? '✅ Active' : '❌ Inactive'}
                  </span>
                </div>
                
                <div className="metadata-details">
                  <div className="detail-row">
                    <span className="label">Assertion Consumer Service:</span>
                    <span className="value">{item.acs_url}</span>
                  </div>
                  
                  <div className="detail-row">
                    <span className="label">ACS Binding:</span>
                    <span className="value">{item.acs_binding}</span>
                  </div>

                  {item.sls_url && (
                    <div className="detail-row">
                      <span className="label">Single Logout Service:</span>
                      <span className="value">{item.sls_url}</span>
                    </div>
                  )}

                  <div className="detail-row">
                    <span className="label">NameID Formats:</span>
                    <span className="value">
                      {item.name_id_formats.length > 0 
                        ? item.name_id_formats.join(', ') 
                        : 'Not specified'}
                    </span>
                  </div>

                  <div className="detail-row">
                    <span className="label">Updated:</span>
                    <span className="value">
                      {new Date(item.updated_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                <div className="metadata-actions">
                  <button
                    onClick={() => handleDeleteMetadata(item.id, item.entity_id)}
                    className="btn btn-danger btn-small"
                  >
                    🗑️ Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* SAML Setup Instructions */}
      <div className="card instructions">
        <h3>📖 Setup Instructions</h3>
        <ol>
          <li>
            <strong>Download IdP Metadata:</strong> Click "Download IdP Metadata XML" above
          </li>
          <li>
            <strong>Configure Datadog SAML:</strong>
            <ul>
              <li>Go to Datadog → Organization Settings → Login Methods</li>
              <li>Click "Configure SAML"</li>
              <li>Upload the IdP metadata XML file or use the metadata URL</li>
              <li>Enable SAML authentication</li>
            </ul>
          </li>
          <li>
            <strong>Download SP Metadata:</strong> In Datadog's SAML configuration, download the SP metadata XML
          </li>
          <li>
            <strong>Upload SP Metadata:</strong> Upload the Datadog SP metadata XML file above
          </li>
          <li>
            <strong>Test SAML:</strong> Use the Single Sign-On URL from Datadog to test authentication
          </li>
        </ol>
        
        <div className="important-note">
          <strong>Important:</strong> Make sure you have configured the SAML certificate and private key 
          in your environment variables (SAML_CERT and SAML_KEY) before using SAML authentication.
        </div>
      </div>
    </div>
  );
};

export default SAMLConfig; 