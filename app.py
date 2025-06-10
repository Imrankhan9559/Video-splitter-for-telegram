import os
import math
from flask import Flask, render_template, request, redirect, send_from_directory, jsonify
from werkzeug.utils import secure_filename
import time

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['BASE_SPLIT_FOLDER'] = os.path.expanduser('~/Downloads/video_splitter')
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov', 'mkv'}

# Create directories if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['BASE_SPLIT_FOLDER'], exist_ok=True)

# Global dictionary to store progress
progress_dict = {}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def split_video(filepath, output_folder):
    filename = os.path.basename(filepath)
    name, ext = os.path.splitext(filename)
    
    # Create video-specific folder
    video_folder = os.path.join(output_folder, name)
    os.makedirs(video_folder, exist_ok=True)
    
    file_size = os.path.getsize(filepath)
    part_size = 2 * 1024 * 1024 * 1024  # 2GB
    
    parts = math.ceil(file_size / part_size)
    part_files = []

    with open(filepath, 'rb') as f:
        for i in range(parts):
            part_filename = f"{i+1} {name}{ext}"
            part_path = os.path.join(video_folder, part_filename)

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

            part_files.append(part_path)

    progress_dict[filename] = 100  # ensure it's 100% at end
    return part_files

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(upload_path)
            return jsonify({'success': True, 'filename': filename})
    
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    filename = request.form['filename']
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    part_files = split_video(upload_path, app.config['BASE_SPLIT_FOLDER'])

    os.remove(upload_path)
    progress_dict.pop(filename, None)

    return jsonify({
        'success': True,
        'filename': filename,
        'split_files': [os.path.basename(f) for f in part_files],
        'output_folder': os.path.join(app.config['BASE_SPLIT_FOLDER'], os.path.splitext(filename)[0])
    })

@app.route('/progress/<filename>')
def progress(filename):
    prog = progress_dict.get(filename, 0)
    return jsonify({'progress': round(prog, 2)})

@app.route('/downloads/<path:filename>')
def download_file(filename):
    folder, file = os.path.split(filename)
    return send_from_directory(os.path.join(app.config['BASE_SPLIT_FOLDER'], folder), file, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
