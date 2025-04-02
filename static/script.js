const recordButton = document.getElementById('record');
const stopButton = document.getElementById('stop');
const audioElement = document.getElementById('audio');
const uploadForm = document.getElementById('uploadForm');
const timerDisplay = document.getElementById('timer');

let mediaRecorder;
let audioChunks = [];
let startTime;
let timerInterval;

function formatTime(time) {
  const minutes = Math.floor(time / 60);
  const seconds = time % 60;
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

recordButton.addEventListener('click', () => {
  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.start();

      startTime = Date.now();
      timerInterval = setInterval(() => {
        const elapsedTime = Math.floor((Date.now() - startTime) / 1000);
        timerDisplay.textContent = formatTime(elapsedTime);
      }, 1000);

      mediaRecorder.ondataavailable = e => {
        audioChunks.push(e.data);
      };

      mediaRecorder.onstop = () => {
        clearInterval(timerInterval);
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });

        const filename = `${new Date().toISOString()}_audio.wav`;  // Ensure filename is unique

        const formData = new FormData();
        formData.append('audio_data', audioBlob, filename);

        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => location.reload())  // Reload after upload
        .catch(error => console.error('Error uploading audio:', error));
      };
    })
    .catch(error => console.error('Error accessing microphone:', error));

  // Disable buttons during recording
  recordButton.disabled = true;
  stopButton.disabled = false;
});

stopButton.addEventListener('click', () => {
  if (mediaRecorder) {
    mediaRecorder.stop();
  }
  // Re-enable buttons after stopping the recording
  recordButton.disabled = false;
  stopButton.disabled = true;
});

stopButton.disabled = true;
