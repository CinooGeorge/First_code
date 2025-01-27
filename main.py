from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, flash
import os

# Google Cloud libraries for Speech-to-Text and Text-to-Speech
from google.cloud import speech
from google.cloud import texttospeech_v1

app = Flask(__name__)
# Set a secret key for session handling
app.secret_key = 'your_secret_key_here'

# Configure upload folders
UPLOAD_FOLDER = 'uploads'
RECORDED_FOLDER = os.path.join(UPLOAD_FOLDER, 'recorded')
GENERATED_FOLDER = os.path.join(UPLOAD_FOLDER, 'generated')
ALLOWED_EXTENSIONS = {'wav', 'txt'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RECORDED_FOLDER'] = RECORDED_FOLDER
app.config['GENERATED_FOLDER'] = GENERATED_FOLDER

# Ensure the folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RECORDED_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)

# Initialize Google Cloud clients
speech_client = speech.SpeechClient()
text_to_speech_client = texttospeech_v1.TextToSpeechClient()

# Utility function to check allowed file types
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_files(folder):
    files = [f for f in os.listdir(folder) if allowed_file(f) and not f.endswith('.txt')]
    files.sort(reverse=True)
    return files


# Route to the home page
@app.route('/')
def index():
    recorded_files = get_files(app.config['RECORDED_FOLDER'])
    generated_files = get_files(app.config['GENERATED_FOLDER'])
    return render_template('index.html', recorded_files=recorded_files, generated_files=generated_files)

# Route to upload audio for Speech-to-Text
@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        flash('No audio data')
        return redirect(request.url)
    file = request.files['audio_data']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file:
        # Generate a unique filename
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        file_path = os.path.join(app.config['RECORDED_FOLDER'], filename)
        file.save(file_path)

        # Call the Google Cloud Speech-to-Text API and save the transcript
        with open(file_path, 'rb') as f:
            audio_content = f.read()

        # Speech-to-Text processing
        audio = speech.RecognitionAudio(content=audio_content)
        config = speech.RecognitionConfig(
            language_code="en-US",
            audio_channel_count=1,
        )
        response = speech_client.recognize(config=config, audio=audio)

        # Save the transcript
        transcript = "\n".join([result.alternatives[0].transcript for result in response.results])
        transcript_filename = filename + '.txt'
        transcript_path = os.path.join(app.config['RECORDED_FOLDER'], transcript_filename)
        with open(transcript_path, 'w') as f:
            f.write(transcript)

        flash(f'Audio uploaded and processed successfully! Transcript saved as {transcript_filename}')
        return redirect('/')

# Route to serve the uploaded file
@app.route('/uploads/<path:folder>/<path:filename>')
def uploaded_file(folder, filename):
    folder_path = app.config['RECORDED_FOLDER'] if folder == 'recorded' else app.config['GENERATED_FOLDER']
    return send_from_directory(folder_path, filename)

# Route to upload text for Text-to-Speech
@app.route('/upload_text', methods=['POST'])
def upload_text():
    text = request.form['text']
    if not text.strip():
        flash('No text provided')
        return redirect('/')

    # Call Google Cloud Text-to-Speech API
    synthesis_input = texttospeech_v1.SynthesisInput(text=text)
    voice = texttospeech_v1.VoiceSelectionParams(
        language_code="en-US", ssml_gender=texttospeech_v1.SsmlVoiceGender.NEUTRAL
    )
    audio_config = texttospeech_v1.AudioConfig(audio_encoding=texttospeech_v1.AudioEncoding.LINEAR16)

    response = text_to_speech_client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )

    # Save the audio output in the GENERATED folder
    tts_filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
    tts_path = os.path.join(app.config['GENERATED_FOLDER'], tts_filename)
    with open(tts_path, 'wb') as out:
        out.write(response.audio_content)

    flash(f'Text-to-Speech audio generated successfully! You can download it here: {tts_filename}')
    return redirect('/')

# Serve static JS file
@app.route('/script.js', methods=['GET'])
def scripts_js():
    return send_file('./script.js')

if __name__ == '__main__':
    app.run(debug=True, port=5004)
