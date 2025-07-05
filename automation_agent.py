import streamlit as st
import os
import platform
import time
from pathlib import Path
import tempfile
import uuid
import shutil

# Try to import speech recognition (works without pyaudio for some methods)
try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False

# Try to import Google Gemini for analysis
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Try PDF processing
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# Configure Streamlit
st.set_page_config(
    page_title="Voice File Search",
    page_icon="🎤",
    layout="wide"
)

class VoiceFileSearcher:
    def __init__(self):
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "AIzaSyDFgcA8F1RD0t0UmMbomQ54dHoGPZRT0ok")
        
        if GEMINI_AVAILABLE:
            try:
                self.gemini_client = genai.Client(api_key=self.gemini_api_key)
                self.model = "gemini-2.0-flash"
            except Exception as e:
                st.error(f"Gemini setup failed: {e}")
                self.gemini_client = None
        else:
            self.gemini_client = None
            
        self.setup_speech_recognition()
        
    def setup_speech_recognition(self):
        """Setup speech recognition without pyaudio dependency"""
        self.recognizer = None
        
        if SPEECH_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
                st.success("✅ Speech Recognition Ready (Browser/Web-based)")
            except Exception as e:
                st.warning(f"Speech recognition setup issue: {e}")
    
    def process_voice_text(self, text):
        """Extract filename from voice text"""
        text = text.lower().strip()
        
        # Common file extensions
        extensions = ['.pdf', '.doc', '.docx', '.txt', '.xlsx', '.pptx', '.png', '.jpg', '.jpeg']
        
        # Look for filename patterns
        words = text.split()
        potential_files = []
        
        # Method 1: Look for words with extensions
        for word in words:
            for ext in extensions:
                if ext.replace('.', '') in word:
                    potential_files.append(word + ext if not word.endswith(ext) else word)
        
        # Method 2: Look for common document names
        doc_patterns = {
            'resume': 'resume.pdf',
            'cv': 'cv.pdf', 
            'cover letter': 'cover_letter.pdf',
            'report': 'report.pdf',
            'invoice': 'invoice.pdf',
            'contract': 'contract.pdf',
            'presentation': 'presentation.pptx',
            'spreadsheet': 'spreadsheet.xlsx',
            'iqac': 'iqac.pdf',
            'thesis': 'thesis.pdf',
            'assignment': 'assignment.pdf'
        }
        
        for pattern, filename in doc_patterns.items():
            if pattern in text:
                potential_files.append(filename)
        
        # Method 3: Extract any word that might be a filename
        for word in words:
            if len(word) > 3 and word not in ['find', 'search', 'open', 'analyze', 'the', 'my', 'file']:
                for ext in ['.pdf', '.doc', '.txt']:
                    potential_files.append(word + ext)
        
        return list(set(potential_files))  # Remove duplicates
    
    def search_files_on_pc(self, search_terms):
        """Enhanced file search across PC"""
        found_files = []
        
        # Define search locations based on OS
        search_locations = self.get_search_locations()
        
        st.info(f"🔍 Searching for: {', '.join(search_terms)}")
        progress_bar = st.progress(0)
        
        total_locations = len(search_locations)
        
        for i, location in enumerate(search_locations):
            try:
                if not location.exists():
                    continue
                    
                progress_bar.progress((i + 1) / total_locations)
                st.caption(f"Searching in: {location}")
                
                # Search for each term
                for term in search_terms:
                    # Exact filename match
                    exact_file = location / term
                    if exact_file.exists() and exact_file.is_file():
                        found_files.append(exact_file)
                    
                    # Partial filename match
                    try:
                        for file_path in location.iterdir():
                            if file_path.is_file():
                                filename_lower = file_path.name.lower()
                                term_lower = term.lower()
                                
                                # Check if term is in filename
                                if term_lower in filename_lower:
                                    found_files.append(file_path)
                                
                                # Check without extension
                                name_without_ext = file_path.stem.lower()
                                term_without_ext = Path(term).stem.lower()
                                if term_without_ext in name_without_ext:
                                    found_files.append(file_path)
                    
                    except (PermissionError, OSError):
                        continue
                    
                    # Recursive search (1 level deep)
                    try:
                        for subfolder in location.iterdir():
                            if subfolder.is_dir() and not subfolder.name.startswith('.'):
                                for file_path in subfolder.iterdir():
                                    if file_path.is_file():
                                        filename_lower = file_path.name.lower()
                                        term_lower = term.lower()
                                        if term_lower in filename_lower:
                                            found_files.append(file_path)
                    except (PermissionError, OSError):
                        continue
                        
            except (PermissionError, OSError):
                continue
        
        progress_bar.empty()
        
        # Remove duplicates and sort by modification time
        unique_files = list({str(f): f for f in found_files}.values())
        
        try:
            unique_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        except:
            pass
            
        return unique_files[:20]  # Return top 20 matches
    
    def get_search_locations(self):
        """Get OS-appropriate search locations"""
        locations = []
        
        if platform.system() == "Windows":
            # Windows search locations
            username = os.getenv("USERNAME", "")
            locations = [
                Path.home() / "Downloads",
                Path.home() / "Documents", 
                Path.home() / "Desktop",
                Path("C:/Users") / username / "Downloads",
                Path("C:/Users") / username / "Documents",
                Path("C:/Users") / username / "Desktop",
            ]
            
            # Add common Windows folders
            if username:
                locations.extend([
                    Path("C:/Users") / username / "Downloads" / "Telegram Desktop",
                    Path("C:/Users") / username / "OneDrive",
                    Path("C:/Users") / username / "OneDrive" / "Documents",
                ])
                
        elif platform.system() == "Darwin":  # macOS
            locations = [
                Path.home() / "Downloads",
                Path.home() / "Documents",
                Path.home() / "Desktop",
                Path.home() / "iCloud Drive",
                Path("/Applications"),
            ]
            
        else:  # Linux
            locations = [
                Path.home() / "Downloads",
                Path.home() / "Documents", 
                Path.home() / "Desktop",
                Path("/tmp"),
                Path("/home") / os.getenv("USER", "") / "Downloads",
            ]
        
        # Filter out None values and duplicates
        return list({str(loc): loc for loc in locations if loc is not None}.values())
    
    def get_file_info(self, file_path):
        """Get file information"""
        try:
            path = Path(file_path)
            stat = path.stat()
            
            return {
                "name": path.name,
                "size_mb": stat.st_size / 1024 / 1024,
                "modified": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
                "extension": path.suffix.lower(),
                "parent_dir": str(path.parent),
                "type": self.get_file_type(path.suffix.lower())
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_file_type(self, extension):
        """Get file type from extension"""
        types = {
            '.pdf': 'PDF Document',
            '.doc': 'Word Document', 
            '.docx': 'Word Document',
            '.txt': 'Text File',
            '.xlsx': 'Excel File',
            '.pptx': 'PowerPoint',
            '.png': 'Image',
            '.jpg': 'Image',
            '.jpeg': 'Image'
        }
        return types.get(extension, 'Unknown')

def main():
    st.title("🎤 Voice File Search on PC")
    st.markdown("**Speak the filename → AI finds it on your computer**")
    
    searcher = VoiceFileSearcher()
    
    # Sidebar status
    with st.sidebar:
        st.header("🎤 System Status")
        
        if SPEECH_AVAILABLE:
            st.success("✅ Speech Recognition Ready")
        else:
            st.error("❌ Speech Recognition Unavailable")
            st.caption("Run: pip install SpeechRecognition")
            
        if GEMINI_AVAILABLE:
            st.success("✅ Gemini AI Ready")
        else:
            st.warning("⚠️ Gemini AI Unavailable")
        
        st.markdown("---")
        st.header("💡 Voice Commands")
        st.markdown("""
        **Examples:**
        - "Find my resume"
        - "Search for invoice PDF"
        - "Open cover letter"
        - "Locate IQAC document"
        - "Find presentation file"
        
        **Tips:**
        - Speak clearly
        - Mention file type
        - Use specific names
        """)
    
    # Main interface
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("🎙️ Voice Search")
        
        # Method 1: Text input (simulating voice)
        st.subheader("🎤 Voice Input (Text Simulation)")
        voice_text = st.text_input(
            "What would you say?",
            placeholder="Find my resume PDF",
            help="Type what you would say to the microphone"
        )
        
        if voice_text and st.button("🔍 **Process Voice Command**", type="primary"):
            with st.spinner("🧠 Processing voice command..."):
                # Extract potential filenames
                potential_files = searcher.process_voice_text(voice_text)
                
                st.success(f"🎤 **Voice Command:** \"{voice_text}\"")
                
                if potential_files:
                    st.info(f"🎯 **Detected Files:** {', '.join(potential_files)}")
                    
                    # Search for files
                    with st.spinner("🔍 Searching PC for files..."):
                        found_files = searcher.search_files_on_pc(potential_files)
                    
                    if found_files:
                        st.success(f"✅ **Found {len(found_files)} file(s)!**")
                        
                        # Display found files
                        for i, file_path in enumerate(found_files):
                            file_info = searcher.get_file_info(file_path)
                            
                            with st.expander(f"📁 {file_info['name']} - {file_info['type']} ({file_info['size_mb']:.2f} MB)"):
                                col_a, col_b = st.columns(2)
                                
                                with col_a:
                                    st.write(f"**📍 Location:** {file_info['parent_dir']}")
                                    st.write(f"**📅 Modified:** {file_info['modified']}")
                                    st.write(f"**📋 Type:** {file_info['type']}")
                                
                                with col_b:
                                    if st.button(f"📂 Open Folder", key=f"folder_{i}"):
                                        # Open file location
                                        if platform.system() == "Windows":
                                            os.system(f'explorer /select,"{file_path}"')
                                        elif platform.system() == "Darwin":
                                            os.system(f'open -R "{file_path}"')
                                        else:
                                            os.system(f'xdg-open "{file_info["parent_dir"]}"')
                                        st.success("📂 Folder opened!")
                                    
                                    if st.button(f"🚀 Open File", key=f"open_{i}"):
                                        # Open file
                                        if platform.system() == "Windows":
                                            os.startfile(file_path)
                                        elif platform.system() == "Darwin":
                                            os.system(f'open "{file_path}"')
                                        else:
                                            os.system(f'xdg-open "{file_path}"')
                                        st.success("🚀 File opened!")
                                
                                # Show file path
                                st.code(str(file_path), language="text")
                    
                    else:
                        st.warning("⚠️ No files found matching your voice command")
                        st.info("💡 Try being more specific or check if the file exists")
                
                else:
                    st.warning("⚠️ Could not detect any filenames in your voice command")
                    st.info("💡 Try saying something like: 'Find my resume PDF' or 'Search for invoice'")
        
        # Method 2: Direct filename search
        st.markdown("---")
        st.subheader("📝 Direct File Search")
        direct_search = st.text_input(
            "Search for filename directly:",
            placeholder="resume.pdf, invoice, contract.doc",
            help="Enter filename or partial name"
        )
        
        if direct_search and st.button("🔍 Search PC", type="secondary"):
            search_terms = [term.strip() for term in direct_search.split(',')]
            
            with st.spinner(f"🔍 Searching for: {', '.join(search_terms)}"):
                found_files = searcher.search_files_on_pc(search_terms)
            
            if found_files:
                st.success(f"✅ Found {len(found_files)} file(s)!")
                
                for i, file_path in enumerate(found_files):
                    file_info = searcher.get_file_info(file_path)
                    st.write(f"📁 **{file_info['name']}** - {file_info['parent_dir']}")
            else:
                st.warning("⚠️ No files found")
    
    with col2:
        st.subheader("ℹ️ How It Works")
        st.markdown("""
        **🎤 Voice Recognition:**
        1. Speak filename or description
        2. AI extracts potential filenames
        3. System searches entire PC
        4. Shows all matching files
        
        **🔍 Search Coverage:**
        - Downloads folder
        - Documents folder  
        - Desktop
        - User folders
        - OneDrive/iCloud (if available)
        - Subfolders (1 level deep)
        
        **📁 Supported Files:**
        - PDF documents
        - Word documents
        - Excel spreadsheets
        - PowerPoint presentations
        - Images (PNG, JPG)
        - Text files
        
        **🎯 Voice Examples:**
        - "Find resume"
        - "Search invoice PDF"
        - "Locate cover letter"
        - "Open contract document"
        """)
        
        # Real-time file count
        if st.button("📊 Quick PC Scan"):
            with st.spinner("Scanning..."):
                locations = searcher.get_search_locations()
                total_files = 0
                
                for location in locations:
                    try:
                        if location.exists():
                            files = list(location.glob("*.*"))
                            total_files += len(files)
                    except:
                        continue
                
                st.metric("📁 Files Found", total_files)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p><strong>🎤 Voice File Search</strong> - Speak and find files instantly on your PC!</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
