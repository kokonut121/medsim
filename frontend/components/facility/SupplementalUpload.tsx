"use client";

import { useMemo, useState } from "react";
import { useDropzone } from "react-dropzone";
import * as tus from "tus-js-client";

export function SupplementalUpload({ facilityId }: { facilityId: string }) {
  const [status, setStatus] = useState<string>("Select targeted gap-fill photos to upload.");
  const endpoint = useMemo(
    () => `${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}/api/upload/supplemental`,
    []
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp"] },
    multiple: true,
    maxFiles: 15,
    onDrop: (files) => {
      files.forEach((file) => {
        const upload = new tus.Upload(file, {
          endpoint,
          retryDelays: [0, 1000, 3000],
          metadata: {
            facility_id: facilityId,
            filename: file.name,
            filetype: file.type || "image/jpeg"
          },
          onProgress: (bytesUploaded, bytesTotal) => {
            const percent = Math.round((bytesUploaded / Math.max(bytesTotal, 1)) * 100);
            setStatus(`Uploading ${file.name} (${percent}%)`);
          },
          onSuccess: () => {
            setStatus(`Uploaded ${file.name}. Refresh coverage in a few seconds to see updated gap-fill coverage.`);
          },
          onError: (error) => {
            setStatus(`Upload failed for ${file.name}: ${error.message}`);
          }
        });
        upload.start();
      });
    }
  });

  return (
    <div className="panel">
      <div className="eyebrow">Supplemental Upload</div>
      <div
        className="upload-zone"
        {...getRootProps()}
        style={{ borderColor: isDragActive ? "var(--accent)" : undefined, cursor: "pointer" }}
      >
        <input {...getInputProps()} />
        <div>
          <h3 style={{ marginTop: 0 }}>Gap-fill targeted photo upload</h3>
          <p className="muted">
            The PRD calls for `tus-js-client` plus a dropzone for 5 to 15 targeted uploads in amber zones.
            Drag in a few targeted images for corridors, medication rooms, or trauma-room sightlines that are missing
            from public coverage.
          </p>
          <button className="button" type="button">
            {isDragActive ? "Drop files to upload" : "Select photos"}
          </button>
          <p className="muted" style={{ marginBottom: 0, marginTop: 16 }}>
            {status}
          </p>
        </div>
      </div>
    </div>
  );
}
