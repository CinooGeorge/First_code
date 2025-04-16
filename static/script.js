const recordButton = document.getElementById('record');
const stopButton = document.getElementById('stop');
const timerDisplay = document.getElementById('timer');
const answerDiv = document.getElementById('answer');
const uploadForm = document.getElementById('uploadForm');
const uploadStatus = document.getElementById('uploadStatus');
const audioPlayer = document.getElementById('audioPlayer');
const bookInput = document.getElementById('bookInput');

let mediaRecorder;
let audioChunks = [];
let timerInterval;
let startTime;
let isBookUploaded = false;  // Flag to track if the book was uploaded

// Disable record button initially
recordButton.disabled = true;

// Format time mm:ss
function formatTime(seconds) {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

// 📤 Book Upload
uploadForm.addEventListener('submit', (e) => {
  e.preventDefault();

  const formData = new FormData(uploadForm);

  fetch('/upload_book', {
    method: 'POST',
    body: formData
  })
  .then(res => res.json())
  .then(msg => {
    uploadStatus.textContent = msg.message;
    uploadStatus.style.color = "green";

    if (msg.book_url) {
      uploadStatus.innerHTML += `<br><a href="${msg.book_url}" target="_blank">Click here to view the uploaded book</a>`;
    }

    // Mark the book as uploaded and enable record button
    isBookUploaded = true;
    recordButton.disabled = false;
  })
  .catch(err => {
    uploadStatus.textContent = "❌ Failed to upload book.";
    uploadStatus.style.color = "red";
  });
});

// 🎙️ Audio Record & Submit
recordButton.addEventListener('click', () => {
  if (!isBookUploaded) {
    // Show error message if no book is uploaded
    alert("❌ Please upload a book first before recording.");
    return;
  }

  // Clear previous answer and stop TTS audio
  answerDiv.textContent = "Your answer will appear here...";
  audioPlayer.pause();
  audioPlayer.currentTime = 0;
  audioPlayer.src = "";
  audioPlayer.style.display = "none";

  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.start();
      recordButton.disabled = true;  // Disable record button during recording
      stopButton.disabled = false;

      startTime = Date.now();
      timerInterval = setInterval(() => {
        const seconds = Math.floor((Date.now() - startTime) / 1000);
        timerDisplay.textContent = formatTime(seconds);
      }, 1000);

      mediaRecorder.ondataavailable = event => {
        audioChunks.push(event.data);
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const audioFile = new File([audioBlob], 'recorded_audio.wav');
        const formData = new FormData();
        formData.append('audio_data', audioFile);

        fetch('/upload', {
          method: 'POST',
          body: formData
        })
        .then(response => response.json())
        .then(data => {
          if (data.answer) {
            answerDiv.textContent = `Answer: ${data.answer}`;
          }

          if (data.audio_url) {
            audioPlayer.src = data.audio_url;
            audioPlayer.style.display = "block";
          }
        })
        .catch(() => {
          answerDiv.textContent = "❌ Error: Unable to process audio.";
        });
      };
    })
    .catch(() => {
      alert('❌ Error accessing audio device.');
    });
});

// ⏹️ Stop Recording
stopButton.addEventListener('click', () => {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    clearInterval(timerInterval);
    stopButton.disabled = true;
    recordButton.disabled = false;
  }
});

// 🧼 Clear previous uploads and responses when selecting new book
bookInput.addEventListener('change', () => {
  uploadStatus.textContent = '';
  uploadStatus.style.color = 'black';
  uploadStatus.innerHTML = '';
  answerDiv.textContent = "Your answer will appear here...";
  audioPlayer.pause();
  audioPlayer.currentTime = 0;
  audioPlayer.src = "";
  audioPlayer.style.display = "none";
  timerDisplay.textContent = "00:00";

  // Reset the book uploaded flag
  isBookUploaded = false;

  // Disable record button if no book is uploaded
  recordButton.disabled = true;
});
