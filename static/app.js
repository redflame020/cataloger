/* Shared utilities for Cataloger */

function accumulateWords(existing, newWords, minLen) {
  minLen = minLen || 3;
  const result = {...existing};
  for (const w of newWords) {
    const clean = w.replace(/[^a-zA-Z]/g, '');
    if (clean.length >= minLen) {
      const key = clean.toLowerCase();
      result[key] = (result[key] || 0) + 1;
    }
  }
  return result;
}

function getHighFreqWords(wordMap, threshold) {
  threshold = threshold || 2;
  const entries = Object.entries(wordMap).filter(([_, count]) => count >= threshold);
  entries.sort((a, b) => b[1] - a[1]);
  return entries.map(([w]) => w);
}

function showToast(message, type, duration) {
  type = type || 'success';
  duration = duration || 2000;
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.classList.add('toast-show'), 10);
  setTimeout(() => {
    toast.classList.remove('toast-show');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

function startCamera(videoEl, onReady) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showToast('Camera not available on this device', 'error', 3000);
    return;
  }
  navigator.mediaDevices.getUserMedia({
    video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }
  }).then(stream => {
    videoEl.srcObject = stream;
    videoEl.onloadedmetadata = () => {
      videoEl.play();
      if (onReady) onReady();
    };
  }).catch(err => {
    showToast('Camera error: ' + err.message, 'error', 3000);
  });
}

function stopCamera(videoEl) {
  if (!videoEl) return;
  const stream = videoEl.srcObject;
  if (stream) {
    stream.getTracks().forEach(t => t.stop());
  }
  videoEl.srcObject = null;
}

function captureFrame(videoEl) {
  const canvas = document.createElement('canvas');
  canvas.width = videoEl.videoWidth;
  canvas.height = videoEl.videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(videoEl, 0, 0);
  return new Promise(resolve => {
    canvas.toBlob(resolve, 'image/jpeg', 0.7);
  });
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}
