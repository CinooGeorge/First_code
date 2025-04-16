import os
import uuid
import logging
from flask import Flask, request, render_template, jsonify, send_from_directory, url_for
from werkzeug.utils import secure_filename
import google.generativeai as genai
from google.cloud import texttospeech  # Google Cloud Text-to-Speech library
import time

# Initialize Flask app
app = Flask(__name__)


# Configure upload folders
app.config['UPLOAD_FOLDER_BOOKS'] = 'uploads/books'
app.config['UPLOAD_FOLDER_QUESTIONS'] = 'uploads/questions'
app.config['UPLOAD_FOLDER_AUDIO_RESPONSES'] = 'uploads/audio_responses'

# Create folders if not exist
os.makedirs(app.config['UPLOAD_FOLDER_BOOKS'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER_QUESTIONS'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER_AUDIO_RESPONSES'], exist_ok=True)

# ✅ Gemini API Setup
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY is not set in the environment variables!")

genai.configure(api_key=api_key)
model = genai.GenerativeModel(model_name="gemini-1.5-pro") 

# Initialize Google Cloud TTS Client
client = texttospeech.TextToSpeechClient()

# Enable Flask debug mode for detailed logging
app.config['DEBUG'] = True

# Set up logging to capture debug information
logging.basicConfig(level=logging.DEBUG)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload_book", methods=["POST"])
def upload_book():
    # Clear the previous uploaded book
    for file in os.listdir(app.config['UPLOAD_FOLDER_BOOKS']):
        os.remove(os.path.join(app.config['UPLOAD_FOLDER_BOOKS'], file))

    book = request.files.get("book")
    if book and book.filename.endswith(".pdf"):
        # Save the book to the server
        path = os.path.join(app.config['UPLOAD_FOLDER_BOOKS'], secure_filename(book.filename))
        book.save(path)
        app.logger.info(f"Book uploaded successfully: {book.filename}")
        
        # Create the URL for the uploaded book
        book_url = url_for('serve_book', filename=secure_filename(book.filename))

        return jsonify({"message": "✅ Book uploaded successfully!", "book_url": book_url})
    else:
        app.logger.error(f"Invalid book format: {book.filename if book else 'None'}")
        return "❌ Invalid book format, only PDF files are allowed.", 400

@app.route("/upload", methods=["POST"])
def upload_audio():
    audio = request.files.get("audio_data")
    if not audio:
        app.logger.error("No audio file received.")
        return jsonify({"error": "No audio received"}), 400

    # Ensure audio file is in a valid format (WAV or MP3)
    valid_audio_formats = ['.wav', '.mp3']
    if not any(audio.filename.endswith(ext) for ext in valid_audio_formats):
        app.logger.error(f"Invalid audio format: {audio.filename}")
        return jsonify({"error": "Invalid audio format. Only WAV and MP3 are supported."}), 400

    # Save the audio file
    audio_filename = secure_filename(audio.filename)
    audio_path = os.path.join(app.config['UPLOAD_FOLDER_QUESTIONS'], audio_filename)
    try:
        audio.save(audio_path)
        app.logger.info(f"Audio file saved: {audio_filename}")
    except Exception as e:
        app.logger.error(f"Error saving audio file: {str(e)}")
        return jsonify({"error": f"Error saving audio file: {str(e)}"}), 500

    # Find the most recent book
    book_files = sorted(os.listdir(app.config['UPLOAD_FOLDER_BOOKS']), reverse=True)
    if not book_files:
        return jsonify({"answer": "No book uploaded yet!"})
    
    book_path = os.path.join(app.config['UPLOAD_FOLDER_BOOKS'], book_files[0])

    # Upload files to Gemini
    try:
        book_part = genai.upload_file(book_path, mime_type="application/pdf")
        audio_part = genai.upload_file(audio_path, mime_type="audio/wav" if audio.filename.endswith(".wav") else "audio/mp3")
    except Exception as e:
        return jsonify({"error": f"Error uploading files to Gemini: {str(e)}"}), 500

    prompt = "Answer the user's question in the audio file based on the content of the uploaded book."
    contents = [prompt, audio_part, book_part]

    try:
        # Generate response from the model
        response = model.generate_content(contents)
        answer = response.text.strip()

        if not answer:
            return jsonify({"error": "No answer generated. Please check the content and try again."}), 500

        # Convert answer to audio using Google Text-to-Speech
        audio_response_filename = f"response_audio_{uuid.uuid4().hex}.mp3"  # Unique filename for each response
        audio_response_path = os.path.join(app.config['UPLOAD_FOLDER_AUDIO_RESPONSES'], audio_response_filename)

        # Prepare the synthesis input for Google TTS
        synthesis_input = texttospeech.SynthesisInput(text=answer)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US", ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        # Generate audio response from the text
        response_audio = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        # Save audio response to file
        with open(audio_response_path, "wb") as out:
            out.write(response_audio.audio_content)

        app.logger.info(f"Audio response saved: {audio_response_filename}")

        return jsonify({"answer": answer, "audio_url": f"/audio_responses/{audio_response_filename}"})

    except Exception as e:
        app.logger.error(f"Error generating content with Gemini: {str(e)}")
        return jsonify({"error": f"Error generating content with Gemini: {str(e)}"}), 500

@app.route("/audio_responses/<filename>")
def serve_audio(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER_AUDIO_RESPONSES'], filename)

@app.route("/books/<filename>")
def serve_book(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER_BOOKS'], filename)

# Optional cleanup function for old audio files (delete files older than 24 hours)
def clean_old_audio_files():
    threshold_time = time.time() - (24 * 60 * 60)  # Files older than 24 hours
    for filename in os.listdir(app.config['UPLOAD_FOLDER_AUDIO_RESPONSES']):
        file_path = os.path.join(app.config['UPLOAD_FOLDER_AUDIO_RESPONSES'], filename)
        if os.path.isfile(file_path):
            # Get the file's last modified time
            file_modified_time = os.path.getmtime(file_path)
            if file_modified_time < threshold_time:
                os.remove(file_path)
                app.logger.info(f"Deleted old audio file: {filename}")

# Uncomment this line to run the cleanup function periodically
# clean_old_audio_files()

if __name__ == "__main__":
    app.run(debug=True)
