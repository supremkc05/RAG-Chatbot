import os
import re
from typing import List, Optional, Dict, Any
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class YouTubeTranscriptProcessor:
    """Service class to handle YouTube transcript processing and Q&A"""
    
    def __init__(self):
        try:
            # Get Google API key from environment
            google_api_key = os.getenv('GOOGLE_API_KEY')
            if not google_api_key:
                raise ValueError("GOOGLE_API_KEY environment variable is not set")
            
            # Set the environment variable for Google AI
            os.environ['GOOGLE_API_KEY'] = google_api_key
            
            self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
            self.llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            self.vector_store = None
            self.retriever = None
            self.qa_chain = None
            
            logger.info("YouTubeTranscriptProcessor initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing YouTubeTranscriptProcessor: {str(e)}")
            raise
        
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
            r'youtube\.com\/embed\/([^&\n?#]+)',
            r'youtube\.com\/v\/([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                # Validate video ID format (YouTube video IDs are 11 characters)
                if len(video_id) == 11:
                    logger.info(f"Extracted video ID: {video_id} from URL: {url}")
                    return video_id
                else:
                    logger.warning(f"Invalid video ID length: {video_id}")
        
        logger.error(f"Could not extract video ID from URL: {url}")
        return None
    
    def validate_video_accessibility(self, video_id: str) -> Dict[str, Any]:
        """Check if video is accessible before processing"""
        try:
            # Try to get transcript using the instance method
            ytt_api = YouTubeTranscriptApi()
            fetched_transcript = ytt_api.fetch(video_id)
            raw_data = fetched_transcript.to_raw_data()
            if raw_data:
                return {'accessible': True, 'message': 'Video is accessible'}
            else:
                return {'accessible': False, 'message': 'No transcript available'}
        except Exception as e:
            error_msg = str(e).lower()
            if 'private' in error_msg or 'unavailable' in error_msg:
                return {'accessible': False, 'message': 'Video is private or unavailable'}
            elif 'disabled' in error_msg:
                return {'accessible': False, 'message': 'Transcripts are disabled for this video'}
            else:
                return {'accessible': False, 'message': f'Video access error: {str(e)}'}
    
    def fetch_transcript(self, video_id: str) -> Dict[str, Any]:
        """Fetch transcript from YouTube video"""
        try:
            logger.info(f"Attempting to fetch transcript for video ID: {video_id}")
            
            # Use the instance method that works
            ytt_api = YouTubeTranscriptApi()
            fetched_transcript = ytt_api.fetch(video_id)
            
            # Convert to raw data
            transcript_data = fetched_transcript.to_raw_data()
            
            if not transcript_data:
                return {
                    'success': False,
                    'error': "No transcript data returned from the API."
                }
            
            # Convert to the format expected by the application
            raw_data = []
            for entry in transcript_data:
                try:
                    raw_data.append({
                        'text': entry.get('text', ''),
                        'start': entry.get('start', 0),
                        'duration': entry.get('duration', 0)
                    })
                except Exception as e:
                    logger.warning(f"Skipping malformed transcript entry: {str(e)}")
                    continue
            
            if not raw_data:
                return {
                    'success': False,
                    'error': "Transcript was found but contained no usable text data."
                }
            
            logger.info(f"Successfully processed transcript for video {video_id} with {len(raw_data)} segments")
            return {
                'success': True,
                'transcript': raw_data,
                'language': 'auto-detected'  # The new API doesn't provide language info directly
            }
            
        except Exception as e:
            logger.error(f"Error fetching transcript for video {video_id}: {str(e)}")
            error_msg = str(e).lower()
            
            if 'transcript' in error_msg and 'disabled' in error_msg:
                return {
                    'success': False,
                    'error': "Transcripts are disabled for this video by the video owner."
                }
            elif 'private' in error_msg or 'unavailable' in error_msg:
                return {
                    'success': False,
                    'error': "This video is private, unavailable, or restricted."
                }
            elif 'not found' in error_msg:
                return {
                    'success': False,
                    'error': "No transcript is available for this video. This may be because the video is too new, has no captions, or captions are disabled."
                }
            else:
                return {
                    'success': False,
                    'error': f"Failed to fetch transcript: {str(e)}"
                }
    
    def process_transcript(self, transcript_data: List[Dict]) -> Dict[str, Any]:
        """Process transcript data into chunks and create embeddings"""
        try:
            # Combine all text segments
            full_text = ' '.join(segment['text'] for segment in transcript_data)
            
            # Split into chunks
            chunks = self.text_splitter.split_text(full_text)
            
            # Convert to Document objects
            from langchain_core.documents import Document
            documents = [Document(page_content=chunk) for chunk in chunks]
            
            # Create vector store with embeddings
            if len(documents) > 60:
                # Process in batches to avoid memory issues
                first_batch = documents[:60]
                remaining_batches = [documents[i:i+60] for i in range(60, len(documents), 60)]
                
                # Create initial vector store
                self.vector_store = FAISS.from_documents(first_batch, self.embeddings)
                
                # Add remaining batches
                for batch in remaining_batches:
                    if batch:  # Only process non-empty batches
                        batch_vector_store = FAISS.from_documents(batch, self.embeddings)
                        self.vector_store.merge_from(batch_vector_store)
            else:
                self.vector_store = FAISS.from_documents(documents, self.embeddings)
            
            # Create retriever
            self.retriever = self.vector_store.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 4}
            )
            
            # Set up the QA chain
            self._setup_qa_chain()
            
            return {
                'success': True,
                'full_text': full_text,
                'chunk_count': len(documents),
                'message': 'Transcript processed successfully'
            }
            
        except Exception as e:
            logger.error(f"Error processing transcript: {str(e)}")
            return {
                'success': False,
                'error': f"Error processing transcript: {str(e)}"
            }
    
    def _setup_qa_chain(self):
        """Set up the question-answering chain"""
        prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""
            You are a helpful assistant.
            Answer ONLY from the provided transcript context.
            If the context is insufficient, just say you don't know.
            
            Context: {context}
            
            Question: {question}
            
            Answer:
            """
        )
        
        def format_docs(retrieved_docs):
            return "\n\n".join(doc.page_content for doc in retrieved_docs)
        
        # Create the chain using RunnableParallel
        parallel_chain = RunnableParallel({
            'context': self.retriever | RunnableLambda(format_docs),
            'question': RunnablePassthrough()
        })
        
        parser = StrOutputParser()
        self.qa_chain = parallel_chain | prompt_template | self.llm | parser
    
    def ask_question(self, question: str) -> Dict[str, Any]:
        """Ask a question about the processed transcript"""
        if not self.qa_chain:
            return {
                'success': False,
                'error': 'No transcript has been processed yet'
            }
        
        try:
            # Get the answer using the chain
            answer = self.qa_chain.invoke(question)
            
            # Get the context that was used
            retrieved_docs = self.retriever.invoke(question)
            context_used = "\n\n".join(doc.page_content for doc in retrieved_docs)
            
            return {
                'success': True,
                'answer': answer,
                'context': context_used
            }
            
        except Exception as e:
            logger.error(f"Error answering question: {str(e)}")
            return {
                'success': False,
                'error': f"Error answering question: {str(e)}"
            }
    
    def is_ready(self) -> bool:
        """Check if the processor is ready to answer questions"""
        return self.qa_chain is not None and self.retriever is not None
