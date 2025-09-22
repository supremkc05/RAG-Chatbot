# YouTube Transcript Chatbot

A Django web application that allows users to chat with YouTube videos using AI. The application fetches video transcripts, processes them using LangChain, and enables users to ask questions about the video content using Google's Gemini AI.

## Features

- **URL Input**: Users can enter any YouTube video URL
- **Async Processing**: Video transcripts are processed in the background using Celery
- **Real-time Status**: Users see processing progress in real-time
- **Question Blocking**: Users cannot ask questions until processing is complete
- **Multiple Questions**: Once processed, users can ask unlimited questions
- **Chat History**: All conversations are saved and can be revisited
- **Modern UI**: Clean, responsive interface built with Tailwind CSS

## Technology Stack

- **Backend**: Django 5.0.6
- **AI/ML**: LangChain, Google Gemini (gemini-1.5-flash, embedding-001)
- **Vector Store**: FAISS
- **Task Queue**: Celery with Redis
- **Frontend**: HTML5, Tailwind CSS, JavaScript
- **Database**: SQLite (development) / PostgreSQL (production)

## Prerequisites

- Python 3.8+
- Redis server
- Google API key for Gemini

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd youtube_chatbot
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your Google API key:
   ```
   GOOGLE_API_KEY=your_google_api_key_here
   ```

5. **Run migrations**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create superuser** (optional):
   ```bash
   python manage.py createsuperuser
   ```

## Running the Application

### Development Mode

1. **Start Redis server**:
   ```bash
   redis-server
   ```

2. **Start Celery worker** (in a new terminal):
   ```bash
   celery -A youtube_chatbot worker --loglevel=info
   ```

3. **Start Django development server** (in another terminal):
   ```bash
   python manage.py runserver
   ```

4. **Access the application**:
   Open http://127.0.0.1:8000 in your browser

## Usage

1. **Enter YouTube URL**: Paste any YouTube video URL on the home page
2. **Wait for Processing**: The system will:
   - Fetch the video transcript
   - Split it into chunks
   - Create embeddings using Google's embedding model
   - Set up the Q&A system
3. **Ask Questions**: Once processing is complete, you can ask questions about the video
4. **View History**: All your conversations are saved and accessible

## Project Structure

```
youtube_chatbot/
├── chatbot/                 # Main Django app
│   ├── models.py           # Database models
│   ├── views.py            # API endpoints and views
│   ├── services.py         # Core transcript processing logic
│   ├── tasks.py            # Celery async tasks
│   ├── urls.py             # URL routing
│   ├── admin.py            # Django admin configuration
│   └── templates/          # HTML templates
├── youtube_chatbot/        # Django project settings
│   ├── settings.py         # Project configuration
│   ├── celery.py          # Celery configuration
│   └── urls.py            # Main URL routing
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
└── README.md              # This file
```

## API Endpoints

- `POST /api/create-session/`: Create a new chat session
- `GET /api/status/<session_id>/`: Get processing status
- `POST /api/ask/<session_id>/`: Ask a question
- `GET /api/history/<session_id>/`: Get chat history

## Models

- **ChatSession**: Stores session information and video details
- **VideoTranscript**: Stores processed transcript data
- **ChatMessage**: Stores Q&A pairs
- **ProcessingStatus**: Tracks processing progress

## Configuration

### Google API Setup

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Add it to your `.env` file

### Redis Configuration

By default, the app connects to `redis://localhost:6379/0`. You can modify this in `settings.py`:

```python
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
```

## Production Deployment

1. **Set environment variables**:
   - `DEBUG=False`
   - `ALLOWED_HOSTS=your-domain.com`
   - `GOOGLE_API_KEY=your-api-key`

2. **Use PostgreSQL**:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.postgresql',
           'NAME': 'your_db_name',
           'USER': 'your_db_user',
           'PASSWORD': 'your_db_password',
           'HOST': 'localhost',
           'PORT': '5432',
       }
   }
   ```

3. **Configure static files**:
   ```bash
   python manage.py collectstatic
   ```

4. **Use production WSGI server** (e.g., Gunicorn):
   ```bash
   gunicorn youtube_chatbot.wsgi:application
   ```

## Troubleshooting

### Common Issues

1. **"No transcript available"**: Some videos don't have transcripts or have them disabled
2. **Redis connection error**: Make sure Redis server is running
3. **Google API errors**: Check your API key and quotas
4. **Celery not processing**: Ensure Celery worker is running

### Logs

Check Django logs in `django.log` and Celery logs in the terminal where the worker is running.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request



## Support

For issues and questions, please create an issue in the GitHub repository.
