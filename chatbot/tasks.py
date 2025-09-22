try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    # Create a dummy decorator for when celery is not available
    def shared_task(bind=False):
        def decorator(func):
            return func
        return decorator

from django.utils import timezone
from .models import ChatSession, VideoTranscript, ProcessingStatus
from .services import YouTubeTranscriptProcessor
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def process_video_async(self, session_id):
    """Async task to process YouTube video transcript"""
    if not CELERY_AVAILABLE:
        logger.error("Celery not available, cannot process video asynchronously")
        return
        
    try:
        session = ChatSession.objects.get(id=session_id)
        status = session.processing_status
        
        # Update status to fetching
        status.status = 'fetching'
        status.progress_percentage = 10
        status.save()
        
        processor = YouTubeTranscriptProcessor()
        
        # Fetch transcript
        transcript_result = processor.fetch_transcript(session.video_id)
        
        if not transcript_result['success']:
            status.status = 'error'
            status.error_message = transcript_result['error']
            status.save()
            return
        
        # Update status to processing
        status.status = 'processing'
        status.progress_percentage = 40
        status.save()
        
        # Save raw transcript
        transcript = VideoTranscript.objects.create(
            session=session,
            raw_transcript=transcript_result['transcript'],
            full_text=''  # Will be filled after processing
        )
        
        # Process transcript and create embeddings
        status.status = 'embedding'
        status.progress_percentage = 70
        status.save()
        
        processing_result = processor.process_transcript(transcript_result['transcript'])
        
        if not processing_result['success']:
            status.status = 'error'
            status.error_message = processing_result['error']
            status.save()
            return
        
        # Update transcript with processed data
        transcript.full_text = processing_result['full_text']
        transcript.chunk_count = processing_result['chunk_count']
        transcript.embeddings_created = True
        transcript.save()
        
        # Mark session as processed
        session.is_processed = True
        session.save()
        
        # Update status to completed
        status.status = 'completed'
        status.progress_percentage = 100
        status.save()
        
        logger.info(f"Successfully processed video {session.video_id} for session {session.session_id}")
        
    except ChatSession.DoesNotExist:
        logger.error(f"Session {session_id} not found")
    except Exception as e:
        logger.error(f"Error processing video for session {session_id}: {str(e)}")
        try:
            status = ProcessingStatus.objects.get(session_id=session_id)
            status.status = 'error'
            status.error_message = str(e)
            status.save()
        except:
            pass
