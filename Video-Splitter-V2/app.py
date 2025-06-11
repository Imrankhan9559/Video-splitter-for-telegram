import os
import math
import time
import shutil
import threading
from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
from zipfile import ZipFile
import io
import subprocess
import logging
from datetime import datetime, timedelta
from flask_session import Session
import secrets

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.abspath('uploads')
app.config['BASE_SPLIT_FOLDER'] = os.path.abspath(os.path.expanduser('~/Downloads/video_splitter'))
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024 * 1024  # 100 GB limit
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './flask_session'
app.config['SECRET_KEY'] = secrets.token_hex(32)  # Generate a secure secret key
app.config['CLEANUP_INTERVAL'] = 300  # Cleanup every 5 minutes

# Create directories if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['BASE_SPLIT_FOLDER'], exist_ok=True)
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
logging.info(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
logging.info(f"Split folder: {app.config['BASE_SPLIT_FOLDER']}")

# Initialize session
Session(app)

# Global dictionaries
progress_dict = {}
session_files = {}  # Track files by session

def start_cleanup_thread():
    """Start background cleanup thread"""
    def cleanup_task():
        while True:
            try:
                cleanup_old_files()
            except Exception as e:
                logging.error(f"Cleanup task error: {e}")
            time.sleep(app.config['CLEANUP_INTERVAL'])
    
    thread = threading.Thread(target=cleanup_task, daemon=True)
    thread.start()
    logging.info("Started background cleanup thread")

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def cleanup_folder(folder_path):
    """Remove folder and its contents"""
    try:
        shutil.rmtree(folder_path)
        logging.info(f"Cleaned up folder: {folder_path}")
        return True
    except Exception as e:
        logging.error(f"Error cleaning up folder {folder_path}: {e}")
        return False

def cleanup_old_files():
    """Clean up files older than 1 hour"""
    now = time.time()
    cutoff = now - 3600  # 1 hour
    
    # Clean upload folder
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff:
            try:
                os.remove(file_path)
                logging.info(f"Cleaned up old upload: {file_path}")
            except Exception as e:
                logging.error(f"Error cleaning up old upload {file_path}: {e}")
    
    # Clean split folders
    for folder in os.listdir(app.config['BASE_SPLIT_FOLDER']):
        folder_path = os.path.join(app.config['BASE_SPLIT_FOLDER'], folder)
        if os.path.isdir(folder_path) and os.path.getmtime(folder_path) < cutoff:
            try:
                cleanup_folder(folder_path)
            except Exception as e:
                logging.error(f"Error cleaning up old split folder {folder_path}: {e}")

def create_zip(folder_path):
    """Create a zip file from folder contents"""
    memory_file = io.BytesIO()
    with ZipFile(memory_file, 'w') as zf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zf.write(file_path, arcname)
    memory_file.seek(0)
    return memory_file

def get_video_duration(filename):
    """Get video duration in seconds using ffprobe"""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of',
            'default=noprint_wrappers=1:nokey=1', filename
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout)
    except Exception as e:
        logging.error(f"Error getting video duration: {e}")
        return None

def split_video_with_ffmpeg(input_path, output_folder, part_size_mb=2000):
    """Split video properly using ffmpeg"""
    filename = os.path.basename(input_path)
    name, ext = os.path.splitext(filename)
    
    # Get video duration
    duration = get_video_duration(input_path)
    if duration is None:
        logging.error(f"Could not determine duration for {input_path}")
        return None
    
    # Calculate split points (in seconds)
    file_size = os.path.getsize(input_path)
    part_size_bytes = part_size_mb * 1024 * 1024  # Convert MB to bytes
    total_parts = math.ceil(file_size / part_size_bytes)
    part_duration = duration / total_parts
    
    part_files = []
    
    for i in range(total_parts):
        part_filename = f"{name}_part{i+1}{ext}"
        part_path = os.path.join(output_folder, part_filename)
        
        start_time = i * part_duration
        end_time = (i + 1) * part_duration if i < total_parts - 1 else None
        
        cmd = [
            'ffmpeg', '-i', input_path,
            '-ss', str(start_time),
            '-c', 'copy'  # Use stream copy for no re-encoding
        ]
        
        if end_time is not None:
            cmd.extend(['-to', str(end_time)])
        
        cmd.append(part_path)
        
        try:
            logging.info(f"Splitting part {i+1}/{total_parts}: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            part_files.append(part_filename)
            
            # Update progress
            progress = ((i + 1) / total_parts) * 100
            progress_dict[filename] = progress
            logging.info(f"Created part {part_filename}, progress: {progress:.2f}%")
        except subprocess.CalledProcessError as e:
            error_msg = f"Error splitting video: {e.stderr.decode('utf-8') if e.stderr else str(e)}"
            logging.error(error_msg)
            return None
    
    return part_files

@app.before_request
def before_request():
    """Initialize session tracking"""
    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(16)
        session_files[session['session_id']] = {
            'uploads': [],
            'splits': []
        }
        logging.info(f"New session started: {session['session_id']}")

@app.route('/')
def index():
    # Clean up previous session files
    cleanup_session_files()
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file part in request'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No selected file'})
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Invalid file type'})
        
        filename = secure_filename(file.filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save file
        file.save(upload_path)
        
        # Verify file was saved
        if not os.path.exists(upload_path):
            return jsonify({'success': False, 'error': 'File save failed'})
        
        # Track file in session
        session_id = session['session_id']
        session_files[session_id]['uploads'].append(upload_path)
        
        file_size = os.path.getsize(upload_path)
        logging.info(f"Uploaded {filename} ({file_size} bytes) to {upload_path}")
        
        return jsonify({'success': True, 'filename': filename})
    
    except Exception as e:
        logging.exception("Error during upload")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/process', methods=['POST'])
def process():
    try:
        filename = request.form['filename']
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Verify file exists
        if not os.path.exists(upload_path):
            logging.error(f"File not found: {upload_path}")
            return jsonify({'success': False, 'error': 'Uploaded file not found'})
        
        name, ext = os.path.splitext(filename)
        output_folder = os.path.join(app.config['BASE_SPLIT_FOLDER'], name)
        
        # Create output folder
        os.makedirs(output_folder, exist_ok=True)
        logging.info(f"Created output folder: {output_folder}")
        
        # Track folder in session
        session_id = session['session_id']
        session_files[session_id]['splits'].append(output_folder)
        
        # Split the video
        part_files = split_video_with_ffmpeg(upload_path, output_folder)
        
        if part_files is None:
            return jsonify({'success': False, 'error': 'Failed to split video'})
        
        # Remove original upload (but keep tracking split folder)
        try:
            if upload_path in session_files[session_id]['uploads']:
                session_files[session_id]['uploads'].remove(upload_path)
            os.remove(upload_path)
            logging.info(f"Removed original file: {upload_path}")
        except Exception as e:
            logging.error(f"Error removing original file: {e}")
        
        progress_dict[filename] = 100
        
        return jsonify({
            'success': True,
            'filename': filename,
            'split_files': part_files,
            'output_folder': output_folder,
            'folder_name': name
        })
    
    except Exception as e:
        logging.exception("Error during processing")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/progress/<filename>')
def progress(filename):
    prog = progress_dict.get(filename, 0)
    return jsonify({'progress': round(prog, 2)})

@app.route('/download/zip/<folder_name>')
def download_zip(folder_name):
    try:
        folder_path = os.path.join(app.config['BASE_SPLIT_FOLDER'], folder_name)
        if not os.path.exists(folder_path):
            return jsonify({'success': False, 'error': 'Folder not found'})
        
        zip_file = create_zip(folder_path)
        response = send_file(
            zip_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{folder_name}.zip'
        )
        
        # Clean up after download
        @response.call_on_close
        def cleanup():
            cleanup_folder(folder_path)
            # Remove from session tracking
            session_id = session.get('session_id')
            if session_id and session_id in session_files:
                if folder_path in session_files[session_id]['splits']:
                    session_files[session_id]['splits'].remove(folder_path)
        
        return response
    except Exception as e:
        logging.exception("Error during zip download")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download/separate/<folder_name>/<filename>')
def download_separate(folder_name, filename):
    try:
        folder_path = os.path.join(app.config['BASE_SPLIT_FOLDER'], folder_name)
        if not os.path.exists(folder_path):
            return jsonify({'success': False, 'error': 'Folder not found'})
        
        # Check if this is the last file to be downloaded
        files_in_folder = os.listdir(folder_path)
        is_last_file = len(files_in_folder) == 1 and files_in_folder[0] == filename
        
        response = send_from_directory( # type: ignore
            folder_path,
            filename,
            as_attachment=True
        )
        
        # Clean up if this is the last file
        if is_last_file:
            @response.call_on_close
            def cleanup():
                cleanup_folder(folder_path)
                # Remove from session tracking
                session_id = session.get('session_id')
                if session_id and session_id in session_files:
                    if folder_path in session_files[session_id]['splits']:
                        session_files[session_id]['splits'].remove(folder_path)
        
        return response
    except Exception as e:
        logging.exception("Error during separate download")
        return jsonify({'success': False, 'error': str(e)})

def cleanup_session_files():
    """Clean up files associated with the current session"""
    session_id = session.get('session_id')
    if not session_id or session_id not in session_files:
        return
    
    # Clean up uploads
    for file_path in session_files[session_id]['uploads'][:]:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"Cleaned session upload: {file_path}")
            session_files[session_id]['uploads'].remove(file_path)
        except Exception as e:
            logging.error(f"Error cleaning session upload: {e}")
    
    # Clean up split folders
    for folder_path in session_files[session_id]['splits'][:]:
        try:
            if os.path.exists(folder_path):
                cleanup_folder(folder_path)
                logging.info(f"Cleaned session split folder: {folder_path}")
            session_files[session_id]['splits'].remove(folder_path)
        except Exception as e:
            logging.error(f"Error cleaning session split folder: {e}")

@app.route('/cleanup', methods=['POST'])
def cleanup():
    """Explicit cleanup endpoint"""
    cleanup_session_files()
    return jsonify({'success': True, 'message': 'Session files cleaned'})

if __name__ == '__main__':
    # Ensure directories are writable
    for path in [app.config['UPLOAD_FOLDER'], app.config['BASE_SPLIT_FOLDER']]:
        if not os.access(path, os.W_OK):
            logging.warning(f"Directory not writable: {path}")
    
    # Start cleanup thread
    start_cleanup_thread()
    
    app.run(debug=True, host='0.0.0.0', port=5000)