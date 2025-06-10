import os
import math
from flask import Flask, render_template, request, redirect, send_from_directory, jsonify, send_file
from werkzeug.utils import secure_filename
import time
import shutil
from zipfile import ZipFile
import io

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['BASE_SPLIT_FOLDER'] = os.path.expanduser('~/Downloads/video_splitter')
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov', 'mkv', 'webm'}

# Create directories if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['BASE_SPLIT_FOLDER'], exist_ok=True)

# Global dictionary to store progress
progress_dict = {}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def cleanup_folder(folder_path):
    """Remove folder and its contents"""
    try:
        shutil.rmtree(folder_path)
        return True
    except Exception as e:
        print(f"Error cleaning up folder: {e}")
        return False

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)
        return jsonify({'success': True, 'filename': filename})
    
    return jsonify({'success': False, 'error': 'Invalid file type'})

@app.route('/process', methods=['POST'])
def process():
    filename = request.form['filename']
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    name, ext = os.path.splitext(filename)
    output_folder = os.path.join(app.config['BASE_SPLIT_FOLDER'], name)
    
    # Create output folder
    os.makedirs(output_folder, exist_ok=True)
    
    # Split the file into 2GB parts
    file_size = os.path.getsize(upload_path)
    part_size = 2 * 1024 * 1024 * 1024  # 2GB
    parts = math.ceil(file_size / part_size)
    part_files = []

    with open(upload_path, 'rb') as f:
        for i in range(parts):
            part_filename = f"{name}_part{i+1}{ext}"
            part_path = os.path.join(output_folder, part_filename)

            start_byte = i * part_size
            end_byte = min((i + 1) * part_size, file_size)
            bytes_to_read = end_byte - start_byte

            f.seek(start_byte)
            with open(part_path, 'wb') as part_file:
                remaining = bytes_to_read
                chunk_size = 1024 * 1024  # 1MB
                bytes_written = 0

                while remaining > 0:
                    chunk = f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    part_file.write(chunk)
                    remaining -= len(chunk)
                    bytes_written += len(chunk)
                    
                    # Update progress
                    progress = (start_byte + bytes_written) / file_size * 100
                    progress_dict[filename] = progress

            part_files.append(part_filename)

    # Clean up
    os.remove(upload_path)
    progress_dict[filename] = 100
    
    return jsonify({
        'success': True,
        'filename': filename,
        'split_files': part_files,
        'output_folder': output_folder,
        'folder_name': name
    })

@app.route('/progress/<filename>')
def progress(filename):
    prog = progress_dict.get(filename, 0)
    return jsonify({'progress': round(prog, 2)})

@app.route('/download/zip/<folder_name>')
def download_zip(folder_name):
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
    
    return response

@app.route('/download/separate/<folder_name>/<filename>')
def download_separate(folder_name, filename):
    folder_path = os.path.join(app.config['BASE_SPLIT_FOLDER'], folder_name)
    if not os.path.exists(folder_path):
        return jsonify({'success': False, 'error': 'Folder not found'})
    
    # Check if this is the last file to be downloaded
    files_in_folder = os.listdir(folder_path)
    is_last_file = len(files_in_folder) == 1 and files_in_folder[0] == filename
    
    response = send_from_directory(
        folder_path,
        filename,
        as_attachment=True
    )
    
    # Clean up if this is the last file
    if is_last_file:
        @response.call_on_close
        def cleanup():
            cleanup_folder(folder_path)
    
    return response

if __name__ == '__main__':
    app.run(debug=True)