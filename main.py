from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
from datetime import datetime
import vertexai
from vertexai.generative_models import GenerativeModel, Part

app = Flask(__name__)

# Configure the uploads folder
UPLOADS_FOLDER = 'uploads'
GENERATED_FOLDER = os.path.join(UPLOADS_FOLDER, 'generated')  # For STT and Sentiment Analysis responses

app.config['UPLOADS_FOLDER'] = UPLOADS_FOLDER
app.config['GENERATED_FOLDER'] = GENERATED_FOLDER

# Ensure the directory exists
os.makedirs(GENERATED_FOLDER, exist_ok=True)

# Initialize Google Cloud Vertex AI
vertexai.init(project='cinoo-conai', location='us-central1')  # Use your GCP project and location

model = GenerativeModel("gemini-1.5-flash-001")  # Use your preferred model

ALLOWED_EXTENSIONS = {'wav'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_files(folder):
    files = [f for f in os.listdir(folder) if allowed_file(f)]
    files.sort(reverse=True)
    return files

@app.route('/')
def index():
    stt_files = get_files(GENERATED_FOLDER)  # Get uploaded audio files
    text_files = [f for f in os.listdir(GENERATED_FOLDER) if f.endswith('.txt')]  # Get transcript files
    text_files.sort(reverse=True)
    return render_template('index.html', stt_files=stt_files, text_files=text_files)

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

        # Transcribe the audio and analyze sentiment using the multimodal LLM
        transcript, sentiment_analysis = analyze_audio_with_llm(file_path)

        # Save the response to a text file
        output_filename = os.path.join(app.config['GENERATED_FOLDER'], filename + ".txt")
        with open(output_filename, 'w') as output_file:
            output_file.write(f"Transcript:\n{transcript}\n\nSentiment Analysis:\n{sentiment_analysis}")

    return redirect('/')

def analyze_audio_with_llm(audio_path):
    # Read the audio file content
    with open(audio_path, 'rb') as audio_file:
        audio_content = audio_file.read()

    # Prepare the audio part
    audio_part = Part.from_data(audio_content, mime_type="audio/wav")

    # Define the prompt for the multimodal LLM
    prompt = """
    Please provide an exact transcript for the audio, followed by sentiment analysis.

    Your response should follow the format:

    Text: USERS SPEECH TRANSCRIPTION

    Sentiment Analysis: positive|neutral|negative
    """

    # Generate the response from the model
    response = model.generate_content([audio_part, prompt])
    
    # Extract the transcript and sentiment from the response
    response_text = response.text
    return response_text.split("\n\nSentiment Analysis:")[0].replace("Text:", "").strip(), response_text.split("\n\nSentiment Analysis:")[1].strip()

@app.route('/uploads/<filename>')
def upload_file(filename):
    return send_from_directory(app.config['GENERATED_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
