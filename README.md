# VerifAI - AI-Powered Fact-Checking System

VerifAI is a comprehensive fact-checking platform that leverages AI to analyze the credibility of information across multiple platforms including direct text input, Reddit posts, and WhatsApp messages.

## Features

- AI-powered credibility analysis using Mistral-7B model
- Cross-referencing with trusted sources
- Multi-platform support (web, Reddit, WhatsApp)
- Detailed assessment reports with reasoning
- Source verification from reputable domains

## Prerequisites

Before you begin, ensure you have the following:

- Python 3.8 or higher
- pip package manager
- A Hugging Face API key
- A Serper API key (for Google search)
- Twilio account (for WhatsApp integration)
- Reddit API credentials (for Reddit integration)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/verifai.git
cd verifai
```

2. Create and activate a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory with your API keys:

```env
HUGGINGFACE_API_KEY=your_huggingface_api_key
SERPER_API_KEY=your_serper_api_key
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=your_twilio_whatsapp_number
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=your_reddit_user_agent
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password
```

## Running the Application

Start the FastAPI server:

```bash
uvicorn backend:app --host 0.0.0.0 --port 5000
```

The application will be available at `http://localhost:5000`

## Usage

### Web Interface
1. Access the web interface at `http://localhost:5000`
2. Choose your verification method:
   - Direct text input
   - Reddit post URL
   - WhatsApp integration

### WhatsApp Integration
1. Send a message to your Twilio WhatsApp number with the text you want to verify
2. The system will respond with a fact-check analysis

### API Endpoints
- `POST /check` - Verify text directly
- `POST /reddit` - Verify a Reddit post
- `POST /whatsapp` - WhatsApp webhook endpoint

## Project Structure

```
verifai/
├── backend.py            # Main FastAPI application
├── requirements.txt      # Python dependencies
├── static/               # Static files (CSS, JS, images)
├── templates/            # HTML templates
│   ├── index.html        # Main interface
│   ├── result.html       # Results page
│   ├── whatsapp.html     # WhatsApp integration page
│   └── whatsapp_result.html # WhatsApp results page
└── .env                  # Environment variables
```

## Configuration

You can modify the following aspects of the application:

- **Trusted Sources**: Edit the `TRUSTED_DOMAINS` list in `backend.py`
- **AI Model**: Change the `HF_API_URL` in `backend.py` to use a different model
- **Styling**: Modify the CSS in the HTML templates

## Troubleshooting

- If you get API errors, verify your API keys in the `.env` file
- For WhatsApp issues, check your Twilio account settings
- For Reddit issues, ensure your API credentials are correct and have proper permissions

## License

This project is licensed under the MIT License. See the LICENSE file for details.

---

**Note**: This application uses third-party APIs which may have usage limits or costs associated with them. Please review the terms of service for each service before deploying in production.
