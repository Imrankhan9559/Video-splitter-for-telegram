
# Video Splitter Application

This application allows users to upload large video files and split them into smaller parts (up to 2GB each) for easier sharing and downloading. The solution uses Flask for the backend and FFmpeg for proper video splitting.

## Features

- Upload large video files (up to 100GB)
- Split videos into 2GB segments while maintaining playability
- Download split videos as a ZIP archive or individual files
- Automatic cleanup of files when:
  - User refreshes the page
  - User closes the page
  - User uploads a new video
  - Files are older than 1 hour
- Real-time progress tracking
- Session-based file management

## Requirements

### System Requirements

- Python 3.7+
- FFmpeg installed system-wide

#### Install FFmpeg

- **Windows**: [Download FFmpeg](https://ffmpeg.org/download.html)
- **macOS**: `brew install ffmpeg`
- **Linux (Ubuntu/Debian)**: `sudo apt install ffmpeg`
- **Linux (CentOS/RHEL)**: `sudo yum install ffmpeg`

### Python Packages

Listed in `requirements.txt`:

```
Flask==3.0.2
Werkzeug==3.0.1
ffmpeg-python==0.2.0
Flask-Session==0.8.1
```

## Installation

Clone the repository:

```bash
git clone https://github.com/yourusername/video-splitter.git
cd video-splitter
```

Create and activate a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate    # Windows
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Set up required directories:

```bash
mkdir -p uploads
mkdir -p ~/Downloads/video_splitter
```

## Usage

### Running the Application

```bash
python app.py
```

The application will be accessible at: [http://localhost:5000](http://localhost:5000)

### Using the Web Interface

1. Open the URL in your browser
2. Click "Choose File" to select a video file
3. Click "Upload" to upload the file to the server
4. The video will be automatically split into 2GB parts

Download options:

- "Download All as ZIP" to get all parts in a ZIP archive
- Click individual part names to download them separately

### Automatic Cleanup

Files are automatically cleaned when:

- You refresh the page
- You close the browser
- You upload a new video
- Files are older than 1 hour

No manual cleanup is needed

## API Endpoints

### Upload File

- **URL**: `/upload`
- **Method**: POST
- **Parameters**: `file` (video file)
- **Response**:

```json
{"success": true, "filename": "example.mp4"}
```

### Process Video

- **URL**: `/process`
- **Method**: POST
- **Parameters**: `filename` (name of uploaded file)
- **Response**:

```json
{
  "success": true,
  "filename": "example.mp4",
  "split_files": ["example_part1.mp4", "example_part2.mp4"],
  "output_folder": "/path/to/output",
  "folder_name": "example"
}
```

### Check Progress

- **URL**: `/progress/<filename>`
- **Method**: GET
- **Response**:

```json
{"progress": 45.23}
```

### Download ZIP

- **URL**: `/download/zip/<folder_name>`
- **Method**: GET
- **Response**: ZIP file download

### Download Individual File

- **URL**: `/download/separate/<folder_name>/<filename>`
- **Method**: GET
- **Response**: Video file download

## File Structure

```
video-splitter/
├── app.py                # Main application code
├── requirements.txt      # Python dependencies
├── uploads/              # Temporary upload directory
├── templates/
│   └── index.html        # Main interface template
├── venv/                 # Virtual environment (created)
└── ~/Downloads/video_splitter/ # Output directory for split videos
```

## Notes

- **Large File Support**: The application can handle files up to 100GB
- **Supported Formats**: MP4 and other common formats supported by FFmpeg
