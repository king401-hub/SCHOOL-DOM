import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { requestJson } from "../AppShared";

const ADMIN_ROLES = new Set(["school_admin", "principal", "super_admin"]);
const ATTENDANCE_ROLES = new Set(["teacher", "staff", "school_admin", "principal", "super_admin"]);

function authHeaders(session, extra = {}) {
  return extra;
}

function userIdParam(session) {
  return session?.user?.id ? `user_id=${encodeURIComponent(session.user.id)}` : "";
}

function withUserId(endpoint, session) {
  const param = userIdParam(session);
  if (!param) return endpoint;
  return `${endpoint}${endpoint.includes("?") ? "&" : "?"}${param}`;
}

function attendanceBody(session, payload = {}) {
  return {
    user_id: session?.user?.id,
    ...payload,
  };
}

async function readJsonResponse(response) {
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(data?.message || data?.detail || `Request failed (${response.status}).`);
  }
  return data ?? {};
}

async function attendanceRequest(session, endpoint, options = {}) {
  const response = await fetch(endpoint, {
    ...options,
    headers: authHeaders(session, {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    }),
  });
  return readJsonResponse(response);
}

function formatDateTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatTime(value, fallback) {
  if (fallback) return fallback;
  if (!value) return "-";
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatCoordinate(value) {
  if (value === null || value === undefined || value === "") return "";
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(6) : String(value);
}

function locationSummary(record, prefix = "check_in") {
  const latitude = record?.[`${prefix}_latitude`];
  const longitude = record?.[`${prefix}_longitude`];
  if (latitude === null || latitude === undefined || longitude === null || longitude === undefined) return null;
  const latText = formatCoordinate(latitude);
  const lngText = formatCoordinate(longitude);
  return {
    latitude: latText,
    longitude: lngText,
    address: record?.[`${prefix}_address`] || `${latText}, ${lngText}`,
    accuracy: record?.[`${prefix}_accuracy_meters`],
    mapUrl: `https://www.google.com/maps?q=${encodeURIComponent(`${latText},${lngText}`)}`,
    embedUrl: `https://www.google.com/maps?q=${encodeURIComponent(`${latText},${lngText}`)}&output=embed`,
  };
}

function collectDeviceInfo() {
  const screenSize = window.screen ? `${window.screen.width}x${window.screen.height}` : "unknown-screen";
  return [
    navigator.userAgent,
    `platform=${navigator.platform || "unknown"}`,
    `language=${navigator.language || "unknown"}`,
    `timezone=${Intl.DateTimeFormat().resolvedOptions().timeZone || "unknown"}`,
    `screen=${screenSize}`,
  ].join(" | ");
}

async function reverseGeocode(latitude, longitude) {
  // Address is cosmetic only (shown for audit purposes) — kept short so it never
  // holds up attendance submission. The GPS coordinates are what's actually recorded.
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 1800);
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${encodeURIComponent(latitude)}&lon=${encodeURIComponent(longitude)}`,
      { signal: controller.signal, headers: { Accept: "application/json" } }
    );
    if (!response.ok) return "";
    const data = await response.json().catch(() => null);
    return data?.display_name || "";
  } catch (_error) {
    return "";
  } finally {
    window.clearTimeout(timer);
  }
}

function requestBrowserPosition() {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new Error("This device does not support browser location services."));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 10000,
      // Reuse a GPS fix from the last 20s (e.g. a retry, or clock-in immediately
      // followed by clock-out) instead of forcing the device to re-acquire a fix.
      maximumAge: 20000,
    });
  });
}

async function getAttendanceLocationPayload() {
  let position;
  try {
    position = await requestBrowserPosition();
  } catch (locationError) {
    if (locationError?.code === 1) {
      throw new Error("Location permission was denied. Enable location access before marking attendance.");
    }
    if (locationError?.code === 2) {
      throw new Error("Location is unavailable. Turn on GPS/location services before marking attendance.");
    }
    if (locationError?.code === 3) {
      throw new Error("Location request timed out. Move to an open area and try again.");
    }
    throw new Error(locationError?.message || "Enable location services before marking attendance.");
  }

  const { latitude, longitude, accuracy } = position.coords;
  const address = await reverseGeocode(latitude, longitude);
  return {
    latitude,
    longitude,
    accuracy,
    address: address || `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`,
    device_info: collectDeviceInfo(),
  };
}

function statusLabel(status) {
  if (!status) return "Present";
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function roleLabel(role) {
  if (!role) return "Staff";
  return role
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function AttendanceStatusPill({ status = "present" }) {
  const isPresent = status === "present" || status === "checked_in" || status === "checked_out";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        borderRadius: "999px",
        padding: "4px 10px",
        fontSize: "0.82rem",
        fontWeight: 700,
        background: isPresent ? "#dcfce7" : "#fef3c7",
        color: isPresent ? "#166534" : "#92400e",
      }}
    >
      {statusLabel(status)}
    </span>
  );
}

function QrScannerPanel({
  title,
  subtitle,
  tokenLabel = "QR token fallback",
  placeholder = "Paste scanned QR token or URL",
  submitLabel = "Submit scan",
  scanningLabel = "Point the camera at the QR code.",
  onScan,
  disabled = false,
  requireLocation = true,
  statusPill = null,
}) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const frameRef = useRef(null);
  const scanningRef = useRef(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [manualToken, setManualToken] = useState("");
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const stopCamera = useCallback(() => {
    scanningRef.current = false;
    if (frameRef.current) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  }, []);

  useEffect(() => stopCamera, [stopCamera]);

  const submitToken = useCallback(
    async (rawToken) => {
      const token = String(rawToken || "").trim();
      if (!token) {
        setError("Scan or paste a valid QR code.");
        return;
      }
      setSubmitting(true);
      setError("");
      setFeedback(requireLocation ? "Requesting location..." : "Saving scan...");
      try {
        const location = requireLocation ? await getAttendanceLocationPayload() : null;
        setFeedback("Saving scan...");
        const result = await onScan(token, location);
        setFeedback(result?.message || "Scan saved successfully.");
        setManualToken("");
        stopCamera();
      } catch (scanError) {
        setFeedback("");
        setError(scanError.message || "Could not complete scan.");
      } finally {
        setSubmitting(false);
      }
    },
    [onScan, requireLocation, stopCamera]
  );

  const startCamera = async () => {
    setError("");
    setFeedback("");
    if (!("BarcodeDetector" in window)) {
      setError("This browser cannot scan QR codes directly. Paste the QR token or URL below instead.");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Camera access is not available on this device.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraActive(true);
      setFeedback(scanningLabel);
      scanningRef.current = true;
      const detector = new window.BarcodeDetector({ formats: ["qr_code"] });

      const scanFrame = async () => {
        if (!scanningRef.current || !videoRef.current || submitting) return;
        try {
          const codes = await detector.detect(videoRef.current);
          const value = codes?.[0]?.rawValue;
          if (value) {
            await submitToken(value);
            return;
          }
        } catch {
          setError("The camera could not read the QR code. Try better light or paste the token below.");
        }
        frameRef.current = requestAnimationFrame(scanFrame);
      };
      frameRef.current = requestAnimationFrame(scanFrame);
    } catch (cameraError) {
      setError(cameraError?.message || "Allow camera access to scan the QR code.");
      stopCamera();
    }
  };

  return (
    <section className="qr-scanner-panel">
      <div className="student-panel-head">
        <div>
          <h3>{title}</h3>
          {subtitle ? <p className="student-panel-sub">{subtitle}</p> : null}
        </div>
        {statusPill}
      </div>
      <div className="qr-scanner-grid">
        <div className="qr-camera-card">
          <video ref={videoRef} muted playsInline className={cameraActive ? "is-active" : ""} />
          {!cameraActive ? <span>Camera preview appears here.</span> : null}
        </div>
        <div className="qr-scanner-copy">
          <strong>{cameraActive ? "Scanning..." : "Ready to scan"}</strong>
          <p>{scanningLabel}</p>
          <div className="panel-form-actions">
            <button type="button" onClick={startCamera} disabled={disabled || submitting || cameraActive}>
              {cameraActive ? "Scanning..." : "Start scanner"}
            </button>
            {cameraActive ? (
              <button type="button" className="table-action" onClick={stopCamera} disabled={submitting}>
                Stop camera
              </button>
            ) : null}
          </div>
        </div>
      </div>
      <label className="panel-field">
        <span>{tokenLabel}</span>
        <input
          type="text"
          value={manualToken}
          onChange={(event) => setManualToken(event.target.value)}
          placeholder={placeholder}
          disabled={disabled || submitting}
        />
      </label>
      <div className="panel-form-actions">
        <button type="button" className="table-action" onClick={() => submitToken(manualToken)} disabled={disabled || submitting}>
          {submitting ? "Saving..." : submitLabel}
        </button>
      </div>
      {feedback ? <p className="form-feedback success">{feedback}</p> : null}
      {error ? <p className="form-feedback error">{error}</p> : null}
    </section>
  );
}

export function StudentQrAttendanceScanner({ session, onRefresh, attendanceToday }) {
  const handleScan = useCallback(
    async (token, location) => {
      const result = await requestJson(session, "POST", "/api/app/attendance/student-qr-mark/", {
        token,
        location,
      });
      await onRefresh?.();
      return result;
    },
    [onRefresh, session]
  );

  return (
    <article className="student-panel">
      <QrScannerPanel
        title="QR Attendance"
        subtitle="Scan the school attendance QR code to mark today's attendance."
        tokenLabel="QR token fallback"
        submitLabel="Mark attendance"
        scanningLabel="Point the camera at the school attendance QR code."
        onScan={handleScan}
        requireLocation={false}
        statusPill={
          <span className={`student-status-pill status-${attendanceToday?.status || "unmarked"}`}>
            {attendanceToday ? `Marked ${attendanceToday.status}` : "Not marked"}
          </span>
        }
      />
    </article>
  );
}

export function IdCardAttendanceScanner({ session, onMarked, title = "Scan Student ID Card", subtitle = "Scan the QR code on the back of a student's ID card to verify it and mark attendance." }) {
  const handleScan = useCallback(
    async (token, location) => {
      const payload = { token };
      if (location) {
        payload.location = location;
      }
      const result = await requestJson(session, "POST", "/api/app/id-cards/scan-attendance/", payload);
      await onMarked?.(result);
      return result;
    },
    [onMarked, session]
  );

  return (
    <article className="app-panel">
      <QrScannerPanel
        title={title}
        subtitle={subtitle}
        tokenLabel="ID card QR fallback"
        placeholder="Paste student ID card QR URL or token"
        submitLabel="Verify & mark present"
        scanningLabel="Point the camera at the QR code on the back of the student ID card."
        requireLocation={false}
        onScan={handleScan}
      />
    </article>
  );
}

export function QRCodeManagement({ session }) {
  const nonK12 = (session?.school?.school_type || session?.school?.schoolType || "k12") === "non_k12";
  const audienceLabel = nonK12 ? "Student" : "Staff";
  const [qrCode, setQrCode] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const loadPreview = useCallback(async () => {
    const response = await fetch(withUserId("/api/attendance/qr-code/download/", session));
    if (!response.ok) return "";
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  }, [session]);

  const loadQRCode = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await attendanceRequest(null, withUserId("/api/attendance/qr-code/get/", session));
      setQrCode(result.data);
      const nextPreview = await loadPreview();
      setPreviewUrl((previous) => {
        if (previous) URL.revokeObjectURL(previous);
        return nextPreview;
      });
    } catch (requestError) {
      if (!requestError.message.toLowerCase().includes("not found")) {
        setError(requestError.message);
      }
      setQrCode(null);
      setPreviewUrl((previous) => {
        if (previous) URL.revokeObjectURL(previous);
        return "";
      });
    } finally {
      setLoading(false);
    }
  }, [loadPreview, session]);

  useEffect(() => {
    loadQRCode();
    return () => {
      setPreviewUrl((previous) => {
        if (previous) URL.revokeObjectURL(previous);
        return "";
      });
    };
  }, [loadQRCode]);

  const createQRCode = async () => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await attendanceRequest(null, "/api/attendance/qr-code/generate/", {
        method: "POST",
        body: JSON.stringify(attendanceBody(session)),
      });
      setQrCode(result.data);
      const nextPreview = await loadPreview();
      setPreviewUrl((previous) => {
        if (previous) URL.revokeObjectURL(previous);
        return nextPreview;
      });
      setMessage(`${audienceLabel} attendance QR code is ready.`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const downloadQRCode = async () => {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(withUserId("/api/attendance/qr-code/download/", session));
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.message || "Download failed.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = nonK12 ? "student_attendance_qr.png" : "staff_attendance_qr.png";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="app-panel">
      <h3>{audienceLabel} QR Code</h3>
      <p className="panel-empty">
        {nonK12
          ? "A single static QR code belongs to students and is scanned from the student attendance page."
          : "A single static QR code is shared by teachers and admins and opens the attendance confirmation page."}
      </p>

      {!session?.user?.id ? (
        <p className="form-feedback error">User account missing. Please sign in again.</p>
      ) : null}

      {loading ? <p className="panel-empty">Loading QR code...</p> : null}
      {error ? <p className="form-feedback error">{error}</p> : null}
      {message ? <p className="form-feedback success">{message}</p> : null}

      {!loading && !qrCode ? (
        <div className="panel-form-actions">
          <button type="button" onClick={createQRCode} disabled={busy || !session?.user?.id}>
            {busy ? "Creating..." : nonK12 ? "Create Student QR Code" : "Create Staff QR Code"}
          </button>
        </div>
      ) : null}

      {qrCode ? (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(220px, 320px) 1fr", gap: 24, alignItems: "start" }}>
          <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 18, textAlign: "center" }}>
            {previewUrl ? (
              <img src={previewUrl} alt={`${audienceLabel} attendance QR code`} style={{ width: "100%", maxWidth: 280, aspectRatio: "1 / 1" }} />
            ) : (
              <p style={{ color: "#111827" }}>QR preview unavailable</p>
            )}
          </div>

          <div>
            <div className="metric-card" style={{ marginBottom: 14 }}>
              <p className="metric-label">{nonK12 ? "Student QR Status" : `${audienceLabel}s Checked In Today`}</p>
              <p className="metric-value">{nonK12 ? (qrCode.is_active ? "Ready" : "Off") : (qrCode.today_attendance_count || 0)}</p>
              <p className="metric-trend">{nonK12 ? "Students scan this QR from their Attendance page" : (qrCode.is_active ? "QR active" : "QR inactive")}</p>
            </div>

            <div className="panel-form-actions" style={{ justifyContent: "flex-start" }}>
              <button type="button" onClick={downloadQRCode} disabled={busy || !session?.user?.id}>
                Download PNG
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </article>
  );
}

export function AttendanceDashboard({ session }) {
  const nonK12 = (session?.school?.school_type || session?.school?.schoolType || "k12") === "non_k12";
  const audienceLabel = nonK12 ? "Student" : "Staff";
  const [records, setRecords] = useState([]);
  const [summary, setSummary] = useState({ date: "", total_present: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [mapLocation, setMapLocation] = useState(null);

  const loadToday = useCallback(async () => {
    setError("");
    try {
      const result = await attendanceRequest(null, withUserId("/api/attendance/today/", session));
      setRecords(result.data || []);
      setSummary({ date: result.date, total_present: result.total_present || 0 });
      setMapLocation((current) => {
        if (!current) return current;
        const stillExists = (result.data || []).some((record) => record.id === current.recordId);
        return stillExists ? current : null;
      });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    loadToday();
  }, [loadToday]);

  useEffect(() => {
    if (!autoRefresh) return undefined;
    const intervalId = window.setInterval(loadToday, 15000);
    return () => window.clearInterval(intervalId);
  }, [autoRefresh, loadToday]);

  return (
    <article className="app-panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h3>Today&apos;s {audienceLabel} Attendance</h3>
          <p className="panel-empty" style={{ margin: 0 }}>
            {summary.date || new Date().toISOString().slice(0, 10)} - {summary.total_present} checked in
          </p>
        </div>
        <div className="panel-form-actions" style={{ margin: 0 }}>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontWeight: 700 }}>
            <input type="checkbox" checked={autoRefresh} onChange={(event) => setAutoRefresh(event.target.checked)} />
            Live refresh
          </label>
          <button type="button" onClick={loadToday} disabled={loading}>
            Refresh
          </button>
        </div>
      </div>

      {error ? <p className="form-feedback error">{error}</p> : null}

      {loading ? (
        <p className="panel-empty">Loading attendance records...</p>
      ) : records.length === 0 ? (
        <p className="panel-empty" style={{ padding: "28px 0" }}>
          No staff member has clocked in today.
        </p>
      ) : (
        <div style={{ overflowX: "auto", marginTop: 18 }}>
          <table className="student-table" style={{ width: "100%" }}>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Check-in Time</th>
                <th>Check-out Time</th>
                <th>Status</th>
                <th>Location</th>
                <th>Device</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => {
                const checkInLocation = locationSummary(record, "check_in");
                return (
                  <tr key={record.id}>
                    <td>{record.teacher_name || "Unknown staff member"}</td>
                    <td>{record.teacher_email || "-"}</td>
                    <td>{roleLabel(record.teacher_role)}</td>
                    <td>{formatTime(record.check_in_time, record.check_in_time_formatted)}</td>
                    <td>{formatTime(record.check_out_time, record.check_out_time_formatted)}</td>
                    <td>
                      <AttendanceStatusPill status={record.check_out_time ? "checked_out" : record.status} />
                    </td>
                    <td>
                      {checkInLocation ? (
                        <button
                          type="button"
                          className="link-button"
                          onClick={() => setMapLocation({ ...checkInLocation, recordId: record.id, teacher: record.teacher_name || "Staff member" })}
                        >
                          View map
                        </button>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td title={record.client_device_info || record.device_info || ""}>
                      {(record.client_device_info || record.device_info) ? `${(record.client_device_info || record.device_info).slice(0, 42)}...` : "-"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {mapLocation ? (
            <div className="attendance-map-panel">
              <div>
                <h4>{mapLocation.teacher}</h4>
                <p>{mapLocation.address}</p>
                <small>
                  {mapLocation.latitude}, {mapLocation.longitude}
                  {mapLocation.accuracy ? ` - +/-${Math.round(Number(mapLocation.accuracy))}m` : ""}
                </small>
                <a href={mapLocation.mapUrl} target="_blank" rel="noreferrer">Open in Google Maps</a>
              </div>
              <iframe title="Attendance location map" src={mapLocation.embedUrl} loading="lazy" />
            </div>
          ) : null}
        </div>
      )}
    </article>
  );
}

export function StudentAttendanceDashboard({ session }) {
  const [records, setRecords] = useState([]);
  const [summary, setSummary] = useState({ date: "", total_present: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [mapLocation, setMapLocation] = useState(null);

  const loadToday = useCallback(async () => {
    setError("");
    try {
      const result = await requestJson(session, "GET", "/api/app/attendance/students/");
      setRecords(result.records || []);
      setSummary({ date: result.date, total_present: result.total_present || 0 });
      setMapLocation((current) => {
        if (!current) return current;
        const stillExists = (result.records || []).some((record) => record.id === current.recordId);
        return stillExists ? current : null;
      });
    } catch (requestError) {
      setError(requestError.message || "Could not load student attendance.");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    loadToday();
  }, [loadToday]);

  useEffect(() => {
    if (!autoRefresh) return undefined;
    const intervalId = window.setInterval(loadToday, 15000);
    return () => window.clearInterval(intervalId);
  }, [autoRefresh, loadToday]);

  return (
    <article className="app-panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h3>Today&apos;s Student Attendance</h3>
          <p className="panel-empty" style={{ margin: 0 }}>
            {summary.date || new Date().toISOString().slice(0, 10)} - {summary.total_present} marked present
          </p>
        </div>
        <div className="panel-form-actions" style={{ margin: 0 }}>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontWeight: 700 }}>
            <input type="checkbox" checked={autoRefresh} onChange={(event) => setAutoRefresh(event.target.checked)} />
            Live refresh
          </label>
          <button type="button" onClick={loadToday} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {error ? <p className="form-feedback error">{error}</p> : null}

      {loading ? (
        <p className="panel-empty">Loading student attendance records...</p>
      ) : records.length === 0 ? (
        <p className="panel-empty" style={{ padding: "28px 0" }}>
          No student has marked attendance today.
        </p>
      ) : (
        <div style={{ overflowX: "auto", marginTop: 18 }}>
          <table className="student-table" style={{ width: "100%" }}>
            <thead>
              <tr>
                <th>Student</th>
                <th>Email</th>
                <th>Class</th>
                <th>Status</th>
                <th>Marked</th>
                <th>Location</th>
                <th>Device</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => {
                const hasLocation = record.latitude !== null && record.latitude !== undefined && record.longitude !== null && record.longitude !== undefined;
                const location = hasLocation
                  ? {
                      recordId: record.id,
                      teacher: record.student_name || "Student",
                      latitude: formatCoordinate(record.latitude),
                      longitude: formatCoordinate(record.longitude),
                      address: record.address || `${record.latitude}, ${record.longitude}`,
                      accuracy: record.accuracy,
                      embedUrl: `https://www.google.com/maps?q=${encodeURIComponent(`${record.latitude},${record.longitude}`)}&output=embed`,
                      mapUrl: `https://www.google.com/maps?q=${encodeURIComponent(`${record.latitude},${record.longitude}`)}`,
                    }
                  : null;
                return (
                  <tr key={record.id}>
                    <td>{record.student_name || "Unknown student"}<small>{record.student_code || ""}</small></td>
                    <td>{record.student_email || "-"}</td>
                    <td>{record.class_name || "-"}</td>
                    <td><AttendanceStatusPill status={record.status} /></td>
                    <td>{formatDateTime(record.updated_at || record.created_at)}</td>
                    <td>
                      {location ? (
                        <button type="button" className="link-button" onClick={() => setMapLocation(location)}>
                          View map
                        </button>
                      ) : "-"}
                    </td>
                    <td><small>{record.device_info || "-"}</small></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {mapLocation ? (
        <div className="modal-backdrop" onClick={() => setMapLocation(null)}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()} style={{ maxWidth: 780 }}>
            <div className="modal-head">
              <div>
                <h3>{mapLocation.teacher} location</h3>
                <p>{mapLocation.address}</p>
                {mapLocation.accuracy ? <small>Accuracy: {mapLocation.accuracy}m</small> : null}
              </div>
              <button type="button" className="table-action" onClick={() => setMapLocation(null)}>Close</button>
            </div>
            <iframe title="Student attendance location" src={mapLocation.embedUrl} style={{ width: "100%", height: 360, border: 0, borderRadius: 8 }} loading="lazy" />
            <div className="panel-form-actions" style={{ justifyContent: "flex-start" }}>
              <a className="table-action" href={mapLocation.mapUrl} target="_blank" rel="noreferrer">Open in Google Maps</a>
            </div>
          </div>
        </div>
      ) : null}
    </article>
  );
}

export function TeacherQRCodeAttendancePage({ session, token, onNavigate }) {
  const [qrDetails, setQrDetails] = useState(null);
  const [statusDetails, setStatusDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [locationStatus, setLocationStatus] = useState("");

  const nonK12 = (session?.school?.school_type || session?.school?.schoolType || "k12") === "non_k12";
  // Non-K12 schools don't use staff QR clock-in at all — students mark their
  // own attendance instead (see StudentQrAttendanceScanner).
  const canUseAttendance = nonK12 ? false : ATTENDANCE_ROLES.has(session?.user?.role);

  const loadPage = useCallback(async () => {
    if (!token) {
      setError("Missing QR code.");
      setLoading(false);
      return;
    }

    setError("");
    setLoading(true);
    try {
      const [scanResult, statusResult] = await Promise.all([
        attendanceRequest(null, `/api/attendance/scan/${encodeURIComponent(token)}/`),
        canUseAttendance ? attendanceRequest(null, withUserId("/api/attendance/check-status/", session)) : Promise.resolve(null),
      ]);
      setQrDetails(scanResult);
      setStatusDetails(statusResult);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [canUseAttendance, session, token]);

  useEffect(() => {
    loadPage();
  }, [loadPage]);

  const markAttendance = async () => {
    setSubmitting(true);
    setError("");
    setMessage("");
    setLocationStatus("Requesting GPS location...");
    try {
      const location = await getAttendanceLocationPayload();
      setLocationStatus("Location captured. Recording attendance...");
      const result = await attendanceRequest(null, `/api/attendance/scan/${encodeURIComponent(token)}/`, {
        method: "POST",
        body: JSON.stringify(attendanceBody(session, { location })),
      });
      setStatusDetails(result);
      setMessage(result.message || "Attendance marked successfully.");
      setLocationStatus("");
    } catch (requestError) {
      setError(requestError.message);
      await loadPage();
    } finally {
      setSubmitting(false);
    }
  };

  const clockOut = async () => {
    setSubmitting(true);
    setError("");
    setMessage("");
    setLocationStatus("Requesting GPS location...");
    try {
      const location = await getAttendanceLocationPayload();
      setLocationStatus("Location captured. Recording clock-out...");
      const result = await attendanceRequest(null, "/api/attendance/clock-out/", {
        method: "POST",
        body: JSON.stringify(attendanceBody(session, { location })),
      });
      setStatusDetails(result);
      setMessage(result.message || "Clock-out recorded.");
      setLocationStatus("");
    } catch (requestError) {
      setError(requestError.message);
      await loadPage();
    } finally {
      setSubmitting(false);
    }
  };

  if (!canUseAttendance) {
    return (
      <main className="signup-page dashboard-page">
        <section className="dashboard-shell">
          <article className="app-panel state-panel">
            <h3>{nonK12 ? "Not Used at Your School" : "Staff Attendance Only"}</h3>
            <p>{nonK12 ? "Non-K12 schools don't use staff QR clock-in — students mark their own attendance instead." : "This QR code can only be used by authenticated staff, teacher, or admin accounts."}</p>
            <div className="panel-form-actions">
              <button type="button" onClick={() => onNavigate?.("/dashboard")}>
                Back to Dashboard
              </button>
            </div>
          </article>
        </section>
      </main>
    );
  }

  const checkedIn = Boolean(statusDetails?.checked_in);
  const checkedOut = Boolean(statusDetails?.checked_out || statusDetails?.data?.check_out_time);
  const checkInData = statusDetails?.data;
  const checkInLocation = locationSummary(checkInData, "check_in");
  const checkOutLocation = locationSummary(checkInData, "check_out");

  return (
    <main className="signup-page dashboard-page">
      <section className="dashboard-shell">
        <header className="dashboard-header">
          <div>
            <p className="topbar-kicker">SchoolDom Attendance</p>
            <h1>Staff Check-in</h1>
            <p>{session?.user?.full_name || session?.user?.email}</p>
          </div>
          <div className="dashboard-actions">
            <button type="button" onClick={() => onNavigate?.("/dashboard")}>
              Dashboard
            </button>
          </div>
        </header>

        <article className="app-panel">
          <h3>Confirm Today&apos;s Attendance</h3>
          {loading ? <p className="panel-empty">Verifying QR code...</p> : null}
          {error ? <p className="form-feedback error">{error}</p> : null}
          {message ? <p className="form-feedback success">{message}</p> : null}
          {locationStatus ? <p className="panel-empty">{locationStatus}</p> : null}

          {qrDetails && !loading ? (
            <div className="panel-list">
              <strong>School</strong>
              <p>{qrDetails.tenant_name || "Your school"}</p>
              <strong>Date</strong>
              <p>{new Date().toLocaleDateString()}</p>
            </div>
          ) : null}

          {checkedIn ? (
            <div style={{ marginTop: 18, padding: 18, borderRadius: 8, background: "#dcfce7", color: "#166534" }}>
              <h3 style={{ color: "#166534", marginTop: 0 }}>{checkedOut ? "Attendance completed" : "Clock-in recorded"}</h3>
              <p>
                Check-in time: <strong>{formatTime(checkInData?.check_in_time, checkInData?.check_in_time_formatted)}</strong>
              </p>
              <p style={{ marginBottom: 0 }}>
                Check-out time: <strong>{formatTime(checkInData?.check_out_time, checkInData?.check_out_time_formatted)}</strong>
              </p>
              {checkInLocation ? (
                <p style={{ marginBottom: 0 }}>
                  Check-in location: <strong>{checkInLocation.address}</strong>
                </p>
              ) : null}
              {checkOutLocation ? (
                <p style={{ marginBottom: 0 }}>
                  Check-out location: <strong>{checkOutLocation.address}</strong>
                </p>
              ) : null}
            </div>
          ) : (
            <div className="panel-form-actions" style={{ justifyContent: "flex-start" }}>
              <button type="button" onClick={markAttendance} disabled={loading || submitting || !qrDetails}>
                {submitting ? "Recording..." : "Clock In"}
              </button>
            </div>
          )}

          {checkedIn && !checkedOut ? (
            <div className="panel-form-actions" style={{ justifyContent: "flex-start" }}>
              <button type="button" onClick={clockOut} disabled={loading || submitting || !qrDetails}>
                {submitting ? "Recording..." : "Clock Out"}
              </button>
            </div>
          ) : null}
        </article>
      </section>
    </main>
  );
}

export function AttendanceModule({ session }) {
  const isAdmin = ADMIN_ROLES.has(session?.user?.role);
  const nonK12 = (session?.school?.school_type || session?.school?.schoolType || "k12") === "non_k12";
  const audienceLabel = nonK12 ? "Student" : "Staff";
  const [activeTab, setActiveTab] = useState(nonK12 ? "qr" : "dashboard");

  const tabs = useMemo(
    () =>
      nonK12
        ? [
            { id: "qr", label: "Student QR", render: () => <QRCodeManagement session={session} /> },
            { id: "scan", label: "Scan ID Card", render: () => <IdCardAttendanceScanner session={session} /> },
            { id: "students", label: "Student List", render: () => <StudentAttendanceDashboard session={session} /> },
          ]
        : [
            { id: "dashboard", label: "Today", render: () => <AttendanceDashboard session={session} /> },
            { id: "qr", label: "QR Code", render: () => <QRCodeManagement session={session} /> },
            { id: "scan", label: "Scan ID Card", render: () => <IdCardAttendanceScanner session={session} /> },
          ],
    [nonK12, session]
  );

  useEffect(() => {
    if (nonK12 && activeTab === "dashboard") {
      setActiveTab("qr");
    }
  }, [activeTab, nonK12]);

  if (!isAdmin) {
    return (
      <article className="app-panel state-panel">
        <h3>Admin Access Required</h3>
        <p>Only school admins, principals, and super admins can manage attendance QR codes.</p>
      </article>
    );
  }

  const active = tabs.find((tab) => tab.id === activeTab) || tabs[0];

  return (
    <section className="screen-grid">
      <div className="screen-hero">
        <h2>{audienceLabel} Attendance</h2>
        <p>
          {nonK12
            ? "Manage the shared student QR code. Students scan it from their own Attendance page."
            : `Manage the shared QR code and monitor today's ${audienceLabel.toLowerCase()} check-ins in real time.`}
        </p>
      </div>
      <div className="segmented-control" style={{ justifyContent: "flex-start" }}>
        {tabs.map((tab) => (
          <button key={tab.id} type="button" className={activeTab === tab.id ? "active" : ""} onClick={() => setActiveTab(tab.id)}>
            {tab.label}
          </button>
        ))}
      </div>
      {active.render()}
    </section>
  );
}
