import React, { useState, useEffect } from 'react';
import { Download, Upload, Eye, EyeOff, Trash2, CheckCircle, XCircle, AlertCircle, FileText, Server } from 'lucide-react';
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
      console.error('Error fetching metadata:', error);
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
      const response = await fetch('/api/saml/upload-metadata', {
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

  const handleDelete = async (filename) => {
    if (!window.confirm(`Are you sure you want to delete ${filename}?`)) return;

    try {
      const response = await fetch(`/api/saml/metadata/${filename}`, {
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

  const handleDownload = async (filename) => {
    try {
      const response = await fetch(`/api/saml/metadata/${filename}`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        window.URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Download error:', error);
    }
  };

  const downloadIdPMetadata = async () => {
    try {
      const response = await fetch('/api/saml/metadata');
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
                <div className="value">{window.location.origin}/saml/sso</div>
              </div>
              <div className="info-item">
                <label>Entity ID</label>
                <div className="value">{window.location.origin}/saml/metadata</div>
              </div>
              <div className="info-item">
                <label>Metadata URL</label>
                <div className="value">{window.location.origin}/api/saml/metadata</div>
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
                     entityID="${window.location.origin}/saml/metadata">
  <md:IDPSSODescriptor WantAuthnRequestsSigned="true" 
                       protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <md:SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" 
                           Location="${window.location.origin}/saml/sso"/>
    <md:SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect" 
                           Location="${window.location.origin}/saml/sso"/>
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
            {metadata.map((file, index) => (
              <div key={index} className="metadata-item">
                <div className="metadata-info">
                  <h3>{file.filename}</h3>
                  <p>
                    Entity ID: {file.entity_id || 'Not specified'} • 
                    Uploaded: {new Date(file.upload_time).toLocaleDateString()}
                  </p>
                </div>
                <div className="metadata-actions">
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleDownload(file.filename)}
                  >
                    <Download size={14} />
                    Download
                  </button>
                  <button
                    className="btn btn-danger"
                    onClick={() => handleDelete(file.filename)}
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