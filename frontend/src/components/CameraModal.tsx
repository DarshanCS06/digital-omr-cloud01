import React, { useRef, useState, useEffect } from 'react';
import { Camera, X, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';

interface CameraModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCapture: (file: File) => void;
}

export const CameraModal: React.FC<CameraModalProps> = ({ isOpen, onClose, onCapture }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [facingMode, setFacingMode] = useState<'environment' | 'user'>('environment');
  const [error, setError] = useState<string | null>(null);
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && !capturedBlob) {
      startCamera();
    }
    return () => {
      stopCamera();
    };
  }, [isOpen, facingMode, capturedBlob]);

  const startCamera = async () => {
    stopCamera();
    setError(null);
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError(
        'Tap "Open Android Camera" below to take a high-resolution photo using your phone camera.'
      );
      return;
    }
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: facingMode },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
      });
      setStream(mediaStream);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
    } catch (err: any) {
      setError(
        'Tap "Open Android Camera" below to capture the OMR sheet with your phone camera or select from gallery.'
      );
    }
  };

  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      setStream(null);
    }
  };

  const takeSnapshot = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (blob) {
          setCapturedBlob(blob);
          setPreviewUrl(URL.createObjectURL(blob));
          stopCamera();
        }
      },
      'image/jpeg',
      0.92
    );
  };

  const handleConfirm = () => {
    if (!capturedBlob) return;
    const file = new File([capturedBlob], `mobile_omr_${Date.now()}.jpg`, { type: 'image/jpeg' });
    onCapture(file);
    handleClose();
  };

  const handleRetake = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setCapturedBlob(null);
    setPreviewUrl(null);
  };

  const handleClose = () => {
    stopCamera();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setCapturedBlob(null);
    setPreviewUrl(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
      <div className="relative w-full max-w-2xl bg-slate-900 rounded-2xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between p-4 bg-slate-800 text-white border-b border-slate-700">
          <div className="flex items-center space-x-2">
            <Camera className="w-5 h-5 text-blue-400" />
            <h3 className="font-semibold text-base">Capture OMR Answer Sheet</h3>
          </div>
          <button onClick={handleClose} className="p-1 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Viewport Content */}
        <div className="relative flex-1 bg-black flex items-center justify-center overflow-hidden min-h-[350px]">
          {error ? (
            <div className="p-6 text-center text-slate-200 max-w-md space-y-4">
              <Camera className="w-12 h-12 text-blue-400 mx-auto" />
              <p className="text-sm text-slate-300">{error}</p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                <label className="w-full sm:w-auto inline-flex items-center justify-center px-5 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl cursor-pointer text-sm font-bold shadow-lg">
                  <Camera className="w-4 h-4 mr-2" /> Open Android Camera
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) {
                        onCapture(f);
                        handleClose();
                      }
                    }}
                  />
                </label>
                <label className="w-full sm:w-auto inline-flex items-center justify-center px-5 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-xl cursor-pointer text-sm font-bold">
                  Choose from Gallery
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) {
                        onCapture(f);
                        handleClose();
                      }
                    }}
                  />
                </label>
              </div>
            </div>
          ) : previewUrl ? (
            <img src={previewUrl} alt="Captured OMR" className="max-h-[60vh] w-auto object-contain" />
          ) : (
            <div className="relative w-full h-full flex items-center justify-center">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-full object-cover max-h-[60vh]"
              />
              {/* OMR Alignment Overlay Frame */}
              <div className="absolute inset-8 border-2 border-dashed border-blue-400/70 rounded-xl pointer-events-none flex flex-col justify-between p-3">
                <div className="flex justify-between">
                  <div className="w-6 h-6 border-t-2 border-l-2 border-blue-400"></div>
                  <div className="w-6 h-6 border-t-2 border-r-2 border-blue-400"></div>
                </div>
                <div className="text-center bg-black/60 text-white text-xs py-1 px-3 rounded-full mx-auto backdrop-blur-sm">
                  Align the 4 black corner squares inside this boundary
                </div>
                <div className="flex justify-between">
                  <div className="w-6 h-6 border-b-2 border-l-2 border-blue-400"></div>
                  <div className="w-6 h-6 border-b-2 border-r-2 border-blue-400"></div>
                </div>
              </div>
            </div>
          )}
          <canvas ref={canvasRef} className="hidden" />
        </div>

        {/* Modal Controls Footer */}
        <div className="p-4 bg-slate-800 flex items-center justify-between border-t border-slate-700">
          {!previewUrl ? (
            <>
              <button
                type="button"
                onClick={() => setFacingMode((prev) => (prev === 'environment' ? 'user' : 'environment'))}
                className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-xs font-medium text-slate-200"
              >
                <RefreshCw className="w-4 h-4" />
                <span>Switch Camera</span>
              </button>

              <button
                type="button"
                onClick={takeSnapshot}
                className="px-6 py-2.5 rounded-full bg-blue-600 hover:bg-blue-500 text-white font-semibold shadow-lg shadow-blue-500/30 flex items-center space-x-2 text-sm"
              >
                <Camera className="w-5 h-5" />
                <span>Snap Sheet</span>
              </button>

              <label className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-xs font-medium text-slate-200 cursor-pointer">
                <Camera className="w-4 h-4" />
                <span>Phone Cam</span>
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) {
                      onCapture(f);
                      handleClose();
                    }
                  }}
                />
              </label>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={handleRetake}
                className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-xs font-medium text-slate-200"
              >
                Retake
              </button>

              <button
                type="button"
                onClick={handleConfirm}
                className="px-6 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold shadow-lg shadow-emerald-500/30 flex items-center space-x-2 text-sm"
              >
                <CheckCircle2 className="w-5 h-5" />
                <span>Use This Photo</span>
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
