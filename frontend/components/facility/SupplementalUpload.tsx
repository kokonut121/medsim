"use client";

export function SupplementalUpload() {
  return (
    <div className="panel">
      <div className="eyebrow">Supplemental Upload</div>
      <div className="upload-zone">
        <div>
          <h3 style={{ marginTop: 0 }}>Gap-fill targeted photo upload</h3>
          <p className="muted">
            The PRD calls for `tus-js-client` plus a dropzone for 5 to 15 targeted uploads in amber zones.
            This UI is staged for that resumable workflow.
          </p>
          <button className="button">Select photos</button>
        </div>
      </div>
    </div>
  );
}

