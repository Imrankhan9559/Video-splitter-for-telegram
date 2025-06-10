# Mysticmovies - Video Splitter

- A local Flask-based web application to split video files into two parts, each around 2GB (or half the file size), and save them in your Downloads folder.
- This Application is Mainly Use to upload Files in telegram by split the video into two parts and send it to the telegram using Non Premium Membership Account.

## Features
- Stylish animated user interface.
- Automatically splits any video into 2 parts.
- Names parts like `1 Filename` and `2 Filename`.
- Stores them in `~/Downloads/video_splitter/{Video Name}`.

## Project Structure
video_splitter/
├── app.py
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── script.js
└── requirements.txt

## Hosting Locally
1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python app.py
```

3. Open in browser:
```
http://localhost:5000
```

## Creator
Mysticmovies  
Website: [https://mysticmovies.site](https://mysticmovies.site)
