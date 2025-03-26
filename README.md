# Mill Test Certificate Analyzer

A Flask web application that analyzes Mill Test Certificates (MTCs) using natural language processing techniques to extract and structure data, check compliance, and provide useful insights.

## Features

- Upload and process Mill Test Certificates in PDF format
- Automatically extract structured data from certificates
- Display detailed chemical composition and mechanical properties
- Check compliance against industry standards
- Present comprehensive analysis with summary view
- Query the data for specific information
- Store and retrieve historical certificate data

## Getting Started

### Prerequisites

- Python 3.8+
- pip
- Virtual environment (recommended)

### Installation

1. Clone the repository
```bash
git clone https://github.com/your-username/mill-test-certificate-analyzer.git
cd mill-test-certificate-analyzer
```

2. Create and activate a virtual environment (recommended)
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install the required dependencies
```bash
pip install -r requirements.txt
```

4. Set up environment variables
Create a `.env` file in the project root directory with the following content:
```
OPENAI_API_KEY=your_openai_api_key
FLASK_APP=app.py
FLASK_ENV=development
```

### Running the Application

1. Start the Flask server
```bash
python app.py
```

2. Open a web browser and navigate to `http://127.0.0.1:8080`

## Usage

### Uploading a Certificate

1. Navigate to the home page
2. Click on the "Upload Mill Test Certificate" button
3. Select a PDF file containing a Mill Test Certificate
4. Click "Upload" to process the certificate

### Viewing Analysis

After uploading a certificate, you'll be redirected to the analysis page, which includes:

- Certificate Summary - An overview of key information and compliance status
- Chemical Composition - Detailed breakdown of material chemical properties
- Mechanical Properties - Strength, hardness, and other mechanical test results
- Additional Information - Other relevant certificate data

### Querying Data

You can query the extracted data using natural language:
1. Navigate to the analysis page for a certificate
2. Enter your question in the query box (e.g., "What is the carbon content?")
3. View the response based on the certificate data

## Deployment

### Deploying with Jupyter Lab/Notebook

You can deploy and run this application using Jupyter Lab or Jupyter Notebook for a more interactive development environment:

1. Install Jupyter Lab (if not already installed)
```bash
pip install jupyterlab
```

2. Start Jupyter Lab
```bash
jupyter lab
```

3. Create a new notebook and run the following code:
```python
import subprocess
import os
import webbrowser
from IPython.display import display, HTML

# Set environment variables (if needed)
os.environ["FLASK_APP"] = "app.py"
os.environ["FLASK_ENV"] = "development"

# Start the Flask application in the background
flask_process = subprocess.Popen(["python", "app.py"])

# Display the application URL with a clickable link
display(HTML('<a href="http://127.0.0.1:8080" target="_blank">Open Mill Test Certificate Analyzer</a>'))

# Keep the notebook cell running to maintain the Flask server
# Press the stop button when you want to shut down the server

# When shutting down, ensure the Flask server is terminated
# flask_process.terminate()
```

4. The notebook will display a clickable link to open the application in a new tab

### Docker Deployment

For containerized deployment:

1. Build the Docker image
```bash
docker build -t mtc-analyzer .
```

2. Run the container
```bash
docker run -p 8080:8080 -e OPENAI_API_KEY=your_openai_api_key mtc-analyzer
```

3. Access the application at `http://localhost:8080`

## Project Structure

```
mill-test-certificate-analyzer/
├── app.py                     # Main Flask application
├── templates/                 # HTML templates
│   ├── analysis.html          # Analysis page template
│   ├── base.html              # Base template with common elements
│   ├── home.html              # Home page template
│   └── ...
├── static/                    # Static assets
│   ├── css/                   # CSS stylesheets
│   ├── js/                    # JavaScript files
│   └── images/                # Image assets
├── processed_jobs/            # Directory for processed certificate data
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables (not in version control)
├── .gitignore                 # Git ignore file
└── README.md                  # Project documentation
```

## Development

### Adding New Features

To add new features:

1. Create a feature branch
```bash
git checkout -b feature/your-feature-name
```

2. Implement your changes
3. Test thoroughly
4. Submit a pull request

### Running Tests

```bash
pytest tests/
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenAI for providing the language model capabilities
- Flask for the web framework
- Contributors and users of the application 

## Deployment on Render.com (Free Tier)

### Prerequisites

- A [Render.com](https://render.com/) account
- A [GitHub](https://github.com/) account

### Deployment Steps

1. **Fork this repository to your GitHub account**

2. **Sign up for Render.com**
   - Go to [render.com](https://render.com/)
   - Sign up for a free account

3. **Create a new Web Service**
   - Click "New" and select "Web Service"
   - Connect your GitHub repository
   - Select the repository containing this application

4. **Configure the Web Service**
   - Name: mill-test-analyzer (or your preferred name)
   - Environment: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --config gunicorn.conf.py`

5. **Add Environment Variables**
   - LLM_WHISPERER_API_KEY: Your LLMWhisperer API key
   - LLM_WHISPERER_API_URL: LLMWhisperer API URL
   - DEEPSEEK_API_KEY: Your DeepSeek API key
   - DEEPSEEK_BASE_URL: DeepSeek base URL
   - SECRET_KEY: A secure random string for Flask sessions

6. **Add Persistent Storage**
   - Navigate to the "Disks" tab
   - Create a new disk:
     - Name: mtc-storage
     - Mount Path: /var/data
     - Size: 1 GB (minimum)

7. **Deploy the Service**
   - Click "Create Web Service"
   - Render will automatically deploy your application

8. **Access Your Application**
   - Once deployment is complete, you can access your application at the URL provided by Render

## Local Development

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run the application: `python app.py`
4. Access the application at [http://localhost:8080](http://localhost:8080)

## License

This project is licensed under the MIT License - see the LICENSE file for details. 