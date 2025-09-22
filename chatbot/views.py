from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
import json
import uuid
from .models import ChatSession, VideoTranscript, ChatMessage, ProcessingStatus
from .services import YouTubeTranscriptProcessor
try:
    from .tasks import process_video_async
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
import logging

logger = logging.getLogger(__name__)

class HomeView(View):
    """Main page view"""
    def get(self, request):
        recent_sessions = ChatSession.objects.filter(is_processed=True)[:5]
        return render(request, 'chatbot/index.html', {'recent_sessions': recent_sessions})

class ChatView(View):
    """Chat interface view"""
    def get(self, request, session_id):
        session = get_object_or_404(ChatSession, session_id=session_id)
        messages = session.messages.all()
        return render(request, 'chatbot/chat.html', {
            'session': session,
            'messages': messages
        })

@method_decorator(csrf_exempt, name='dispatch')
class CreateSessionView(View):
    """Create a new chat session"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            video_url = data.get('video_url', '').strip()
            
            if not video_url:
                return JsonResponse({'success': False, 'error': 'Video URL is required'})
            
            # Try to initialize the processor to check for configuration issues
            try:
                processor = YouTubeTranscriptProcessor()
            except Exception as e:
                logger.error(f"Failed to initialize processor: {str(e)}")
                return JsonResponse({'success': False, 'error': f'Configuration error: {str(e)}'})
            
            video_id = processor.extract_video_id(video_url)
            
            if not video_id:
                return JsonResponse({'success': False, 'error': 'Invalid YouTube URL. Please provide a valid YouTube video URL.'})
            
            # Validate video accessibility before creating session
            logger.info(f"Validating accessibility for video: {video_id}")
            accessibility = processor.validate_video_accessibility(video_id)
            if not accessibility['accessible']:
                return JsonResponse({'success': False, 'error': accessibility['message']})
            
            # Create session
            session_id = str(uuid.uuid4())
            session = ChatSession.objects.create(
                session_id=session_id,
                video_id=video_id,
                video_url=video_url,
                user=request.user if request.user.is_authenticated else None
            )
            
            # Create processing status
            ProcessingStatus.objects.create(
                session=session,
                status='pending'
            )
            
            # Start processing (async if Celery available, sync if not)
            if CELERY_AVAILABLE:
                try:
                    process_video_async.delay(session.id)
                except Exception as e:
                    logger.error(f"Celery error, falling back to sync: {str(e)}")
                    self._process_video_sync(session.id)
            else:
                # Process synchronously for testing without Celery
                self._process_video_sync(session.id)
            
            return JsonResponse({
                'success': True,
                'session_id': session_id,
                'video_id': video_id
            })
            
        except Exception as e:
            logger.error(f"Error creating session: {str(e)}")
            return JsonResponse({'success': False, 'error': f'Failed to create session: {str(e)}'})
    
    def _process_video_sync(self, session_id):
        """Synchronous video processing for when Celery is not available"""
        try:
            session = ChatSession.objects.get(id=session_id)
            status = session.processing_status
            
            # Update status to fetching
            status.status = 'fetching'
            status.progress_percentage = 10
            status.save()
            
            try:
                processor = YouTubeTranscriptProcessor()
            except Exception as e:
                logger.error(f"Failed to initialize processor: {str(e)}")
                status.status = 'error'
                status.error_message = f"Configuration error: {str(e)}"
                status.save()
                return
            
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
            
        except Exception as e:
            logger.error(f"Error processing video for session {session_id}: {str(e)}")
            try:
                status = ProcessingStatus.objects.get(session_id=session_id)
                status.status = 'error'
                status.error_message = str(e)
                status.save()
            except:
                pass

@method_decorator(csrf_exempt, name='dispatch')
class AskQuestionView(View):
    """Handle question asking"""
    
    def post(self, request, session_id):
        try:
            session = get_object_or_404(ChatSession, session_id=session_id)
            
            if not session.is_processed:
                return JsonResponse({
                    'success': False, 
                    'error': 'Video is still being processed. Please wait.'
                })
            
            data = json.loads(request.body)
            question = data.get('question', '').strip()
            
            if not question:
                return JsonResponse({'success': False, 'error': 'Question is required'})
            
            # Get the transcript processor (in production, you'd cache this)
            processor = YouTubeTranscriptProcessor()
            
            # Load the transcript and recreate the vector store
            transcript = session.transcript
            transcript_result = processor.process_transcript(transcript.raw_transcript)
            
            if not transcript_result['success']:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to load transcript data'
                })
            
            # Ask the question
            result = processor.ask_question(question)
            
            if result['success']:
                # Save the message
                message = ChatMessage.objects.create(
                    session=session,
                    question=question,
                    answer=result['answer'],
                    context_used=result.get('context', '')
                )
                
                return JsonResponse({
                    'success': True,
                    'answer': result['answer'],
                    'message_id': message.id
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result['error']
                })
                
        except Exception as e:
            logger.error(f"Error asking question: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Failed to process question'})

class SessionStatusView(View):
    """Get session processing status"""
    
    def get(self, request, session_id):
        try:
            session = get_object_or_404(ChatSession, session_id=session_id)
            status = session.processing_status
            
            return JsonResponse({
                'success': True,
                'status': status.status,
                'progress': status.progress_percentage,
                'is_processed': session.is_processed,
                'error': status.error_message if status.status == 'error' else None
            })
            
        except Exception as e:
            logger.error(f"Error getting session status: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Failed to get status'})

class ChatHistoryView(View):
    """Get chat history for a session"""
    
    def get(self, request, session_id):
        try:
            session = get_object_or_404(ChatSession, session_id=session_id)
            messages = session.messages.all()
            
            message_data = [
                {
                    'id': msg.id,
                    'question': msg.question,
                    'answer': msg.answer,
                    'timestamp': msg.timestamp.isoformat()
                }
                for msg in messages
            ]
            
            return JsonResponse({
                'success': True,
                'messages': message_data,
                'session_info': {
                    'video_id': session.video_id,
                    'video_url': session.video_url,
                    'is_processed': session.is_processed
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting chat history: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Failed to get chat history'})
