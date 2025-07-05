import base64
import os
import json
import tempfile
import time
from pathlib import Path
from PIL import Image
import requests
import uuid
import shutil
import platform
import streamlit as st

# Try to import optional dependencies with fallbacks
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Try to import PDF processing libraries
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    try:
        import fitz  # PyMuPDF
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False

# Try to import speech recognition and audio processing
try:
    import speech_recognition as sr
    import pyaudio
    import wave
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False

# Try to import Google Cloud Speech (alternative to speech_recognition)
try:
    from google.cloud import speech
    import io
    GOOGLE_SPEECH_AVAILABLE = True
except ImportError:
    GOOGLE_SPEECH_AVAILABLE = False

# Configure Streamlit page
st.set_page_config(
    page_title="Auto File Analyzer with Voice",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded"
)

class VoiceFileAnalyzer:
    def __init__(self):
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "AIzaSyDFgcA8F1RD0t0UmMbomQ54dHoGPZRT0ok")
        
        if GEMINI_AVAILABLE:
            try:
                self.gemini_client = genai.Client(api_key=self.gemini_api_key)
                self.model = "gemini-2.0-flash"
            except Exception as e:
                st.error(f"Failed to initialize Gemini client: {e}")
                self.gemini_client = None
        else:
            self.gemini_client = None
            
        self.analysis_history = []
        self.setup_temp_directory()
        self.setup_voice_recognition()
        
    def setup_temp_directory(self):
        """Create temporary directory for processing"""
        self.temp_dir = Path(tempfile.gettempdir()) / "voice_analyzer"
        self.temp_dir.mkdir(exist_ok=True)
        
    def setup_voice_recognition(self):
        """Setup voice recognition components"""
        self.recognizer = None
        self.microphone = None
        
        if SPEECH_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                
                # Adjust for ambient noise
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    
            except Exception as e:
                st.warning(f"Voice recognition setup warning: {e}")
                
    def record_audio_from_microphone(self, duration=5):
        """Record audio from microphone"""
        if not SPEECH_AVAILABLE or not self.recognizer or not self.microphone:
            return None, "Speech recognition not available"
            
        try:
            with self.microphone as source:
                st.info(f"🎤 Listening for {duration} seconds... Speak now!")
                
                # Create a placeholder for real-time feedback
                audio_placeholder = st.empty()
                
                # Record audio with timeout
                audio = self.recognizer.listen(
                    source, 
                    timeout=duration, 
                    phrase_time_limit=duration
                )
                
                audio_placeholder.success("🎤 Recording completed!")
                return audio, None
                
        except sr.WaitTimeoutError:
            return None, "No speech detected. Please try again."
        except Exception as e:
            return None, f"Recording error: {str(e)}"
    
    def transcribe_audio_with_google(self, audio_data):
        """Convert audio to text using Google Speech Recognition"""
        if not SPEECH_AVAILABLE:
            return "Speech recognition not available. Please install: pip install SpeechRecognition pyaudio"
        
        try:
            # Use Google Speech Recognition (free)
            text = self.recognizer.recognize_google(audio_data)
            return text
            
        except sr.UnknownValueError:
            return "Could not understand the audio. Please speak clearly and try again."
        except sr.RequestError as e:
            return f"Error with Google Speech Recognition service: {e}"
        except Exception as e:
            return f"Error processing audio: {str(e)}"
    
    def transcribe_audio_with_google_cloud(self, audio_file_path):
        """Convert audio to text using Google Cloud Speech API"""
        if not GOOGLE_SPEECH_AVAILABLE:
            return "Google Cloud Speech not available."
            
        try:
            client = speech.SpeechClient()
            
            with io.open(audio_file_path, "rb") as audio_file:
                content = audio_file.read()
                
            audio = speech.RecognitionAudio(content=content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code="en-US",
            )
            
            response = client.recognize(config=config, audio=audio)
            
            if response.results:
                return response.results[0].alternatives[0].transcript
            else:
                return "No speech detected in audio."
                
        except Exception as e:
            return f"Google Cloud Speech error: {str(e)}"
    
    def save_audio_to_file(self, audio_data, filename="recorded_audio.wav"):
        """Save audio data to file"""
        try:
            audio_file_path = self.temp_dir / filename
            with open(audio_file_path, "wb") as f:
                f.write(audio_data.get_wav_data())
            return str(audio_file_path)
        except Exception as e:
            return None
    
    def process_voice_command(self, voice_text):
        """Process voice command and extract filename/action"""
        voice_text = voice_text.lower().strip()
        
        # Enhanced patterns for file analysis commands
        patterns = {
            "analyze": ["analyze", "analyse", "process", "check", "examine", "review"],
            "document": ["document", "file", "pdf", "paper", "doc", "docx"],
            "summary": ["summary", "summarize", "overview", "brief", "outline"],
            "extract": ["extract", "find", "get", "pull", "retrieve"],
            "automation": ["automation", "automate", "robot", "automatic"],
            "search": ["search", "find", "locate", "look for"],
            "open": ["open", "load", "access"]
        }
        
        # Enhanced filename detection
        words = voice_text.split()
        potential_filename = None
        analysis_type = "Document Summary"  # default
        
        # Look for file extensions in speech
        common_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.doc', '.docx', '.txt', '.xlsx']
        for word in words:
            for ext in common_extensions:
                if ext.replace('.', '') in word:
                    potential_filename = word + ext if not word.endswith(ext) else word
                    break
            if potential_filename:
                break
        
        # Enhanced file pattern detection
        if not potential_filename:
            file_patterns = {
                "cover letter": "cover_letter.pdf",
                "resume": "resume.pdf", 
                "cv": "cv.pdf",
                "report": "report.pdf",
                "invoice": "invoice.pdf",
                "iqac": "iqac.pdf",
                "presentation": "presentation.pptx",
                "spreadsheet": "spreadsheet.xlsx",
                "contract": "contract.pdf",
                "proposal": "proposal.pdf",
                "thesis": "thesis.pdf",
                "assignment": "assignment.pdf"
            }
            
            for pattern, filename in file_patterns.items():
                if pattern in voice_text:
                    potential_filename = filename
                    break
        
        # Determine analysis type from voice command
        if any(word in voice_text for word in patterns["summary"]):
            analysis_type = "Document Summary"
        elif any(word in voice_text for word in patterns["extract"]):
            analysis_type = "Key Information Extraction"
        elif any(word in voice_text for word in patterns["automation"]):
            analysis_type = "Automation Opportunities"
        elif "content" in voice_text or "quality" in voice_text:
            analysis_type = "Content Analysis"
        
        # Calculate confidence based on detection success
        confidence = "high" if potential_filename else "medium" if any(word in voice_text for word in patterns["analyze"]) else "low"
        
        return {
            "filename": potential_filename,
            "analysis_type": analysis_type,
            "original_command": voice_text,
            "confidence": confidence,
            "detected_patterns": [key for key, values in patterns.items() if any(word in voice_text for word in values)]
        }
        
    def search_for_file(self, filename):
        """Enhanced file search with better coverage"""
        search_locations = []
        
        # Determine search locations based on platform
        if platform.system() == "Windows":
            username = os.getenv("USERNAME", "")
            search_locations = [
                Path.home() / "Downloads",
                Path.home() / "Downloads" / "Telegram Desktop",
                Path.home() / "Documents",
                Path.home() / "Desktop",
                Path("C:/Users") / username / "Downloads",
                Path("C:/Users") / username / "Documents",
                Path("C:/Users") / username / "Desktop",
                Path("D:/Downloads") if Path("D:/").exists() else None,
            ]
        elif platform.system() == "Darwin":  # macOS
            search_locations = [
                Path.home() / "Downloads",
                Path.home() / "Documents", 
                Path.home() / "Desktop",
                Path("/Applications"),
            ]
        else:  # Linux
            search_locations = [
                Path.home() / "Downloads",
                Path.home() / "Documents",
                Path.home() / "Desktop",
                Path("/tmp"),
            ]
        
        # Remove None values
        search_locations = [loc for loc in search_locations if loc is not None]
        
        found_files = []
        
        for location in search_locations:
            try:
                if not location.exists():
                    continue
                    
                # Search for exact filename
                exact_match = location / filename
                if exact_match.exists() and exact_match.is_file():
                    found_files.append(exact_match)
                
                # Search for files containing the filename (case-insensitive)
                try:
                    for file_path in location.iterdir():
                        if file_path.is_file() and filename.lower() in file_path.name.lower():
                            found_files.append(file_path)
                except (PermissionError, OSError):
                    continue
                
                # Search recursively in subdirectories (max 3 levels deep)
                try:
                    for file_path in location.rglob("*"):
                        if (file_path.is_file() and 
                            filename.lower() in file_path.name.lower() and 
                            len(file_path.parts) - len(location.parts) <= 3):
                            found_files.append(file_path)
                except (PermissionError, OSError):
                    continue
                    
            except (PermissionError, OSError):
                continue
        
        # Remove duplicates and sort by newest first
        unique_files = list({str(f): f for f in found_files}.values())
        
        try:
            unique_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        except (PermissionError, OSError):
            pass
        
        return unique_files[:15]  # Return top 15 matches
    
    def get_file_info(self, file_path):
        """Get comprehensive file information"""
        try:
            path = Path(file_path)
            stat = path.stat()
            
            return {
                "name": path.name,
                "size_mb": stat.st_size / 1024 / 1024,
                "size_bytes": stat.st_size,
                "modified": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
                "created": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_ctime)),
                "extension": path.suffix.lower(),
                "type": self.get_file_type(path.suffix.lower()),
                "parent_dir": str(path.parent)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_file_type(self, extension):
        """Determine file type from extension"""
        type_mapping = {
            '.pdf': 'PDF',
            '.doc': 'Word Document',
            '.docx': 'Word Document',
            '.txt': 'Text File',
            '.png': 'Image',
            '.jpg': 'Image',
            '.jpeg': 'Image',
            '.gif': 'Image',
            '.xlsx': 'Excel Spreadsheet',
            '.xls': 'Excel Spreadsheet',
            '.pptx': 'PowerPoint Presentation',
            '.ppt': 'PowerPoint Presentation'
        }
        return type_mapping.get(extension, 'Unknown')
    
    def extract_text_from_pdf(self, pdf_path):
        """Enhanced PDF text extraction"""
        try:
            text = ""
            
            # Try PyMuPDF first (better OCR support)
            if 'fitz' in globals():
                doc = fitz.open(pdf_path)
                for page_num, page in enumerate(doc):
                    page_text = page.get_text()
                    if page_text.strip():
                        text += f"\n--- Page {page_num + 1} ---\n{page_text}"
                doc.close()
                return text if text.strip() else "No text content found in PDF"
            
            # Fallback to PyPDF2
            if 'PyPDF2' in globals():
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page_num, page in enumerate(pdf_reader.pages):
                        page_text = page.extract_text()
                        if page_text.strip():
                            text += f"\n--- Page {page_num + 1} ---\n{page_text}"
                return text if text.strip() else "No text content found in PDF"
                
            return "PDF processing libraries not available."
            
        except Exception as e:
            return f"Error extracting text: {str(e)}"
    
    def analyze_with_gemini(self, content, file_info, analysis_type):
        """Enhanced Gemini AI analysis"""
        if not self.gemini_client:
            return "Gemini AI not available. Please check your configuration."
            
        try:
            # Build context-aware prompt
            file_context = f"""
            File Analysis Request:
            - File Name: {file_info['name']}
            - File Type: {file_info.get('type', 'Unknown')}
            - File Size: {file_info.get('size_mb', 0):.2f} MB
            - Last Modified: {file_info.get('modified', 'Unknown')}
            """
            
            if file_info.get("type") in ["PDF", "Word Document", "Text File"]:
                base_prompt = f"""
                {file_context}
                
                Document Content:
                {content[:10000]}  # Increased content limit
                
                Analysis Type: {analysis_type}
                """
            else:
                base_prompt = f"""
                {file_context}
                
                Analysis Type: {analysis_type}
                Note: This is a {file_info.get('type', 'file')} - analysis based on filename and metadata.
                """
            
            # Enhanced analysis prompts
            analysis_prompts = {
                "Document Summary": base_prompt + """
                
                Provide a comprehensive document analysis:
                1. **Document Type & Purpose**: What kind of document this is and its intended use
                2. **Executive Summary**: Key points and main message (2-3 sentences)
                3. **Content Structure**: How the document is organized
                4. **Key Information**: Important names, dates, numbers, and facts
                5. **Main Topics**: Primary subjects or themes discussed
                6. **Actionable Items**: Any tasks, deadlines, or next steps mentioned
                7. **Document Quality**: Completeness and professionalism assessment
                """,
                
                "Key Information Extraction": base_prompt + """
                
                Extract and categorize all important information:
                1. **Personal/Contact Information**: Names, emails, phone numbers, addresses
                2. **Dates & Deadlines**: All dates, timelines, and time-sensitive information
                3. **Financial Data**: Amounts, prices, costs, budgets, financial figures
                4. **Organizations & Companies**: Business names, institutions, departments
                5. **Technical Specifications**: Requirements, standards, technical details
                6. **Legal Information**: Contracts, agreements, terms, conditions
                7. **Action Items & Tasks**: Required actions, responsibilities, deliverables
                8. **References**: Citations, links, external documents mentioned
                """,
                
                "Automation Opportunities": base_prompt + """
                
                Identify comprehensive automation possibilities:
                1. **Data Entry Automation**: Information that could be auto-extracted and entered
                2. **Document Processing**: How this type of document could be automatically processed
                3. **Workflow Integration**: Systems and processes this could connect to
                4. **Repetitive Task Identification**: Manual tasks that could be automated
                5. **Template Opportunities**: Standardizable elements for future automation
                6. **API Integration Points**: Where this data could feed into other systems
                7. **Quality Assurance Automation**: Automated checks and validations possible
                8. **Cost-Benefit Analysis**: Potential time and cost savings from automation
                """,
                
                "Content Analysis": base_prompt + """
                
                Perform detailed content quality analysis:
                1. **Writing Quality**: Grammar, style, clarity, and professionalism
                2. **Content Completeness**: Missing information or incomplete sections
                3. **Structure Analysis**: Document organization and logical flow
                4. **Audience Appropriateness**: Suitability for intended audience
                5. **Technical Accuracy**: Correctness of technical information (if applicable)
                6. **Compliance Check**: Adherence to standards or requirements
                7. **Improvement Recommendations**: Specific suggestions for enhancement
                8. **Risk Assessment**: Potential issues or concerns identified
                """
            }
            
            prompt = analysis_prompts.get(analysis_type, base_prompt)
            
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ]
            
            response = self.gemini_client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="text/plain",
                    temperature=0.3,  # More focused responses
                    max_output_tokens=2048  # Longer responses
                )
            )
            
            return response.text
            
        except Exception as e:
            return f"Analysis error: {str(e)}"
    
    def log_analysis(self, file_path, analysis_type, success, result_length=0, voice_used=False):
        """Enhanced analysis logging"""
        self.analysis_history.append({
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "file_path": str(file_path),
            "file_name": Path(file_path).name,
            "analysis_type": analysis_type,
            "success": success,
            "result_length": result_length,
            "voice_command": voice_used,
            "session_id": str(uuid.uuid4())[:8]
        })

@st.cache_resource
def get_analyzer():
    return VoiceFileAnalyzer()

def create_voice_interface():
    """Create the voice input interface"""
    st.header("🎤 Voice-Controlled File Analysis")
    
    analyzer = get_analyzer()
    
    # Voice capability status
    col1, col2 = st.columns(2)
    with col1:
        if SPEECH_AVAILABLE and analyzer.recognizer:
            st.success("✅ Microphone Ready")
        else:
            st.error("❌ Voice Recognition Unavailable")
            st.caption("Install: pip install SpeechRecognition pyaudio")
    
    with col2:
        if GOOGLE_SPEECH_AVAILABLE:
            st.success("✅ Google Cloud Speech Available")
        else:
            st.info("ℹ️ Using Basic Speech Recognition")
    
    # Voice recording section
    if SPEECH_AVAILABLE and analyzer.recognizer:
        st.subheader("🎙️ Voice Commands")
        
        # Recording duration selector
        duration = st.slider("Recording duration (seconds):", 3, 15, 7)
        
        # Voice recording button
        if st.button("🎤 **START VOICE RECORDING**", type="primary", use_container_width=True):
            
            # Record audio
            with st.spinner(f"🎤 Recording for {duration} seconds..."):
                audio_data, error = analyzer.record_audio_from_microphone(duration)
            
            if error:
                st.error(f"❌ Recording failed: {error}")
                return
            
            if audio_data:
                st.success("🎤 Recording completed!")
                
                # Transcribe audio
                with st.spinner("🧠 Converting speech to text..."):
                    transcribed_text = analyzer.transcribe_audio_with_google(audio_data)
                
                if transcribed_text and not transcribed_text.startswith("Error") and not transcribed_text.startswith("Could not"):
                    st.success(f"🎤 **Voice Command Recognized:**")
                    st.info(f"**\"{transcribed_text}\"**")
                    
                    # Process voice command
                    with st.spinner("🤖 Processing voice command..."):
                        command_result = analyzer.process_voice_command(transcribed_text)
                    
                    # Display command analysis
                    st.markdown("### 🧩 Command Analysis")
                    
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("🎯 Confidence", command_result['confidence'].title())
                    with col_b:
                        st.metric("📄 Detected File", command_result['filename'] or "None")
                    with col_c:
                        st.metric("🔍 Analysis Type", command_result['analysis_type'])
                    
                    if command_result['detected_patterns']:
                        st.write(f"**🎪 Detected Patterns:** {', '.join(command_result['detected_patterns'])}")
                    
                    # File search if filename detected
                    if command_result['filename']:
                        st.markdown("### 🔍 Searching for File...")
                        
                        with st.spinner(f"Searching for {command_result['filename']}..."):
                            found_files = analyzer.search_for_file(command_result['filename'])
                        
                        if found_files:
                            st.success(f"✅ Found {len(found_files)} matching file(s)!")
                            
                            # Display found files
                            for i, file_path in enumerate(found_files[:5]):  # Show top 5
                                file_info = analyzer.get_file_info(file_path)
                                
                                with st.expander(f"📁 {file_info['name']} ({file_info['size_mb']:.2f} MB)"):
                                    st.write(f"**📍 Location:** {file_info['parent_dir']}")
                                    st.write(f"**📅 Modified:** {file_info['modified']}")
                                    st.write(f"**📋 Type:** {file_info['type']}")
                                    
                                    if st.button(f"🚀 Analyze This File", key=f"voice_analyze_{i}"):
                                        # Store selection in session state
                                        st.session_state.selected_file = str(file_path)
                                        st.session_state.selected_file_info = file_info
                                        st.session_state.voice_analysis_type = command_result['analysis_type']
                                        st.session_state.voice_command_used = True
                                        st.rerun()
                        else:
                            st.warning(f"⚠️ No files found matching '{command_result['filename']}'")
                            st.info("💡 Try using a more specific filename or check the file location")
                    
                    else:
                        st.warning("⚠️ No specific filename detected in voice command")
                        st.info("💡 Try saying something like: 'Analyze my cover letter PDF' or 'Process IQAC document'")
                
                else:
                    st.error(f"❌ Speech recognition failed: {transcribed_text}")
                    st.info("💡 Please speak clearly and try again")
    
    else:
        # Fallback for environments without voice support
        st.warning("🎤 Voice recording not available in this environment")
        st.markdown("### 🎭 Voice Command Simulator")
        
        example_commands = [
            "Analyze my cover letter PDF",
            "Process the IQAC document", 
            "Extract information from invoice PDF",
            "Summarize the report file",
            "Check automation opportunities in contract",
            "Open resume document",
            "Find thesis PDF file"
        ]
        
        selected_demo = st.selectbox("🎪 Try a demo voice command:", example_commands)
        
        if st.button("🎬 **Simulate Voice Command**", type="primary"):
            with st.spinner("🎙️ Processing simulated voice command..."):
                time.sleep(1)
                command_result = analyzer.process_voice_command(selected_demo)
            
            st.success(f"🎤 **Simulated Command:** \"{selected_demo}\"")
            st.info(f"📄 Detected filename: {command_result['filename'] or 'No specific file detected'}")
            st.info(f"🎯 Analysis type: {command_result['analysis_type']}")
            st.info(f"🎲 Confidence: {command_result['confidence']}")
            
            if command_result['filename']:
                # Create simulated file info for demo
                simulated_file_info = {
                    "name": command_result['filename'],
                    "size_mb": 0.5,
                    "modified": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "type": analyzer.get_file_type(Path(command_result['filename']).suffix.lower()),
                    "parent_dir": "/demo/downloads"
                }
                
                st.session_state.selected_file = f"/demo/voice/{command_result['filename']}"
                st.session_state.selected_file_info = simulated_file_info
                st.session_state.voice_analysis_type = command_result['analysis_type']
                st.session_state.voice_command_used = True
                st.success("✅ Demo file selected! Analysis section will appear below.")
                st.rerun()

def main():
    st.title("🎤 Voice-Enabled Auto File Analyzer")
    st.markdown("**Smart File Processing** with **Voice Commands** + **Gemini AI Analysis**")
    
    if not GEMINI_AVAILABLE:
        st.error("⚠️ Google Gemini AI not available. Please install: pip install google-genai")
        return
    
    analyzer = get_analyzer()
    
    # Sidebar with enhanced information
    with st.sidebar:
        st.header("🎤 Voice Analysis Dashboard")
        
        # System status
        if analyzer.gemini_client:
            st.success("✅ Gemini AI Connected")
        else:
            st.error("❌ Gemini AI Not Available")
        
        if SPEECH_AVAILABLE:
            st.success("✅ Voice Recognition Ready")
        else:
            st.warning("⚠️ Voice Recognition Unavailable")
        
        # Statistics
        if analyzer.analysis_history:
            total = len(analyzer.analysis_history)
            successful = len([a for a in analyzer.analysis_history if a['success']])
            voice_used = len([a for a in analyzer.analysis_history if a.get('voice_command', False)])
            
            st.metric("Total Analyses", total)
            st.metric("Success Rate", f"{(successful/total*100):.0f}%")
            st.metric("Voice Commands", voice_used)
            
            st.subheader("📈 Recent Activity")
            for analysis in analyzer.analysis_history[-3:]:
                icon = "🎤" if analysis.get('voice_command', False) else "📁"
                st.write(f"**{icon} {analysis['timestamp']}**")
                st.write(f"File: {analysis['file_name']}")
                st.write(f"Type: {analysis['analysis_type']}")
                st.write(f"Status: {'✅' if analysis['success'] else '❌'}")
                st.write("---")
        
        st.header("🎙️ Voice Commands Guide")
        st.markdown("""
        **📢 Supported Commands:**
        - "Analyze [filename]"
        - "Process [document type]"
        - "Extract from [filename]"
        - "Summarize [document]"
        - "Find automation in [file]"
        
        **📄 File Types:**
        - PDF documents
        - Word documents
        - Images (PNG, JPG)
        - Excel spreadsheets
        - PowerPoint presentations
        
        **🎯 Tips for Better Recognition:**
        - Speak clearly and slowly
        - Use specific filenames
        - Mention file extensions
        - Avoid background noise
        """)
    
    # Main interface tabs
    tab1, tab2, tab3 = st.tabs(["🎤 Voice Control", "📝 Text Input", "📤 Manual Upload"])
    
    with tab1:
        create_voice_interface()
    
    with tab2:
        st.header("📁 Text-Based File Processing")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Method 1: Full path input
            st.markdown("**Method 1: Enter Full File Path**")
            file_path_input = st.text_input(
                "Full file path:",
                placeholder="C:\\Users\\Username\\Downloads\\document.pdf",
                help="Enter the complete path to your file"
            )
            
            # Method 2: Filename search
            st.markdown("**Method 2: Search by Filename**")
            filename_only = st.text_input(
                "Just the filename:",
                placeholder="document.pdf",
                help="Enter just the filename - we'll search for it automatically"
            )
            
            # Analysis type selection
            analysis_type = st.selectbox(
                "Select Analysis Type:",
                [
                    "Document Summary",
                    "Key Information Extraction", 
                    "Automation Opportunities",
                    "Content Analysis"
                ]
            )
            
            # File processing logic
            if filename_only and not file_path_input:
                if st.button("🔍 Search for File", type="primary"):
                    with st.spinner(f"Searching for {filename_only}..."):
                        found_files = analyzer.search_for_file(filename_only)
                    
                    if found_files:
                        st.success(f"✅ Found {len(found_files)} matching file(s)!")
                        
                        for i, file_path in enumerate(found_files[:5]):
                            file_info = analyzer.get_file_info(file_path)
                            
                            with st.expander(f"📁 {file_info['name']} ({file_info['size_mb']:.2f} MB)"):
                                st.write(f"**📍 Location:** {file_info['parent_dir']}")
                                st.write(f"**📅 Modified:** {file_info['modified']}")
                                st.write(f"**📋 Type:** {file_info['type']}")
                                
                                if st.button(f"Select This File", key=f"select_{i}"):
                                    st.session_state.selected_file = str(file_path)
                                    st.session_state.selected_file_info = file_info
                                    st.session_state.text_analysis_type = analysis_type
                                    st.rerun()
                    else:
                        st.warning(f"⚠️ No files found matching '{filename_only}'")
            
            elif file_path_input:
                if st.button("✅ Validate File Path", type="primary"):
                    file_path = Path(file_path_input)
                    if file_path.exists() and file_path.is_file():
                        file_info = analyzer.get_file_info(file_path_input)
                        st.session_state.selected_file = file_path_input
                        st.session_state.selected_file_info = file_info
                        st.session_state.text_analysis_type = analysis_type
                        st.success("✅ File validated and selected!")
                        st.rerun()
                    else:
                        st.error("❌ File not found or invalid path")
        
        with col2:
            st.subheader("ℹ️ How It Works")
            st.markdown("""
            **🎯 Two Methods:**
            
            **Method 1: Full Path**
            - Enter complete file path
            - System validates file exists
            - Processes immediately
            
            **Method 2: Filename Search**
            - Enter just the filename
            - System searches common folders
            - Shows all matches found
            - Select the right file
            
            **🔍 Search Locations:**
            - Downloads folder
            - Documents folder
            - Desktop
            - Telegram Desktop folder
            - Subfolders (up to 3 levels)
            """)
    
    with tab3:
        st.header("📤 Manual File Upload")
        
        uploaded_file = st.file_uploader(
            "Upload file directly", 
            type=['pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'txt', 'xlsx', 'pptx']
        )
        
        if uploaded_file:
            st.success(f"📁 Uploaded: {uploaded_file.name}")
            
            upload_analysis_type = st.selectbox(
                "Select Analysis Type:",
                [
                    "Document Summary",
                    "Key Information Extraction",
                    "Automation Opportunities", 
                    "Content Analysis"
                ],
                key="upload_analysis_type"
            )
            
            if st.button("🔍 Analyze Uploaded File", type="primary"):
                with st.spinner("🤖 Analyzing uploaded file..."):
                    # Create file info
                    file_info = {
                        "name": uploaded_file.name,
                        "size_mb": len(uploaded_file.getvalue()) / 1024 / 1024,
                        "type": analyzer.get_file_type(Path(uploaded_file.name).suffix.lower()),
                        "modified": time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # Save file temporarily
                    temp_path = analyzer.temp_dir / f"uploaded_{uuid.uuid4().hex[:8]}_{uploaded_file.name}"
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getvalue())
                    
                    # Extract content based on file type
                    if file_info['type'] in ["PDF"]:
                        content = analyzer.extract_text_from_pdf(temp_path)
                    elif file_info['type'] in ["Word Document"]:
                        content = f"Word document analysis for: {uploaded_file.name}"
                    else:
                        content = f"File analysis for: {uploaded_file.name}"
                    
                    # Analyze with Gemini
                    analysis_result = analyzer.analyze_with_gemini(content, file_info, upload_analysis_type)
                    
                    # Show results
                    if analysis_result and not analysis_result.startswith("Error"):
                        st.success("🎉 **Analysis Completed Successfully!**")
                        st.markdown("### 📊 Analysis Results")
                        st.markdown("---")
                        st.markdown(analysis_result)
                        st.markdown("---")
                        
                        # Download button
                        timestamp = int(time.time())
                        download_filename = f"analysis_{uploaded_file.name}_{timestamp}.txt"
                        
                        download_content = f"""
VOICE-ENABLED FILE ANALYZER REPORT
=================================

File: {uploaded_file.name}
Analysis Type: {upload_analysis_type}
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
File Size: {file_info['size_mb']:.2f} MB

ANALYSIS RESULTS:
{analysis_result}

---
Generated by Voice-Enabled Auto File Analyzer with Gemini AI
                        """
                        
                        st.download_button(
                            label="💾 Download Analysis Report",
                            data=download_content,
                            file_name=download_filename,
                            mime="text/plain",
                            use_container_width=True
                        )
                        
                        # Log the analysis
                        analyzer.log_analysis(str(temp_path), upload_analysis_type, True, len(analysis_result))
                        st.balloons()
                    else:
                        st.error(f"❌ Analysis failed: {analysis_result}")
                    
                    # Cleanup
                    temp_path.unlink(missing_ok=True)

    # Show selected file and analysis section (works for all tabs)
    if hasattr(st.session_state, 'selected_file') and hasattr(st.session_state, 'selected_file_info'):
        st.markdown("---")
        st.header("📁 Selected File Analysis")
        
        selected_file_path = st.session_state.selected_file
        file_info = st.session_state.selected_file_info
        
        # Determine analysis type based on source
        if hasattr(st.session_state, 'voice_analysis_type'):
            analysis_type_selected = st.session_state.voice_analysis_type
            source_icon = "🎤"
            source_text = "Voice Command"
        elif hasattr(st.session_state, 'text_analysis_type'):
            analysis_type_selected = st.session_state.text_analysis_type
            source_icon = "📝"
            source_text = "Text Input"
        else:
            analysis_type_selected = "Document Summary"
            source_icon = "📁"
            source_text = "Manual"
        
        st.success(f"{source_icon} File selected via {source_text}: **{file_info['name']}**")
        
        # File information display
        info_col1, info_col2, info_col3, info_col4 = st.columns(4)
        with info_col1:
            st.metric("📄 File Name", file_info['name'])
        with info_col2:
            st.metric("📊 Size", f"{file_info['size_mb']:.2f} MB")
        with info_col3:
            st.metric("📋 Type", file_info['type'])
        with info_col4:
            st.metric("🎯 Analysis", analysis_type_selected)
        
        st.write(f"**📅 Last Modified:** {file_info.get('modified', 'Unknown')}")
        st.write(f"**📁 Path:** {selected_file_path}")
        
        # Analysis section
        st.subheader("🤖 Gemini AI Analysis")
        
        # Allow changing analysis type
        analysis_type_final = st.selectbox(
            "🎯 Choose Final Analysis Type:",
            [
                "Document Summary",
                "Key Information Extraction",
                "Automation Opportunities", 
                "Content Analysis"
            ],
            index=[
                "Document Summary",
                "Key Information Extraction", 
                "Automation Opportunities",
                "Content Analysis"
            ].index(analysis_type_selected) if analysis_type_selected in [
                "Document Summary",
                "Key Information Extraction",
                "Automation Opportunities", 
                "Content Analysis"
            ] else 0,
            key="final_analysis_type"
        )
        
        # Analysis button
        if st.button("🚀 **START GEMINI AI ANALYSIS**", type="primary", use_container_width=True):
            with st.spinner("🤖 Analyzing with Gemini AI... Please wait..."):
                
                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Step 1: File preparation
                status_text.text("📄 Preparing file for analysis...")
                progress_bar.progress(20)
                time.sleep(1)
                
                # Step 2: Content extraction
                status_text.text("📖 Extracting content...")
                progress_bar.progress(40)
                
                # Extract content based on file type and path
                if selected_file_path.startswith("/demo/") or selected_file_path.startswith("/voice/"):
                    # Demo/simulated content
                    if "cover" in file_info['name'].lower():
                        content = """
                        Dear Hiring Manager,
                        
                        I am writing to express my strong interest in the Software Developer position at your company. 
                        With my background in computer science and 3+ years of experience in full-stack development, 
                        I believe I would be a valuable addition to your engineering team.
                        
                        My technical qualifications include:
                        - Bachelor's degree in Computer Science from State University
                        - 3+ years of experience with Python, JavaScript, and React
                        - Strong problem-solving and analytical skills
                        - Experience with machine learning, AI technologies, and cloud platforms
                        - Proficiency in database design and API development
                        
                        In my previous role at TechCorp, I successfully:
                        - Led the development of a customer portal that increased user engagement by 40%
                        - Optimized database queries resulting in 25% faster application performance
                        - Collaborated with cross-functional teams to deliver projects on time and within budget
                        
                        I am particularly excited about your company's focus on innovative AI solutions and would 
                        welcome the opportunity to contribute to your mission. I am confident that my technical 
                        skills and passion for technology align well with your team's needs.
                        
                        Thank you for considering my application. I look forward to discussing how I can contribute 
                        to your organization's continued success.
                        
                        Sincerely,
                        John Smith
                        Email: john.smith@email.com
                        Phone: (555) 123-4567
                        """
                    elif "iqac" in file_info['name'].lower():
                        content = """
                        INTERNAL QUALITY ASSURANCE CELL (IQAC) DOCUMENT
                        
                        Institution: State University College of Engineering
                        Academic Year: 2023-2024
                        Document Version: 2.1
                        Last Updated: March 15, 2024
                        
                        EXECUTIVE SUMMARY:
                        This document outlines the comprehensive quality assurance framework implemented by 
                        the Internal Quality Assurance Cell to ensure continuous improvement in academic 
                        and administrative processes.
                        
                        QUALITY OBJECTIVES:
                        1. Maintain academic excellence through systematic quality monitoring
                        2. Enhance teaching-learning processes and student outcomes
                        3. Ensure compliance with regulatory standards and accreditation requirements
                        4. Foster a culture of continuous improvement and innovation
                        5. Strengthen industry-academia partnerships
                        
                        KEY PERFORMANCE INDICATORS:
                        - Student satisfaction rate: 92%
                        - Faculty satisfaction rate: 88%
                        - Placement rate: 85%
                        - Research publications: 45 papers published
                        - Industry collaborations: 12 active partnerships
                        
                        ASSESSMENT METHODOLOGIES:
                        1. Student feedback surveys (semester-wise)
                        2. Faculty performance evaluations
                        3. Curriculum review and updates
                        4. Infrastructure quality audits
                        5. External expert evaluations
                        
                        CONTINUOUS IMPROVEMENT PROCESSES:
                        - Monthly IQAC meetings with stakeholder representation
                        - Annual quality assurance reports
                        - Action plans for identified improvement areas
                        - Best practices documentation and sharing
                        
                        STAKEHOLDER FEEDBACK MECHANISMS:
                        - Student feedback portals
                        - Alumni networking and surveys
                        - Industry partner consultations
                        - Parent-teacher interaction sessions
                        
                        Next Review Date: September 2024
                        Approved by: Dr. Sarah Johnson, IQAC Coordinator
                        """
                    elif "resume" in file_info['name'].lower():
                        content = """
                        JOHN SMITH
                        Software Developer & AI Enthusiast
                        
                        Contact Information:
                        Email: john.smith@email.com
                        Phone: (555) 123-4567
                        LinkedIn: linkedin.com/in/johnsmith
                        GitHub: github.com/johnsmith
                        Location: San Francisco, CA
                        
                        PROFESSIONAL SUMMARY:
                        Experienced software developer with 5+ years in full-stack development, specializing in 
                        Python, JavaScript, and AI/ML technologies. Proven track record of delivering scalable 
                        applications and leading cross-functional teams to achieve project goals.
                        
                        TECHNICAL SKILLS:
                        Programming Languages: Python, JavaScript, Java, C++, SQL
                        Frameworks: React, Node.js, Django, Flask, TensorFlow, PyTorch
                        Databases: PostgreSQL, MongoDB, Redis
                        Cloud Platforms: AWS, Google Cloud, Azure
                        Tools: Docker, Kubernetes, Git, Jenkins, JIRA
                        
                        PROFESSIONAL EXPERIENCE:
                        
                        Senior Software Developer | TechCorp Inc. | 2021 - Present
                        - Led development of AI-powered customer analytics platform serving 10M+ users
                        - Improved application performance by 40% through database optimization
                        - Mentored 3 junior developers and conducted code reviews
                        - Collaborated with product managers to define technical requirements
                        
                        Software Developer | StartupXYZ | 2019 - 2021
                        - Developed RESTful APIs and microservices architecture
                        - Implemented machine learning models for recommendation systems
                        - Reduced deployment time by 60% through CI/CD pipeline automation
                        - Worked in Agile environment with 2-week sprints
                        
                        Junior Developer | WebSolutions | 2018 - 2019
                        - Built responsive web applications using React and Node.js
                        - Participated in full software development lifecycle
                        - Maintained legacy systems and performed bug fixes
                        
                        EDUCATION:
                        Bachelor of Science in Computer Science
                        State University | Graduated: May 2018 | GPA: 3.8/4.0
                        
                        PROJECTS:
                        AI Chatbot Platform (2023)
                        - Developed intelligent chatbot using NLP and machine learning
                        - Integrated with multiple messaging platforms
                        - Achieved 95% user satisfaction rate
                        
                        E-commerce Analytics Dashboard (2022)
                        - Created real-time analytics dashboard for online retailers
                        - Processed and visualized large datasets
                        - Increased client insights and decision-making speed
                        
                        CERTIFICATIONS:
                        - AWS Certified Solutions Architect (2023)
                        - Google Cloud Professional Data Engineer (2022)
                        - Microsoft Azure AI Engineer Associate (2021)
                        
                        ACHIEVEMENTS:
                        - Employee of the Month (3 times) at TechCorp
                        - Published 2 technical articles on AI/ML best practices
                        - Speaker at Bay Area Tech Conference 2023
                        """
                    else:
                        content = f"This is simulated content for {file_info['name']}. In a real environment, this would contain the actual extracted text from the document."
                
                else:
                    # Real file processing
                    if file_info['type'] == "PDF":
                        content = analyzer.extract_text_from_pdf(selected_file_path)
                    elif file_info['type'] == "Word Document":
                        content = f"Word document content from: {file_info['name']}"
                    else:
                        content = f"Content analysis for: {file_info['name']}"
                
                progress_bar.progress(60)
                status_text.text("🤖 Sending to Gemini AI...")
                time.sleep(1)
                
                # Step 3: AI Analysis
                analysis_result = analyzer.analyze_with_gemini(content, file_info, analysis_type_final)
                
                progress_bar.progress(80)
                status_text.text("📝 Processing results...")
                time.sleep(1)
                
                progress_bar.progress(100)
                status_text.text("✅ Analysis complete!")
                time.sleep(1)
                
                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()
                
                # Show results
                if analysis_result and not analysis_result.startswith("Error"):
                    st.success("🎉 **Analysis Completed Successfully!**")
                    
                    # Results section
                    st.markdown("### 📊 Gemini AI Analysis Results")
                    st.markdown("---")
                    st.markdown(analysis_result)
                    st.markdown("---")
                    
                    # Download section
                    st.subheader("💾 Download Results")
                    
                    timestamp = int(time.time())
                    safe_filename = "".join(c for c in file_info['name'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    download_filename = f"voice_analysis_{safe_filename}_{timestamp}.txt"
                    
                    # Enhanced download content
                    download_content = f"""
VOICE-ENABLED FILE ANALYZER REPORT
=================================

File Information:
- Name: {file_info['name']}
- Type: {file_info['type']}
- Size: {file_info['size_mb']:.2f} MB
- Modified: {file_info.get('modified', 'Unknown')}
- Path: {selected_file_path}

Analysis Details:
- Type: {analysis_type_final}
- Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
- Method: {source_text}
- Voice Command Used: {hasattr(st.session_state, 'voice_command_used')}

ANALYSIS RESULTS:
================
{analysis_result}

---
Generated by Voice-Enabled Auto File Analyzer with Gemini AI
Powered by Google Speech Recognition and Gemini 2.0 Flash
                    """
                    
                    col_download1, col_download2 = st.columns(2)
                    with col_download1:
                        st.download_button(
                            label="💾 **Download Complete Report**",
                            data=download_content,
                            file_name=download_filename,
                            mime="text/plain",
                            use_container_width=True
                        )
                    with col_download2:
                        # Copy to clipboard (simulated)
                        if st.button("📋 Copy to Clipboard", use_container_width=True):
                            st.success("✅ Analysis copied to clipboard!")
                    
                    # Additional options
                    st.subheader("🔄 Next Actions")
                    col_action1, col_action2, col_action3 = st.columns(3)
                    
                    with col_action1:
                        if st.button("🔄 **Analyze Again**", use_container_width=True):
                            st.rerun()
                    
                    with col_action2:
                        if st.button("📄 **Select New File**", use_container_width=True):
                            # Clear session state
                            keys_to_clear = ['selected_file', 'selected_file_info', 'voice_analysis_type', 
                                           'text_analysis_type', 'voice_command_used']
                            for key in keys_to_clear:
                                if hasattr(st.session_state, key):
                                    delattr(st.session_state, key)
                            st.rerun()
                    
                    with col_action3:
                        if st.button("🎤 **Voice Command**", use_container_width=True):
                            # Switch to voice tab
                            st.switch_page  # This would need to be implemented
                    
                    # Log success
                    voice_used = hasattr(st.session_state, 'voice_command_used')
                    analyzer.log_analysis(selected_file_path, analysis_type_final, True, 
                                        len(analysis_result), voice_used)
                    
                    # Celebration
                    st.balloons()
                    
                    # Usage tips
                    with st.expander("💡 Tips for Better Analysis"):
                        st.markdown("""
                        **🎤 Voice Command Tips:**
                        - Speak clearly and at moderate pace
                        - Use specific filenames with extensions
                        - Include analysis type in your command
                        - Try: "Analyze my resume PDF for key information"
                        
                        **📄 File Processing Tips:**
                        - PDF files work best for text extraction
                        - Ensure files are not password protected
                        - Larger files may take longer to process
                        - Clear scanned documents work better than blurry ones
                        
                        **🤖 Analysis Tips:**
                        - Choose the right analysis type for your needs
                        - Summary: For general overview
                        - Key Information: For specific data extraction
                        - Automation: For process improvement ideas
                        - Content Analysis: For quality assessment
                        """)
                
                else:
                    st.error(f"❌ Analysis failed: {analysis_result}")
                    analyzer.log_analysis(selected_file_path, analysis_type_final, False, 0, 
                                        hasattr(st.session_state, 'voice_command_used'))
                    
                    if st.button("🔄 Try Again"):
                        st.rerun()

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <h4>🎤 Voice-Enabled Auto File Analyzer</h4>
        <p><strong>Smart file processing + Voice commands + Gemini AI analysis</strong></p>
        <p>🎙️ <em>Now with hands-free voice control for ultimate automation!</em></p>
        <p>Features: Microphone input • Google Speech Recognition • File search • AI analysis</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
