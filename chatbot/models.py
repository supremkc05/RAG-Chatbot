from django.db import models
from django.contrib.auth.models import User
import json

class ChatSession(models.Model):
    """Model to store chat sessions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100, unique=True)
    video_id = models.CharField(max_length=50)
    video_url = models.URLField()
    title = models.CharField(max_length=255, blank=True)
    is_processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Session {self.session_id} - {self.video_id}"

class VideoTranscript(models.Model):
    """Model to store video transcripts"""
    session = models.OneToOneField(ChatSession, on_delete=models.CASCADE, related_name='transcript')
    raw_transcript = models.JSONField()
    full_text = models.TextField()
    chunk_count = models.IntegerField(default=0)
    embeddings_created = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Transcript for {self.session.video_id}"

class ChatMessage(models.Model):
    """Model to store chat messages"""
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    question = models.TextField()
    answer = models.TextField()
    context_used = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"Message in {self.session.session_id} at {self.timestamp}"

class ProcessingStatus(models.Model):
    """Model to track processing status"""
    session = models.OneToOneField(ChatSession, on_delete=models.CASCADE, related_name='processing_status')
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('fetching', 'Fetching Transcript'),
        ('processing', 'Processing Text'),
        ('embedding', 'Creating Embeddings'),
        ('completed', 'Completed'),
        ('error', 'Error')
    ], default='pending')
    progress_percentage = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Status: {self.status} ({self.progress_percentage}%)"
