'use client';

import React, { useState, useEffect, useRef } from 'react';

interface CandidateProfile {
  name: string;
  email: string;
  phone: string;
  skills: string[];
  experience_years: number;
  summary: string;
  target_roles: string[];
}

interface JobRecommendation {
  job_id: string;
  title: string;
  company: string;
  url: string;
  location: string;
  category: string;
  semantic_score: number;
  ai_score: number;
  reason: string;
  skill_gaps: string[];
  resume_suggestions: string[];
  cover_letter_intro: string;
}

const BACKEND_URL = "http://localhost:8000";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [recommendations, setRecommendations] = useState<JobRecommendation[]>([]);
  const [selectedJob, setSelectedJob] = useState<JobRecommendation | null>(null);
  
  // States for operations
  const [isBackendConnected, setIsBackendConnected] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isMatching, setIsMatching] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [syncMsg, setSyncMsg] = useState("");
  const [copied, setCopied] = useState(false);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Check health on page load and poll
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/api/health`);
        const data = await response.json();
        if (data.status === "healthy") {
          setIsBackendConnected(true);
        } else {
          setIsBackendConnected(false);
        }
      } catch (err) {
        setIsBackendConnected(false);
      }
    };
    
    checkHealth();
    const interval = setInterval(checkHealth, 8000);
    return () => clearInterval(interval);
  }, []);

  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    setErrorMsg("");
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type === "application/pdf") {
        setFile(droppedFile);
        uploadResume(droppedFile);
      } else {
        setErrorMsg("Only PDF resumes are supported.");
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setErrorMsg("");
    if (e.target.files && e.target.files.length > 0) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      uploadResume(selectedFile);
    }
  };

  const triggerFileSelect = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  // Upload API request
  const uploadResume = async (pdfFile: File) => {
    setIsUploading(true);
    setErrorMsg("");
    setProfile(null);
    setRecommendations([]);
    
    const formData = new FormData();
    formData.append("file", pdfFile);
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/upload-resume`, {
        method: "POST",
        body: formData,
      });
      
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to parse resume PDF.");
      }
      
      const data = await response.json();
      setProfile(data);
    } catch (err: any) {
      setErrorMsg(err.message || "Could not parse file. Verify that the backend is running.");
    } finally {
      setIsUploading(false);
    }
  };

  // Fetch jobs API request
  const handleSyncJobs = async () => {
    setIsSyncing(true);
    setSyncMsg("");
    setErrorMsg("");
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/sync-jobs?limit=40`, {
        method: "POST"
      });
      
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to index jobs from feed.");
      }
      
      const data = await response.json();
      setSyncMsg(data.message);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to crawl jobs feed.");
    } finally {
      setIsSyncing(false);
    }
  };

  // Match resume API request
  const handleMatchJobs = async () => {
    if (!profile) return;
    setIsMatching(true);
    setErrorMsg("");
    setRecommendations([]);
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/match-jobs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(profile)
      });
      
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Match request failed.");
      }
      
      const data = await response.json();
      setRecommendations(data.recommendations || []);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to match jobs. Indexing jobs first is required.");
    } finally {
      setIsMatching(false);
    }
  };

  // Copy cover letter intro to clipboard
  const handleCopyText = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <main className="app-container">
      {/* Ambient background glows for glassmorphism layout */}
      <div className="bg-ambient-glow" />
      <div className="bg-ambient-glow-2" />

      {/* Header Dashboard Banner */}
      <header className="app-header">
        <div className="logo-section">
          <h1>RepoMind RAG Matcher</h1>
          <p>Resume Analyzer and Semantic Job Aggregator Matcher</p>
        </div>
        <div className="api-status">
          <span className={`status-indicator ${isBackendConnected ? 'connected' : ''}`} />
          {isBackendConnected ? "Backend Connected" : "Backend Offline"}
        </div>
      </header>

      {/* Error alert wrapper */}
      {errorMsg && (
        <div className="glass-card" style={{ borderColor: 'var(--color-danger)', color: '#fca5a5', padding: '1rem', marginBottom: '2rem' }}>
          <strong>Error:</strong> {errorMsg}
        </div>
      )}

      {/* Dashboard Panels Grid */}
      <div className="grid-cols-2">
        {/* Left Hand side Panel: Upload, Sync and Candidate Profile */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          {/* Step 1: Upload Resume */}
          <section className="glass-card">
            <h2 className="card-title">
              <span style={{ color: 'var(--color-primary)' }}>01</span> Upload Resume
            </h2>
            <div 
              className={`dropzone-container ${isDragOver ? 'drag-over' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={triggerFileSelect}
            >
              <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileChange} 
                accept="application/pdf" 
                style={{ display: 'none' }}
              />
              <div className="dropzone-icon">📄</div>
              <div className="dropzone-text">
                {file ? (
                  <div className="file-selected-badge">
                    <span>File: {file.name}</span>
                  </div>
                ) : (
                  <>Drag & drop resume PDF or <span>Browse files</span></>
                )}
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>PDF formats only</p>
            </div>
            
            {isUploading && (
              <div className="animate-pulse" style={{ marginTop: '1rem', color: 'var(--color-primary)', fontSize: '0.9rem', fontWeight: 500 }}>
                AI parsing resume content... Please hold
              </div>
            )}
          </section>

          {/* Step 2: Index Job listings */}
          <section className="glass-card">
            <h2 className="card-title">
              <span style={{ color: 'var(--color-primary)' }}>02</span> Sync Jobs Directory
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.25rem' }}>
              Index active jobs from the WeWorkRemotely public feed into our local ChromaDB vector store.
            </p>
            <button 
              className="btn btn-secondary" 
              onClick={handleSyncJobs}
              disabled={isSyncing || !isBackendConnected}
            >
              {isSyncing ? "Syncing Feed..." : "Sync Jobs from Feed"}
            </button>
            {syncMsg && (
              <p style={{ color: 'var(--color-success)', fontSize: '0.85rem', fontWeight: 600, marginTop: '0.75rem' }}>
                ✓ {syncMsg}
              </p>
            )}
          </section>

          {/* Step 3: Run RAG Evaluator */}
          {profile && (
            <section className="glass-card animate-fade-in">
              <h2 className="card-title">
                <span style={{ color: 'var(--color-primary)' }}>03</span> Candidate Profile
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div className="profile-detail-item">
                  <div className="profile-detail-label">Name</div>
                  <div className="profile-detail-value">{profile.name}</div>
                </div>
                <div className="profile-detail-item">
                  <div className="profile-detail-label">Contact</div>
                  <div className="profile-detail-value">{profile.email} {profile.phone && `• ${profile.phone}`}</div>
                </div>
                <div className="profile-detail-item">
                  <div className="profile-detail-label">Total Experience</div>
                  <div className="profile-detail-value">{profile.experience_years} Years</div>
                </div>
                <div className="profile-detail-item">
                  <div className="profile-detail-label">Summary</div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{profile.summary}</p>
                </div>
                <div className="profile-detail-item">
                  <div className="profile-detail-label">Skills</div>
                  <div className="badge-container">
                    {profile.skills.map((skill, i) => (
                      <span key={i} className="badge badge-indigo">{skill}</span>
                    ))}
                  </div>
                </div>
                <div className="profile-detail-item">
                  <div className="profile-detail-label">Target Positions</div>
                  <div className="badge-container">
                    {profile.target_roles.map((role, i) => (
                      <span key={i} className="badge">{role}</span>
                    ))}
                  </div>
                </div>
                <button 
                  className="btn btn-primary"
                  style={{ marginTop: '1rem' }}
                  onClick={handleMatchJobs}
                  disabled={isMatching}
                >
                  {isMatching ? "Finding AI Matches..." : "Evaluate Matches Now"}
                </button>
              </div>
            </section>
          )}
        </div>

        {/* Right Hand side Panel: Recommendations List */}
        <div>
          <section className="glass-card" style={{ minHeight: '400px' }}>
            <h2 className="card-title">
              Matched Job Openings 
              {recommendations.length > 0 && (
                <span className="badge badge-indigo" style={{ fontSize: '0.8rem' }}>{recommendations.length} Roles Found</span>
              )}
            </h2>
            
            {isMatching && (
              <div className="flex-center" style={{ flexDirection: 'column', height: '300px', gap: '1rem' }}>
                <div className="animate-pulse" style={{ fontSize: '2.5rem' }}>🔍</div>
                <div className="loading-dots">
                  Scanning vectors & running semantic gap analysis<span>.</span><span>.</span><span>.</span>
                </div>
              </div>
            )}

            {!isMatching && recommendations.length === 0 && (
              <div className="flex-center" style={{ flexDirection: 'column', height: '300px', gap: '1rem', color: 'var(--text-muted)', textAlign: 'center' }}>
                <span style={{ fontSize: '2.5rem' }}>🎯</span>
                <p>Upload a resume and sync the jobs directory to find compatible matches.</p>
              </div>
            )}

            {!isMatching && recommendations.length > 0 && (
              <div className="jobs-list">
                {recommendations.map((job) => {
                  let pillClass = "match-low";
                  if (job.ai_score >= 80) pillClass = "match-high";
                  else if (job.ai_score >= 50) pillClass = "match-med";

                  return (
                    <div 
                      key={job.job_id} 
                      className="job-card"
                      onClick={() => setSelectedJob(job)}
                    >
                      <div className="job-header">
                        <div className="job-info">
                          <h3>{job.title}</h3>
                          <p className="company">{job.company}</p>
                        </div>
                        <div className={`match-pill ${pillClass}`}>
                          {job.ai_score}% Match
                        </div>
                      </div>
                      <div className="job-meta">
                        <span>📍 {job.location}</span>
                        <span>🏷️ {job.category}</span>
                        <span>⚡ Vector: {job.semantic_score}%</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>

      {/* Drawer Overlay for Match Details */}
      {selectedJob && (
        <div className="drawer-backdrop" onClick={() => setSelectedJob(null)}>
          <div className="drawer-content" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 800 }}>{selectedJob.title}</h2>
                <p style={{ color: 'var(--color-primary)', fontWeight: 600 }}>{selectedJob.company}</p>
              </div>
              <button className="drawer-close" onClick={() => setSelectedJob(null)}>×</button>
            </div>

            <div>
              <div className="drawer-section-title">📊 Match Rating</div>
              <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
                <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--color-primary)' }}>
                  {selectedJob.ai_score}%
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                  Based on skills alignment, required seniority, and experience relevance.
                </div>
              </div>
            </div>

            <div>
              <div className="drawer-section-title">💡 Why you match</div>
              <p className="text-block">{selectedJob.reason}</p>
            </div>

            <div>
              <div className="drawer-section-title">⚠️ Identified Skill Gaps</div>
              {selectedJob.skill_gaps.length > 0 ? (
                <div className="badge-container">
                  {selectedJob.skill_gaps.map((skill, idx) => (
                    <span key={idx} className="badge badge-danger">{skill}</span>
                  ))}
                </div>
              ) : (
                <p style={{ color: 'var(--color-success)', fontSize: '0.9rem', fontWeight: 500 }}>✓ No critical skill gaps identified!</p>
              )}
            </div>

            <div>
              <div className="drawer-section-title">✍️ Tailoring Suggestions</div>
              <ul className="suggestion-list">
                {selectedJob.resume_suggestions.map((sug, idx) => (
                  <li key={idx}>{sug}</li>
                ))}
              </ul>
            </div>

            <div>
              <div className="drawer-section-title">✉️ Cover Letter Opening Hook</div>
              <div className="copy-box">
                <button className="copy-btn" onClick={() => handleCopyText(selectedJob.cover_letter_intro)}>
                  {copied ? "Copied!" : "Copy"}
                </button>
                {selectedJob.cover_letter_intro}
              </div>
            </div>

            <div style={{ marginTop: 'auto', paddingTop: '1.5rem', borderTop: '1px solid var(--border-color)' }}>
              <a 
                href={selectedJob.url} 
                target="_blank" 
                rel="noreferrer"
                className="btn btn-primary"
                style={{ textDecoration: 'none' }}
              >
                Apply to Opening ↗
              </a>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
