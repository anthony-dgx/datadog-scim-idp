import React, { useState, useEffect } from 'react';
import { Download, Upload, Eye, EyeOff, Trash2, CheckCircle, XCircle, AlertCircle, FileText, Server } from 'lucide-react';
import './SAMLConfig.css';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

const SAMLConfig = () => {
  const [metadata, setMetadata] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState('');
  const [showIdPMetadata, setShowIdPMetadata] = useState(false);
  const [jitConfig, setJitConfig] = useState(null);
  const [showJitConfig, setShowJitConfig] = useState(false);

  useEffect(() => {
    fetchMetadata();
    fetchJitConfig();
  }, []);

  const fetchMetadata = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/saml/metadata-list`);
      if (response.ok) {
        const data = await response.json();
        setMetadata(data);
      }
    } catch (error) {
      console.error('Error fetching metadata:', error);
    }
  };

  const fetchJitConfig = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/saml/jit-config`);
      if (response.ok) {
        const data = await response.json();
        setJitConfig(data);
      }
    } catch (error) {
      console.error('Error fetching JIT config:', error);
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedFile(file);
      setUploadStatus('');
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setUploadStatus('');

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch(`${API_BASE_URL}/api/saml/metadata`, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        setUploadStatus('success');
        setSelectedFile(null);
        fetchMetadata();
        // Reset file input
        const fileInput = document.getElementById('metadata-file');
        if (fileInput) fileInput.value = '';
      } else {
        const error = await response.json();
        setUploadStatus('error');
        console.error('Upload failed:', error);
      }
    } catch (error) {
      setUploadStatus('error');
      console.error('Upload error:', error);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (metadataId) => {
    if (!window.confirm(`Are you sure you want to delete this metadata record?`)) return;

    try {
      const response = await fetch(`${API_BASE_URL}/api/saml/metadata/${metadataId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        fetchMetadata();
      } else {
        console.error('Delete failed');
      }
    } catch (error) {
      console.error('Delete error:', error);
    }
  };

  const handleDownload = async (metadataRecord) => {
    try {
      // For now, we'll create a downloadable XML file from the metadata
      const xmlContent = metadataRecord.metadata_xml || `<?xml version="1.0"?>
<EntityDescriptor entityID="${metadataRecord.entity_id}">
  <SPSSODescriptor>
    <AssertionConsumerService Location="${metadataRecord.acs_url}" Binding="${metadataRecord.acs_binding}" />
  </SPSSODescriptor>
</EntityDescriptor>`;
      
      const blob = new Blob([xmlContent], { type: 'application/xml' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${metadataRecord.entity_id.replace(/[^a-zA-Z0-9]/g, '_')}-metadata.xml`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download error:', error);
    }
  };

  const downloadIdPMetadata = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/saml/metadata`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'idp-metadata.xml';
        a.click();
        window.URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Download error:', error);
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
        return <CheckCircle size={16} />;
      case 'error':
        return <XCircle size={16} />;
      default:
        return <AlertCircle size={16} />;
    }
  };

  return (
    <div className="saml-config">
      <div className="page-header">
        <h1>SAML Configuration</h1>
        <p>Manage SAML metadata and configure single sign-on</p>
      </div>

      <div className="config-grid">
        {/* Upload Section */}
        <div className="config-section">
          <h2>
            <Upload size={20} />
            Upload SP Metadata
          </h2>
          <p className="section-description">
            Upload Service Provider metadata XML files to configure SAML authentication
          </p>
          
          <div className="upload-section">
            <div className="upload-text">
              <FileText size={24} />
              <strong>Choose metadata file</strong>
            </div>
            <p className="upload-subtext">
              Select an XML file containing Service Provider metadata
            </p>
            <input
              type="file"
              id="metadata-file"
              accept=".xml,application/xml,text/xml"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
            <label htmlFor="metadata-file" className="btn btn-secondary">
              <Upload size={16} />
              Select File
            </label>
          </div>

          {selectedFile && (
            <div className="status-message info">
              <FileText size={16} />
              Selected: {selectedFile.name}
            </div>
          )}

          {uploadStatus && (
            <div className={`status-message ${uploadStatus}`}>
              {getStatusIcon(uploadStatus)}
              {uploadStatus === 'success' ? 'Metadata uploaded successfully!' : 'Upload failed. Please try again.'}
            </div>
          )}

          <button
            className="btn btn-primary"
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
          >
            {uploading ? 'Uploading...' : 'Upload Metadata'}
          </button>
        </div>

        {/* Download Section */}
        <div className="config-section">
          <h2>
            <Server size={20} />
            Identity Provider
          </h2>
          <p className="section-description">
            Download the Identity Provider metadata to configure your Service Provider
          </p>
          
          <div className="provider-info">
            <h3>
              <Download size={16} />
              IdP Metadata
            </h3>
            <div className="info-grid">
              <div className="info-item">
                <label>SSO URL</label>
                <div className="value">http://localhost:8000/saml/login</div>
              </div>
              <div className="info-item">
                <label>Entity ID</label>
                <div className="value">http://localhost:8000/saml/metadata</div>
              </div>
              <div className="info-item">
                <label>Metadata URL</label>
                <div className="value">http://localhost:8000/saml/metadata</div>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <button className="btn btn-primary" onClick={downloadIdPMetadata}>
              <Download size={16} />
              Download Metadata
            </button>
            <button 
              className="btn btn-secondary"
              onClick={() => setShowIdPMetadata(!showIdPMetadata)}
            >
              {showIdPMetadata ? <EyeOff size={16} /> : <Eye size={16} />}
              {showIdPMetadata ? 'Hide' : 'View'} Metadata
            </button>
          </div>
        </div>

        {/* JIT Configuration Section */}
        <div className="jit-config-section">
          <div className="section-header">
            <h3>
              <Server size={20} />
              Just-In-Time Provisioning
            </h3>
            <button
              className="toggle-button"
              onClick={() => setShowJitConfig(!showJitConfig)}
            >
              {showJitConfig ? <EyeOff size={16} /> : <Eye size={16} />}
              {showJitConfig ? 'Hide' : 'Show'} JIT Config
            </button>
          </div>
          
          {showJitConfig && jitConfig && (
            <div className="jit-config-details">
              <div className="config-row">
                <div className="config-item">
                  <strong>JIT Enabled:</strong>
                  <span className={`status ${jitConfig.jit_enabled ? 'enabled' : 'disabled'}`}>
                    {jitConfig.jit_enabled ? 'Yes' : 'No'}
                  </span>
                </div>
                <div className="config-item">
                  <strong>Auto-activate Users:</strong>
                  <span className={`status ${jitConfig.auto_activate ? 'enabled' : 'disabled'}`}>
                    {jitConfig.auto_activate ? 'Yes' : 'No'}
                  </span>
                </div>
              </div>
              
              <div className="config-row">
                <div className="config-item">
                  <strong>Create in Datadog:</strong>
                  <span className={`status ${jitConfig.create_in_datadog ? 'enabled' : 'disabled'}`}>
                    {jitConfig.create_in_datadog ? 'Yes' : 'No'}
                  </span>
                </div>
                <div className="config-item">
                  <strong>Default Title:</strong>
                  <span className="value">{jitConfig.default_title}</span>
                </div>
              </div>

              <div className="supported-flows">
                <strong>Supported Flows:</strong>
                <ul>
                  {jitConfig.supported_flows.map((flow, index) => (
                    <li key={index}>{flow}</li>
                  ))}
                </ul>
              </div>

              <div className="attribute-mappings">
                <strong>SAML Attribute Mappings:</strong>
                <div className="mapping-grid">
                  {Object.entries(jitConfig.supported_attribute_mappings).map(([saml, local]) => (
                    <div key={saml} className="mapping-item">
                      <code>{saml}</code> → <code>{local}</code>
                    </div>
                  ))}
                </div>
              </div>

              <div className="sample-attributes">
                <strong>Sample SAML Attributes:</strong>
                <pre className="sample-code">
                  {JSON.stringify(jitConfig.sample_saml_attributes.example, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Metadata Preview */}
      {showIdPMetadata && (
        <div className="config-section">
          <button 
            className="metadata-toggle"
            onClick={() => setShowIdPMetadata(!showIdPMetadata)}
          >
            <span>Identity Provider Metadata</span>
            {showIdPMetadata ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
          <div className="metadata-content">
            <pre>
              <code>
{`<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" 
                     entityID="http://localhost:8000/saml/metadata">
  <md:IDPSSODescriptor WantAuthnRequestsSigned="true" 
                       protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <md:SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" 
                           Location="http://localhost:8000/saml/login"/>
    <md:SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect" 
                           Location="http://localhost:8000/saml/login"/>
  </md:IDPSSODescriptor>
</md:EntityDescriptor>`}
              </code>
            </pre>
          </div>
        </div>
      )}

      {/* Uploaded Metadata List */}
      {metadata.length > 0 && (
        <div className="config-section">
          <h2>
            <FileText size={20} />
            Uploaded Metadata Files
          </h2>
          <p className="section-description">
            Manage your uploaded Service Provider metadata files
          </p>
          
          <div className="metadata-list">
            {metadata.map((record, index) => (
              <div key={index} className="metadata-item">
                <div className="metadata-info">
                  <h3>{record.entity_id}</h3>
                  <p>
                    ACS URL: {record.acs_url || 'Not specified'} • 
                    Uploaded: {new Date(record.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="metadata-actions">
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleDownload(record)}
                  >
                    <Download size={14} />
                    Download
                  </button>
                  <button
                    className="btn btn-danger"
                    onClick={() => handleDelete(record.id)}
                  >
                    <Trash2 size={14} />
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default SAMLConfig; 