from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
from google.cloud import speech, texttospeech, language
import os
from datetime import datetime

app = Flask(__name__)

# Configure the uploads folder
UPLOADS_FOLDER = 'uploads'

# Configure subdirectories inside uploads (STT and TTS)
GENERATED_FOLDER = os.path.join(UPLOADS_FOLDER, 'generated')  # For STT transcripts
RECORDED_FOLDER = os.path.join(UPLOADS_FOLDER, 'recorded')    # For TTS audio

app.config['UPLOADS_FOLDER'] = UPLOADS_FOLDER
app.config['GENERATED_FOLDER'] = GENERATED_FOLDER
app.config['RECORDED_FOLDER'] = RECORDED_FOLDER

# Ensure the directory exists
os.makedirs(GENERATED_FOLDER, exist_ok=True)
os.makedirs(RECORDED_FOLDER, exist_ok=True)

# Initialize Google Cloud Clients
speech_client = speech.SpeechClient()
tts_client = texttospeech.TextToSpeechClient()
language_client = language.LanguageServiceClient()

ALLOWED_EXTENSIONS = {'wav'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_files(folder):
    files = [f for f in os.listdir(folder) if allowed_file(f)]
    files.sort(reverse=True)
    return files

@app.route('/')
def index():
    stt_files = get_files(GENERATED_FOLDER)  # Speech-to-Text files
    tts_files = get_files(RECORDED_FOLDER)   # Text-to-Speech files

    # Load TTS transcripts
    tts_file_data = []
    for file in tts_files:
        transcript_file = os.path.join(RECORDED_FOLDER, file + ".txt")
        transcript = ""
        sentiment_file = os.path.join(RECORDED_FOLDER, file + "_sentiment.txt")
        sentiment = ""
        if os.path.exists(transcript_file):
            with open(transcript_file, 'r') as f:
                transcript = f.read()
        if os.path.exists(sentiment_file):
            with open(sentiment_file, 'r') as f:
                sentiment = f.read()
        tts_file_data.append((file, transcript, sentiment))

    return render_template('index.html', stt_files=stt_files, tts_file_data=tts_file_data)

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        return redirect(request.url)

    file = request.files['audio_data']
    if file.filename == '':
        return redirect(request.url)

    if file and allowed_file(file.filename):
        filename = datetime.now().strftime("%Y%m%d-%H%M%S") + '.wav'
        file_path = os.path.join(app.config['GENERATED_FOLDER'], filename)
        file.save(file_path)

        # Convert speech to text and save in generated folder
        transcript = transcribe_audio(file_path)
        txt_filename = os.path.join(app.config['GENERATED_FOLDER'], filename + ".txt")
        with open(txt_filename, 'w') as txt_file:
            txt_file.write(transcript)

        # Perform sentiment analysis and save the result
        sentiment, sentiment_classification = analyze_text_sentiment(transcript)
        sentiment_filename = os.path.join(app.config['GENERATED_FOLDER'], filename + "_sentiment.txt")

        # Merge the transcript and sentiment into one file
        with open(sentiment_filename, 'w') as sentiment_file:
            sentiment_file.write(f"Transcript:\n{transcript}\n\nSentiment Analysis:\n{sentiment}\nSentiment Classification: {sentiment_classification}")

    return redirect('/')

@app.route('/upload_text', methods=['POST'])
def upload_text():
    text = request.form['text']
    if not text:
        return redirect('/')

    filename = datetime.now().strftime("%Y%m%d-%H%M%S") + '.wav'
    file_path = os.path.join(app.config['RECORDED_FOLDER'], filename)

    # Convert text to speech and save in recorded folder
    audio_data = text_to_speech(text)
    with open(file_path, 'wb') as audio_file:
        audio_file.write(audio_data)

    # Save transcript of text in recorded folder
    transcript_filename = os.path.join(app.config['RECORDED_FOLDER'], filename + ".txt")
    with open(transcript_filename, 'w') as text_file:
        text_file.write(text)

    # Perform sentiment analysis and save the result
    sentiment, sentiment_classification = analyze_text_sentiment(text)
    sentiment_filename = os.path.join(app.config['RECORDED_FOLDER'], filename + "_sentiment.txt")

    # Merge the transcript and sentiment into one file
    with open(sentiment_filename, 'w') as sentiment_file:
        sentiment_file.write(f"Transcript:\n{text}\n\nSentiment Analysis:\n{sentiment}\nSentiment Classification: {sentiment_classification}")

    return redirect('/')

def transcribe_audio(file_path):
    print(f"Starting transcription for {file_path}")
    
    with open(file_path, 'rb') as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        language_code="en-US",
        model="default",  # Use 'default' for short files, 'latest_long' for longer files
        enable_word_confidence=True,
        enable_word_time_offsets=True,
    )

    try:
        operation = speech_client.long_running_recognize(config=config, audio=audio)
        response = operation.result(timeout=90)
        print("Transcription completed.")

        transcript = "\n".join([result.alternatives[0].transcript for result in response.results])
        return transcript
    except Exception as e:
        print(f"Error during transcription: {e}")
        return "Error during transcription."

def text_to_speech(text):
    input_text = texttospeech.SynthesisInput(text=text)

    # Choose either Male or Female voice
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE  # Change to MALE for male voice
    )

    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)

    try:
        response = tts_client.synthesize_speech(
            request=texttospeech.SynthesizeSpeechRequest(
                input=input_text,
                voice=voice,
                audio_config=audio_config,
            )
        )
        return response.audio_content
    except Exception as e:
        print(f"Error during text-to-speech conversion: {e}")
        return b"Error during text-to-speech conversion."

def analyze_text_sentiment(text):
    document = language.Document(
        content=text,
        type_=language.Document.Type.PLAIN_TEXT,
    )
    response = language_client.analyze_sentiment(document=document)
    sentiment = response.document_sentiment

    # Sentiment Classification based on the score
    if sentiment.score > 0.75:
        sentiment_classification = "POSITIVE SENTIMENT"
    elif sentiment.score < -0.75:
        sentiment_classification = "NEGATIVE SENTIMENT"
    else:
        sentiment_classification = "NEUTRAL SENTIMENT"

    sentiment_result = f"SENTIMENT SCORE: {sentiment.score},SENTIMENT MAGNITUDE: {sentiment.magnitude}"
    
    return sentiment_result, sentiment_classification

@app.route('/uploads/<folder>/<filename>')
def upload_file(folder, filename):
    if folder == 'generated':
        return send_from_directory(app.config['GENERATED_FOLDER'], filename)
    elif folder == 'recorded':
        return send_from_directory(app.config['RECORDED_FOLDER'], filename)
    return "File not found", 404

if __name__ == '__main__':
    app.run(debug=True)
