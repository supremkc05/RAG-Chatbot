from django.contrib import admin
from .models import ChatSession, VideoTranscript, ChatMessage, ProcessingStatus

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'video_id', 'is_processed', 'created_at']
    list_filter = ['is_processed', 'created_at']
    search_fields = ['session_id', 'video_id', 'video_url']
    readonly_fields = ['session_id', 'created_at', 'updated_at']

@admin.register(VideoTranscript)
class VideoTranscriptAdmin(admin.ModelAdmin):
    list_display = ['session', 'chunk_count', 'embeddings_created', 'created_at']
    list_filter = ['embeddings_created', 'created_at']
    readonly_fields = ['created_at']

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'question_preview', 'timestamp']
    list_filter = ['timestamp']
    search_fields = ['question', 'answer']
    readonly_fields = ['timestamp']
    
    def question_preview(self, obj):
        return obj.question[:50] + "..." if len(obj.question) > 50 else obj.question
    question_preview.short_description = 'Question'

@admin.register(ProcessingStatus)
class ProcessingStatusAdmin(admin.ModelAdmin):
    list_display = ['session', 'status', 'progress_percentage', 'updated_at']
    list_filter = ['status', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
