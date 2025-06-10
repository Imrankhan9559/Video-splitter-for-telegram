document.getElementById('uploadForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const fileInput = document.getElementById('file');
    const filename = fileInput.files[0].name;

    document.getElementById('currentFilename').textContent = filename;
    document.getElementById('progressContainer').style.display = 'block';

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    fetch('/', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            processVideo(data.filename);
        } else {
            alert('Upload failed');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred during upload');
    });
});

function processVideo(filename) {
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');

    const pollInterval = setInterval(() => {
        fetch(`/progress/${encodeURIComponent(filename)}`)
        .then(res => res.json())
        .then(data => {
            const percent = Math.floor(data.progress);
            progressBar.style.width = percent + '%';
            progressText.textContent = percent + '%';
        });
    }, 500);

    fetch('/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `filename=${encodeURIComponent(filename)}`
    })
    .then(response => response.json())
    .then(data => {
        clearInterval(pollInterval);
        progressBar.style.width = '100%';
        progressText.textContent = '100%';
        showResults(data);
    })
    .catch(error => {
        clearInterval(pollInterval);
        console.error('Error:', error);
        alert('An error occurred during processing');
    });
}

function showResults(data) {
    document.getElementById('progressContainer').style.display = 'none';

    const resultContainer = document.getElementById('resultContainer');
    resultContainer.style.display = 'block';

    document.getElementById('resultFilename').textContent = data.filename;
    document.getElementById('partCount').textContent = data.split_files.length;
    document.getElementById('outputPath').textContent = data.output_folder;

    const fileList = document.getElementById('fileList');
    fileList.innerHTML = '';

    const folderName = data.filename.split('.')[0];
    data.split_files.forEach(file => {
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.href = `/downloads/${folderName}/${file}`;
        a.textContent = file;
        a.download = file;
        li.appendChild(a);
        fileList.appendChild(li);
    });
}

const fileInput = document.getElementById('file');
const fileNameDisplay = document.getElementById('file-name');
fileInput.addEventListener('change', function () {
    if (fileInput.files.length > 0) {
        fileNameDisplay.textContent = `Selected: ${fileInput.files[0].name}`;
    } else {
        fileNameDisplay.textContent = '';
    }
});