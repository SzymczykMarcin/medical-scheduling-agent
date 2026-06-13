import {
  CheckCircle2,
  Clock3,
  Mic,
  PlayCircle,
  RefreshCw,
  RotateCcw,
  Send,
  Square,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { createAppointmentFromAudio } from "../api/client";
import type { AppointmentResponse } from "../types/api";

type WindowWithWebkitAudioContext = Window &
  typeof globalThis & {
    webkitAudioContext?: typeof AudioContext;
  };

const LAST_APPOINTMENT_RESPONSE_KEY = "medicalSchedulingAgent:lastAppointmentResponse";

export function RecorderPage() {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const initialDeviceProbeRef = useRef(false);
  const waveformBars = Array.from({ length: 36 }, (_, index) => index);

  const [recording, setRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioLevel, setAudioLevel] = useState(0);
  const [audioDevices, setAudioDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const [deviceStatus, setDeviceStatus] = useState("Sprawdzam dostęp do mikrofonu...");
  const [appointmentResponse, setAppointmentResponse] = useState<AppointmentResponse | null>(() =>
    readStoredAppointmentResponse(),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeAudioInput = recording && audioLevel > 0.035;
  const audioUrl = useMemo(() => (audioBlob ? URL.createObjectURL(audioBlob) : null), [audioBlob]);

  const refreshAudioDevices = useCallback(
    async ({ requestPermission }: { requestPermission: boolean }) => {
      if (!navigator.mediaDevices?.enumerateDevices) {
        setDeviceStatus("Ta przeglądarka nie obsługuje wyboru mikrofonu.");
        return;
      }

      setError(null);

      try {
        if (requestPermission) {
          await ensureMicrophonePermission();
        }

        const devices = await navigator.mediaDevices.enumerateDevices();
        const microphones = devices.filter((device) => device.kind === "audioinput");
        setAudioDevices(microphones);

        setSelectedDeviceId((currentDeviceId) => {
          if (microphones.length === 0) {
            return "";
          }

          const stillAvailable = microphones.some((device) => device.deviceId === currentDeviceId);
          return stillAvailable ? currentDeviceId : microphones[0].deviceId;
        });

        setDeviceStatus(getDeviceStatusMessage(microphones));
      } catch (devicesError) {
        const message = getRecordingErrorMessage(devicesError);
        setDeviceStatus(message);
        setError(message);
      }
    },
    [],
  );

  useEffect(() => {
    if (!initialDeviceProbeRef.current) {
      initialDeviceProbeRef.current = true;
      void refreshAudioDevices({ requestPermission: true });
    }

    const handleDeviceChange = () => {
      void refreshAudioDevices({ requestPermission: false });
    };

    navigator.mediaDevices?.addEventListener("devicechange", handleDeviceChange);
    return () => {
      navigator.mediaDevices?.removeEventListener("devicechange", handleDeviceChange);
      stopAudioPreview();
    };
  }, [refreshAudioDevices]);

  useEffect(() => {
    return () => {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [audioUrl]);

  async function startRecording() {
    setError(null);
    setAppointmentResponse(null);
    setAudioBlob(null);
    setAudioLevel(0);

    try {
      await ensureMicrophonePermission();
      const stream = await openSelectedMicrophone(selectedDeviceId);
      await refreshAudioDevices({ requestPermission: false });
      syncSelectedDeviceFromStream(stream);

      const mimeType = getSupportedAudioMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType || "audio/webm" });
        if (blob.size > 0) {
          setAudioBlob(blob);
        } else {
          setError("Nagranie jest puste. Sprawdź wybrany mikrofon i spróbuj ponownie.");
        }
        stream.getTracks().forEach((track) => track.stop());
        stopAudioPreview();
      };

      startAudioPreview(stream);
      recorder.start(250);
      mediaRecorderRef.current = recorder;
      setRecording(true);
    } catch (recordingError) {
      setError(getRecordingErrorMessage(recordingError));
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
    setAudioLevel(0);
  }

  async function submitRecording() {
    if (!audioBlob) {
      return;
    }

    setSubmitting(true);
    setError(null);
    setAppointmentResponse(null);
    clearStoredAppointmentResponse();

    try {
      const response = await createAppointmentFromAudio(audioBlob);
      setAppointmentResponse(response);
      storeAppointmentResponse(response);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Nie udało się wysłać nagrania do backendu.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  function resetRecording() {
    setAudioBlob(null);
    setAppointmentResponse(null);
    clearStoredAppointmentResponse();
    setError(null);
    setAudioLevel(0);
  }

  function syncSelectedDeviceFromStream(stream: MediaStream) {
    const [track] = stream.getAudioTracks();
    const deviceId = track?.getSettings().deviceId;

    if (deviceId) {
      setSelectedDeviceId(deviceId);
    }
  }

  function startAudioPreview(stream: MediaStream) {
    const audioWindow = window as WindowWithWebkitAudioContext;
    const AudioContextClass = audioWindow.AudioContext || audioWindow.webkitAudioContext;
    if (!AudioContextClass) {
      return;
    }

    const audioContext = new AudioContextClass();
    const analyser = audioContext.createAnalyser();
    const source = audioContext.createMediaStreamSource(stream);
    analyser.fftSize = 256;
    source.connect(analyser);
    audioContextRef.current = audioContext;
    analyserRef.current = analyser;

    const samples = new Uint8Array(analyser.frequencyBinCount);

    function drawAudioLevel() {
      analyser.getByteTimeDomainData(samples);
      let sum = 0;

      for (const sample of samples) {
        const centeredSample = (sample - 128) / 128;
        sum += centeredSample * centeredSample;
      }

      const rms = Math.sqrt(sum / samples.length);
      setAudioLevel(Math.min(1, rms * 5));
      animationFrameRef.current = window.requestAnimationFrame(drawAudioLevel);
    }

    drawAudioLevel();
  }

  function stopAudioPreview() {
    if (animationFrameRef.current) {
      window.cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    void audioContextRef.current?.close();
    audioContextRef.current = null;
    analyserRef.current = null;
  }

  return (
    <section className="page page-grid">
      <div className="page-intro">
        <span className="eyebrow">Zgłoszenie głosowe pacjenta</span>
        <h1>Powiedz, z czym potrzebujesz pomocy.</h1>
        <p>
          Nagraj krótką wiadomość po polsku. Backend przepisze ją na tekst, przeanalizuje
          preferencje terminu i przygotuje testowe potwierdzenie SMS.
        </p>
      </div>

      <div className="record-layout">
        <section className="panel recorder-panel" aria-labelledby="recorder-title">
          <div className="panel-heading">
            <div>
              <h2 id="recorder-title">Wiadomość głosowa</h2>
              <p>Powiedz krótko: objawy, preferowany dzień i preferowaną godzinę.</p>
            </div>
            <div className={recording ? "recording-badge active" : "recording-badge"}>
              <span aria-hidden="true" />
              {recording ? "Nagrywanie" : "Gotowe"}
            </div>
          </div>

          <div className="recording-surface">
            <button
              className={recording ? "record-button recording" : "record-button"}
              onClick={recording ? stopRecording : startRecording}
              aria-label={recording ? "Zatrzymaj nagrywanie" : "Rozpocznij nagrywanie"}
            >
              {recording ? (
                <Square size={32} aria-hidden="true" />
              ) : (
                <Mic size={36} aria-hidden="true" />
              )}
            </button>
            <div>
              <h3>{recording ? "Słucham..." : audioBlob ? "Nagranie zapisane" : "Gotowe do nagrania"}</h3>
              <p>
                {recording
                  ? "Naciśnij stop, gdy skończysz mówić."
                  : audioBlob
                    ? "Odsłuchaj nagranie albo wyślij je do demo."
                    : "Naciśnij przycisk mikrofonu, aby rozpocząć."}
              </p>
            </div>
          </div>

          <div className="device-panel">
            <label htmlFor="microphone-select">Źródło mikrofonu</label>
            <div className="device-controls">
              <select
                id="microphone-select"
                value={selectedDeviceId}
                onChange={(event) => setSelectedDeviceId(event.target.value)}
                disabled={recording}
              >
                {audioDevices.length === 0 ? (
                  <option value="">Domyślny mikrofon</option>
                ) : (
                  audioDevices.map((device, index) => (
                    <option key={device.deviceId} value={device.deviceId}>
                      {device.label || `Mikrofon ${index + 1}`}
                    </option>
                  ))
                )}
              </select>
              <button
                className="icon-button"
                type="button"
                onClick={() => refreshAudioDevices({ requestPermission: true })}
                disabled={recording}
              >
                <RefreshCw size={18} aria-hidden="true" />
                <span>Odśwież</span>
              </button>
            </div>
            <p>{deviceStatus}</p>
          </div>

          <div
            className={recording ? "waveform active" : "waveform"}
            aria-label={
              recording
                ? `Poziom mikrofonu ${Math.round(audioLevel * 100)} procent`
                : "Podgląd poziomu mikrofonu"
            }
          >
            {waveformBars.map((bar) => {
              const distanceFromCenter = Math.abs(bar - (waveformBars.length - 1) / 2);
              const centerWeight = 1 - distanceFromCenter / (waveformBars.length / 2);
              const idleHeight = 10 + (bar % 5) * 4;
              const activeHeight = 12 + audioLevel * 86 * Math.max(0.22, centerWeight);

              return (
                <span
                  key={bar}
                  style={{
                    height: `${recording ? activeHeight : idleHeight}px`,
                    opacity: recording ? 0.42 + audioLevel * 0.58 : 0.36,
                  }}
                />
              );
            })}
          </div>

          <div className="input-meter" aria-live="polite">
            <div>
              <span>Poziom wejścia</span>
              <strong>{recording ? `${Math.round(audioLevel * 100)}%` : "Bezczynny"}</strong>
            </div>
            <div className="meter-track">
              <span style={{ width: `${recording ? Math.max(3, audioLevel * 100) : 0}%` }} />
            </div>
            {recording ? (
              <p className={activeAudioInput ? "input-status active" : "input-status"}>
                {activeAudioInput
                  ? "Wykryto sygnał mikrofonu."
                  : "Nie wykryto wyraźnego sygnału. Jeśli pasek się nie rusza, wybierz inny mikrofon."}
              </p>
            ) : null}
          </div>

          {audioUrl ? (
            <div className="audio-review">
              <PlayCircle size={20} aria-hidden="true" />
              <audio controls src={audioUrl} />
            </div>
          ) : null}

          {error ? (
            <p className="alert" role="alert">
              {error}
            </p>
          ) : null}

          <div className="button-row">
            <button
              className="button primary"
              onClick={submitRecording}
              disabled={!audioBlob || recording || submitting}
            >
              <Send size={18} aria-hidden="true" /> {submitting ? "Wysyłam..." : "Wyślij wiadomość"}
            </button>
            <button className="button" onClick={resetRecording} disabled={recording}>
              <RotateCcw size={18} aria-hidden="true" /> Wyczyść
            </button>
          </div>
        </section>

        <aside className="panel sms-panel" aria-labelledby="sms-title">
          <div className="panel-heading">
            <div>
              <h2 id="sms-title">Odpowiedź SMS</h2>
              <p>Ostatnia odpowiedź backendu jest zachowana w tej karcie przeglądarki.</p>
            </div>
          </div>

          <div className="phone-preview" aria-live="polite">
            <div className="phone-header">
              <span>Nazwa placówki</span>
              <Clock3 size={16} aria-hidden="true" />
            </div>
            <div className={appointmentResponse ? "sms-bubble filled" : "sms-bubble"}>
              {appointmentResponse?.sms_text ??
                "Tutaj pojawi się testowe potwierdzenie SMS po wysłaniu nagrania."}
            </div>
          </div>

          {appointmentResponse ? (
            <div className="debug-summary">
              <div>
                <span>Status</span>
                <strong>{appointmentResponse.status}</strong>
              </div>
              <div>
                <span>Transkrypcja</span>
                <p>{appointmentResponse.transcript}</p>
              </div>
              <div>
                <span>Umawianie</span>
                <p>{appointmentResponse.scheduling_explanation}</p>
              </div>
            </div>
          ) : null}

          <div className="status-list">
            <div>
              <CheckCircle2 size={18} aria-hidden="true" />
              Audio nagrywane lokalnie w przeglądarce
            </div>
            <div>
              <CheckCircle2 size={18} aria-hidden="true" />
              Odpowiedź backendu z terminem wizyty gotowa do integracji
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}

function getSupportedAudioMimeType() {
  const mimeTypes = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  return mimeTypes.find((mimeType) => MediaRecorder.isTypeSupported(mimeType));
}

function readStoredAppointmentResponse(): AppointmentResponse | null {
  try {
    const storedValue = window.sessionStorage.getItem(LAST_APPOINTMENT_RESPONSE_KEY);
    if (!storedValue) {
      return null;
    }

    return JSON.parse(storedValue) as AppointmentResponse;
  } catch {
    clearStoredAppointmentResponse();
    return null;
  }
}

function storeAppointmentResponse(response: AppointmentResponse) {
  window.sessionStorage.setItem(LAST_APPOINTMENT_RESPONSE_KEY, JSON.stringify(response));
}

function clearStoredAppointmentResponse() {
  window.sessionStorage.removeItem(LAST_APPOINTMENT_RESPONSE_KEY);
}

function getAudioConstraints(deviceId: string): MediaTrackConstraints {
  return {
    deviceId: deviceId ? { exact: deviceId } : undefined,
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  };
}

async function ensureMicrophonePermission() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  stream.getTracks().forEach((track) => track.stop());
}

async function openSelectedMicrophone(deviceId: string) {
  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: getAudioConstraints(deviceId),
    });
  } catch (error) {
    if (deviceId && error instanceof DOMException && error.name === "OverconstrainedError") {
      return navigator.mediaDevices.getUserMedia({ audio: getAudioConstraints("") });
    }

    throw error;
  }
}

function getDeviceStatusMessage(devices: MediaDeviceInfo[]) {
  if (devices.length === 0) {
    return "Nie znaleziono mikrofonu. Podłącz zestaw słuchawkowy albo kamerę i odśwież listę.";
  }

  const hasNamedDevices = devices.some((device) => device.label);
  if (!hasNamedDevices) {
    return "Zezwól na dostęp do mikrofonu, aby pokazać nazwy zestawu słuchawkowego i kamery.";
  }

  return `Wykryto ${devices.length} ${getPolishMicrophoneCountLabel(devices.length)}. Wybierz wejście, które porusza miernikiem poziomu.`;
}

function getRecordingErrorMessage(error: unknown) {
  if (error instanceof DOMException && error.name === "OverconstrainedError") {
    return "Wybrany mikrofon jest niedostępny. Odśwież urządzenia albo wybierz inne wejście.";
  }

  if (error instanceof DOMException && error.name === "NotAllowedError") {
    return "Nie udzielono dostępu do mikrofonu. Zezwól na dostęp i spróbuj ponownie.";
  }

  if (error instanceof DOMException && error.name === "NotFoundError") {
    return "Nie znaleziono mikrofonu. Podłącz zestaw słuchawkowy albo kamerę i odśwież urządzenia.";
  }

  return "Nie udało się rozpocząć nagrywania. Sprawdź wybrany mikrofon i spróbuj ponownie.";
}

function getPolishMicrophoneCountLabel(count: number) {
  if (count === 1) {
    return "źródło mikrofonu";
  }

  if (count >= 2 && count <= 4) {
    return "źródła mikrofonu";
  }

  return "źródeł mikrofonu";
}
