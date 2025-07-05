import streamlit as st
import os
import json
import tempfile
import time
from pathlib import Path
import uuid
import shutil
import platform
import string

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

# Configure Streamlit page
st.set_page_config(
    page_title="Auto File Analyzer",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

class AutoFileAnalyzer:
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
        
    def setup_temp_directory(self):
        """Create temporary directory for processing"""
        self.temp_dir = Path(tempfile.gettempdir()) / "auto_analyzer"
        self.temp_dir.mkdir(exist_ok=True)
        
    def search_for_file(self, filename, max_results=50, deep_search=False):
        """Search for a file across the entire computer with enhanced options"""
        search_locations = []
        found_files = []
        
        if platform.system() == "Windows":
            # Windows - search all drives and common locations
            available_drives = []
            for letter in string.ascii_uppercase:
                drive_path = Path(f"{letter}:/")
                if drive_path.exists():
                    available_drives.append(drive_path)
            
            # Start with user-specific locations for faster results
            username = os.getenv("USERNAME", "")
            if username:
                search_locations = [
                    Path("C:/Users") / username / "Downloads",
                    Path("C:/Users") / username / "Downloads" / "Telegram Desktop",
                    Path("C:/Users") / username / "Documents",
                    Path("C:/Users") / username / "Desktop",
                    Path("C:/Users") / username,
                ]
            
            # Add system-wide locations
            search_locations.extend([
                Path("C:/Users"),
                Path("C:/Program Files"),
                Path("C:/Program Files (x86)"),
                Path("C:/ProgramData"),
                Path("C:/Temp"),
                Path("C:/Windows/Temp"),
            ])
            
            # Add all drives for comprehensive search
            if deep_search:
                search_locations.extend(available_drives)
        
        elif platform.system() == "Darwin":  # macOS
            search_locations = [
                Path.home() / "Downloads",
                Path.home() / "Documents",
                Path.home() / "Desktop",
                Path.home(),
                Path("/Applications"),
                Path("/Users"),
                Path("/tmp"),
            ]
            if deep_search:
                search_locations.extend([
                    Path("/"),
                    Path("/System"),
                    Path("/Library"),
                    Path("/var"),
                    Path("/usr"),
                ])
        
        else:  # Linux and others
            search_locations = [
                Path.home() / "Downloads",
                Path.home() / "Documents",
                Path.home() / "Desktop",
                Path.home(),
                Path("/home"),
                Path("/usr"),
                Path("/opt"),
                Path("/var"),
                Path("/tmp"),
            ]
            if deep_search:
                search_locations.insert(0, Path("/"))
        
        # Progress tracking
        progress_placeholder = st.empty()
        total_locations = len(search_locations)
        
        for idx, location in enumerate(search_locations):
            try:
                if location.exists():
                    # Update progress
                    progress_placeholder.text(f"🔍 Searching in: {location} ({idx+1}/{total_locations})")
                    
                    # Search for exact filename
                    exact_match = location / filename
                    if exact_match.exists() and exact_match.is_file():
                        found_files.append(exact_match)
                    
                    # Search for files containing the filename (recursive)
                    try:
                        if deep_search:
                            # Deep recursive search
                            for file_path in location.rglob(f"*{filename}*"):
                                if file_path.is_file():
                                    found_files.append(file_path)
                                    
                                # Limit results to prevent overwhelming output
                                if len(found_files) >= max_results:
                                    break
                        else:
                            # Limited depth search (max 3 levels)
                            for file_path in location.glob(f"*{filename}*"):
                                if file_path.is_file():
                                    found_files.append(file_path)
                            
                            # Search 2 levels deep
                            try:
                                for file_path in location.glob(f"*/*{filename}*"):
                                    if file_path.is_file():
                                        found_files.append(file_path)
                                for file_path in location.glob(f"*/*/*{filename}*"):
                                    if file_path.is_file():
                                        found_files.append(file_path)
                            except (PermissionError, OSError):
                                continue
                                
                    except (PermissionError, OSError):
                        continue
                        
                # Break if we have enough results and not doing deep search
                if not deep_search and len(found_files) >= 20:
                    break
                    
            except (PermissionError, OSError):
                continue
        
        # Clear progress indicator
        progress_placeholder.empty()
        
        # Remove duplicates
        unique_files = []
        seen_paths = set()
        for file_path in found_files:
            if str(file_path) not in seen_paths:
                unique_files.append(file_path)
                seen_paths.add(str(file_path))
        
        # Sort by newest first
        try:
            unique_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        except (PermissionError, OSError):
            pass
        
        return unique_files[:max_results]
    
    def search_by_extension(self, extension, max_results=50):
        """Search for files by extension across the entire system"""
        found_files = []
        
        if platform.system() == "Windows":
            # Search all Windows drives
            for letter in string.ascii_uppercase:
                drive_path = Path(f"{letter}:/")
                if drive_path.exists():
                    try:
                        for file_path in drive_path.rglob(f"*.{extension}"):
                            if file_path.is_file():
                                found_files.append(file_path)
                                
                                if len(found_files) >= max_results:
                                    return found_files
                                    
                    except (PermissionError, OSError):
                        continue
        
        else:
            # Unix-like systems
            try:
                search_root = Path("/home") if Path("/home").exists() else Path.home()
                for file_path in search_root.rglob(f"*.{extension}"):
                    if file_path.is_file():
                        found_files.append(file_path)
                        
                        if len(found_files) >= max_results:
                            return found_files
                            
            except (PermissionError, OSError):
                pass
        
        return found_files
        
    def validate_file_path(self, file_path):
        """Validate that the file path exists and is accessible"""
        try:
            file_path = file_path.strip()
            
            # Replace common path variables
            if "%USERPROFILE%" in file_path:
                file_path = file_path.replace("%USERPROFILE%", str(Path.home()))
            if "%USERNAME%" in file_path:
                username = os.getenv("USERNAME", os.getenv("USER", ""))
                file_path = file_path.replace("%USERNAME%", username)
            
            path = Path(file_path)
            
            if not path.exists():
                # Try to find the file
                filename = path.name
                found_files = self.search_for_file(filename)
                
                if found_files:
                    return True, f"File found at: {found_files[0]}", str(found_files[0])
                else:
                    return False, f"File not found: {file_path}", None
            
            if not path.is_file():
                return False, f"Path is not a file: {file_path}", None
            if not os.access(path, os.R_OK):
                return False, f"File is not readable: {file_path}", None
            
            return True, "File is valid", str(path)
            
        except Exception as e:
            return False, f"Error validating file: {str(e)}", None
    
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
                "type": "PDF" if path.suffix.lower() == ".pdf" else "Document"
            }
        except Exception as e:
            return {"name": str(file_path), "size_mb": 0, "modified": "Unknown", "extension": "", "type": "Unknown", "error": str(e)}
    
    def extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF file"""
        try:
            text = ""
            
            # Try PyMuPDF first
            if 'fitz' in globals():
                doc = fitz.open(pdf_path)
                for page in doc:
                    text += page.get_text()
                doc.close()
                return text
            
            # Fallback to PyPDF2
            if 'PyPDF2' in globals():
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        text += page.extract_text()
                return text
                
            return "PDF processing libraries not available."
            
        except Exception as e:
            return f"Error extracting text: {str(e)}"
    
    def analyze_with_gemini(self, content, file_info, analysis_type):
        """Analyze content with Gemini AI"""
        if not self.gemini_client:
            return "Gemini AI not available. Please check your configuration."
            
        try:
            if file_info.get("type") == "PDF":
                base_prompt = f"""
                Analyze this PDF document: {file_info['name']}
                
                Document Content:
                {content[:8000] if content else 'No content extracted'}
                
                Analysis Type: {analysis_type}
                """
            else:
                base_prompt = f"""
                Analyze this file: {file_info['name']}
                File Type: {file_info.get('type', 'Unknown')}
                Analysis Type: {analysis_type}
                """
            
            analysis_prompts = {
                "Document Summary": base_prompt + """
                
                Please provide:
                1. **Document Overview**: What type of document this is
                2. **Main Content**: Key points and important information
                3. **Purpose**: What this document is used for
                4. **Key Details**: Important names, dates, numbers, etc.
                5. **Summary**: Concise overview of the entire document
                """,
                
                "Key Information Extraction": base_prompt + """
                
                Extract and organize:
                1. **Personal Information**: Names, contact details, addresses
                2. **Dates and Deadlines**: All dates mentioned
                3. **Financial Information**: Amounts, prices, costs
                4. **Organizations**: Companies, institutions
                5. **Technical Details**: Specifications, requirements
                6. **Action Items**: Tasks, requirements, next steps
                """,
                
                "Automation Opportunities": base_prompt + """
                
                Identify automation possibilities:
                1. **Data Entry Tasks**: Information that could be auto-extracted
                2. **Repetitive Processes**: Tasks that could be automated
                3. **Document Processing**: How this could be handled automatically
                4. **Integration Opportunities**: Systems this could connect to
                5. **Workflow Improvements**: How to streamline processes
                """,
                
                "Content Analysis": base_prompt + """
                
                Provide detailed analysis:
                1. **Content Quality**: Writing quality, completeness
                2. **Structure Analysis**: How the document is organized
                3. **Missing Information**: What might be incomplete
                4. **Improvements**: Suggestions for enhancement
                5. **Recommendations**: Next steps or actions needed
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
                config=types.GenerateContentConfig(response_mime_type="text/plain")
            )
            
            return response.text
            
        except Exception as e:
            return f"Analysis error: {str(e)}"
    
    def log_analysis(self, file_path, analysis_type, success, result_length=0):
        """Log the analysis"""
        self.analysis_history.append({
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "file_path": str(file_path),
            "file_name": Path(file_path).name,
            "analysis_type": analysis_type,
            "success": success,
            "result_length": result_length
        })

@st.cache_resource
def get_analyzer():
    return AutoFileAnalyzer()

def main():
    st.title("🤖 Auto File Analyzer with Full Computer Search")
    st.markdown("**Smart File Processing** - Find any file on your computer and analyze with Gemini AI")
    
    if not GEMINI_AVAILABLE:
        st.error("⚠️ Google Gemini AI not available. Please install: pip install google-genai")
        return
    
    analyzer = get_analyzer()
    
    # Sidebar
    with st.sidebar:
        st.header("📊 Analysis Dashboard")
        
        if analyzer.gemini_client:
            st.success("✅ Gemini AI Connected")
        else:
            st.error("❌ Gemini AI Not Available")
        
        if analyzer.analysis_history:
            total = len(analyzer.analysis_history)
            successful = len([a for a in analyzer.analysis_history if a['success']])
            st.metric("Total Analyses", total)
            st.metric("Success Rate", f"{(successful/total*100):.0f}%")
            
            st.subheader("📈 Recent Activity")
            for analysis in analyzer.analysis_history[-3:]:
                st.write(f"**{analysis['timestamp']}**")
                st.write(f"File: {analysis['file_name']}")
                st.write(f"Type: {analysis['analysis_type']}")
                st.write(f"Status: {'✅' if analysis['success'] else '❌'}")
                st.write("---")
        else:
            st.info("No analyses completed yet")
        
        st.header("🔍 Search Features")
        st.markdown("""
        - **Quick Search**: Common locations
        - **Deep Search**: Entire computer
        - **Extension Search**: Find by file type
        - **Direct Path**: Enter full file path
        - **File Upload**: Manual upload option
        """)
    
    # Main content - Two columns
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.header("🔍 Find Your File")
        
        # Tab-based interface for different search methods
        tab1, tab2, tab3, tab4 = st.tabs(["📝 File Path", "🔍 Search by Name", "📁 Search by Type", "📤 Upload File"])
        
        with tab1:
            st.markdown("**Enter Full File Path**")
            file_path_input = st.text_input(
                "Complete file path:",
                placeholder="C:\\Users\\YourName\\Downloads\\document.pdf",
                help="Enter the complete path to your file"
            )
            
            if st.button("✅ Validate & Use File", type="primary", key="validate_path"):
                if file_path_input:
                    is_valid, message, validated_path = analyzer.validate_file_path(file_path_input)
                    
                    if is_valid:
                        st.success(f"✅ {message}")
                        file_info = analyzer.get_file_info(validated_path)
                        st.session_state.selected_file = validated_path
                        st.session_state.selected_file_info = file_info
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
                else:
                    st.warning("Please enter a file path")
        
        with tab2:
            st.markdown("**Search by Filename**")
            
            col_search1, col_search2 = st.columns([3, 1])
            with col_search1:
                filename_input = st.text_input(
                    "Filename to search:",
                    placeholder="document.pdf",
                    help="Enter just the filename"
                )
            with col_search2:
                max_results = st.selectbox("Max Results", [10, 25, 50, 100], index=1)
            
            search_col1, search_col2 = st.columns(2)
            
            with search_col1:
                if st.button("🔍 Quick Search", type="primary", key="quick_search"):
                    if filename_input:
                        with st.spinner(f"Searching for {filename_input}..."):
                            found_files = analyzer.search_for_file(filename_input, max_results, deep_search=False)
                            
                            if found_files:
                                st.success(f"✅ Found {len(found_files)} files!")
                                
                                for i, file_path in enumerate(found_files):
                                    file_info = analyzer.get_file_info(file_path)
                                    
                                    with st.expander(f"📄 {file_info['name']} ({file_info['size_mb']:.2f} MB)"):
                                        st.write(f"**Path:** {file_path}")
                                        st.write(f"**Modified:** {file_info['modified']}")
                                        
                                        if st.button(f"✅ Use This File", key=f"use_quick_{i}"):
                                            st.session_state.selected_file = str(file_path)
                                            st.session_state.selected_file_info = file_info
                                            st.rerun()
                            else:
                                st.warning("No files found. Try Deep Search.")
                    else:
                        st.warning("Please enter a filename")
            
            with search_col2:
                if st.button("🔍 Deep Search", type="secondary", key="deep_search"):
                    if filename_input:
                        with st.spinner(f"Deep searching for {filename_input}... This may take time..."):
                            found_files = analyzer.search_for_file(filename_input, max_results, deep_search=True)
                            
                            if found_files:
                                st.success(f"✅ Deep search found {len(found_files)} files!")
                                
                                for i, file_path in enumerate(found_files):
                                    file_info = analyzer.get_file_info(file_path)
                                    
                                    with st.expander(f"📄 {file_info['name']} ({file_info['size_mb']:.2f} MB)"):
                                        st.write(f"**Path:** {file_path}")
                                        st.write(f"**Modified:** {file_info['modified']}")
                                        
                                        if st.button(f"✅ Use This File", key=f"use_deep_{i}"):
                                            st.session_state.selected_file = str(file_path)
                                            st.session_state.selected_file_info = file_info
                                            st.rerun()
                            else:
                                st.error("No files found even with deep search")
                    else:
                        st.warning("Please enter a filename")
        
        with tab3:
            st.markdown("**Search by File Extension**")
            
            col_ext1, col_ext2 = st.columns([2, 1])
            with col_ext1:
                extension_input = st.text_input(
                    "File extension:",
                    placeholder="pdf",
                    help="Enter file extension without the dot"
                )
            with col_ext2:
                ext_max_results = st.selectbox("Max Results", [10, 25, 50, 100], index=1, key="ext_max")
            
            if st.button("🔍 Search by Extension", type="primary", key="search_extension"):
                if extension_input:
                    with st.spinner(f"Searching for .{extension_input} files..."):
                        found_files = analyzer.search_by_extension(extension_input, ext_max_results)
                        
                        if found_files:
                            st.success(f"✅ Found {len(found_files)} .{extension_input} files!")
                            
                            for i, file_path in enumerate(found_files):
                                file_info = analyzer.get_file_info(file_path)
                                
                                with st.expander(f"📄 {file_info['name']} ({file_info['size_mb']:.2f} MB)"):
                                    st.write(f"**Path:** {file_path}")
                                    st.write(f"**Modified:** {file_info['modified']}")
                                    
                                    if st.button(f"✅ Use This File", key=f"use_ext_{i}"):
                                        st.session_state.selected_file = str(file_path)
                                        st.session_state.selected_file_info = file_info
                                        st.rerun()
                        else:
                            st.error(f"No .{extension_input} files found")
                else:
                    st.warning("Please enter a file extension")
        
        with tab4:
            st.markdown("**Upload File Directly**")
            uploaded_file = st.file_uploader(
                "Choose a file",
                type=['pdf', 'txt', 'docx', 'png', 'jpg', 'jpeg'],
                help="Upload a file directly for analysis"
            )
            
            if uploaded_file:
                st.success(f"📁 File uploaded: {uploaded_file.name}")
                
                # Create file info for uploaded file
                file_info = {
                    "name": uploaded_file.name,
                    "size_mb": len(uploaded_file.getvalue()) / 1024 / 1024,
                    "modified": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "extension": Path(uploaded_file.name).suffix.lower(),
                    "type": "PDF" if uploaded_file.type == "application/pdf" else "Document"
                }
                
                if st.button("✅ Use Uploaded File", type="primary", key="use_upload"):
                    # Save uploaded file to temp directory
                    temp_path = analyzer.temp_dir / f"uploaded_{uuid.uuid4().hex[:8]}_{uploaded_file.name}"
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getvalue())
                    
                    st.session_state.selected_file = str(temp_path)
                    st.session_state.selected_file_info = file_info
                    st.session_state.is_uploaded = True
                    st.rerun()
        
        # Show selected file and analysis section
        if hasattr(st.session_state, 'selected_file') and hasattr(st.session_state, 'selected_file_info'):
            st.markdown("---")
            st.header("📁 Selected File Ready for Analysis")
            
            selected_file_path = st.session_state.selected_file
            file_info = st.session_state.selected_file_info
            
            # File info display
            info_col1, info_col2, info_col3 = st.columns(3)
            with info_col1:
                st.metric("📄 Filename", file_info['name'])
            with info_col2:
                st.metric("📊 Size", f"{file_info['size_mb']:.2f} MB")
            with info_col3:
                st.metric("📋 Type", file_info['type'])
            
            st.info(f"**📁 Path:** {selected_file_path}")
            st.info(f"**📅 Modified:** {file_info['modified']}")
            
            # Analysis section
            st.subheader("🤖 AI Analysis Configuration")
            
            analysis_type = st.selectbox(
                "Choose Analysis Type:",
                [
                    "Document Summary",
                    "Key Information Extraction",
                    "Automation Opportunities",
                    "Content Analysis"
                ],
                help="Select the type of analysis you want Gemini AI to perform"
            )
            
            # Analysis button
            if st.button("🚀 START GEMINI AI ANALYSIS", type="primary", use_container_width=True):
                with st.spinner("🤖 Analyzing with Gemini AI..."):
                    
                    # Progress tracking
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Step 1: File preparation
                    status_text.text("📄 Preparing file...")
                    progress_bar.progress(20)
                    time.sleep(0.5)
                    
                    # Step 2: Content extraction
                    status_text.text("📖 Extracting content...")
                    progress_bar.progress(40)
                    
                    try:
                        if file_info['type'] == "PDF":
                            content = analyzer.extract_text_from_pdf(selected_file_path)
                            if not content or len(content.strip()) == 0:
                                content = f"PDF file: {file_info['name']} - Content extraction completed but no text found."
                        else:
                            content = f"File: {file_info['name']} - Non-PDF document ready for analysis."
                    except Exception as e:
                        content = f"Error extracting content from {file_info['name']}: {str(e)}"
                        st.warning(f"⚠️ Content extraction issue: {str(e)}")
                    
                    progress_bar.progress(60)
                    status_text.text("🤖 Sending to Gemini AI...")
                    time.sleep(0.5)
                    
                    # Step 3: AI Analysis
                    analysis_result = analyzer.analyze_with_gemini(content, file_info, analysis_type)
                    
                    progress_bar.progress(80)
                    status_text.text("📝 Processing results...")
                    time.sleep(0.5)
                    
                    progress_bar.progress(100)
                    status_text.text("✅ Analysis complete!")
                    time.sleep(0.5)
                    
                    # Clear progress
                    progress_bar.empty()
                    status_text.empty()
                    
                    # Show results
                    if analysis_result and not analysis_result.startswith("Error"):
                        st.success("🎉 **Analysis Completed Successfully!**")
                        
                        st.markdown("### 📊 Gemini AI Analysis Results")
                        st.markdown("---")
                        st.markdown(analysis_result)
                        st.markdown("---")
                        
                        # Download section
                        st.subheader("💾 Download Analysis Report")
                        
                        timestamp = int(time.time())
                        safe_filename = "".join(c for c in file_info['name'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        download_filename = f"analysis_{safe_filename}_{timestamp}.txt"
                        
                        download_content = f"""GEMINI AI ANALYSIS REPORT
========================

File: {file_info['name']}
Analysis Type: {analysis_type}
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
File Size: {file_info['size_mb']:.2f} MB
File Path: {selected_file_path}

ANALYSIS RESULTS:
{analysis_result}

---
Generated by Auto File Analyzer with Gemini AI
"""
                        
                        st.download_button(
                            label="💾 Download Complete Report",
                            data=download_content,
                            file_name=download_filename,
                            mime="text/plain",
                            use_container_width=True
                        )
                        
                        # Action buttons
                        action_col1, action_col2 = st.columns(2)
                        with action_col1:
                            if st.button("🔄 Analyze Again", key="analyze_again"):
                                st.rerun()
                        with action_col2:
                            if st.button("📄 Select New File", key="new_file"):
                                # Clear session state
                                for key in ['selected_file', 'selected_file_info', 'is_uploaded']:
                                    if hasattr(st.session_state, key):
                                        delattr(st.session_state, key)
                                st.rerun()
                        
                        # Log success
                        analyzer.log_analysis(selected_file_path, analysis_type, True, len(analysis_result))
                        st.balloons()
                        
                    else:
                        st.error(f"❌ Analysis failed: {analysis_result}")
                        analyzer.log_analysis(selected_file_path, analysis_type, False)
                        
                        if st.button("🔄 Retry Analysis", key="retry"):
                            st.rerun()
    
    with col2:
        st.header("ℹ️ Features")
        st.markdown("""
        **🔍 Search Methods:**
        - Direct file path entry
        - Filename search (quick/deep)
        - Extension-based search
        - Manual file upload
        
        **🔧 Search Capabilities:**
        - Full computer scan
        - All drives (Windows)
        - System directories
        - User folders priority
        - Permission handling
        - Duplicate removal
        
        **📊 Analysis Types:**
        - Document Summary
        - Key Information Extraction
        - Automation Opportunities
        - Content Analysis
        
        **🤖 AI Features:**
        - Gemini 2.0 Flash
        - PDF text extraction
        - Multiple file types
        - Progress tracking
        - Error handling
        - Download reports
        
        **💡 Tips:**
        - Use Quick Search first
        - Try Deep Search if needed
        - Extension search for file types
        - Upload for cloud files
        """)
        
        st.header("🎯 How to Use")
        st.markdown("""
        1. **Choose a search method** from the tabs above
        2. **Find your file** using one of the search options
        3. **Select the file** you want to analyze
        4. **Choose analysis type** based on your needs
        5. **Click analyze** and wait for results
        6. **Download the report** when complete
        """)
        
        st.header("⚡ Performance")
        if analyzer.analysis_history:
            avg_length = sum(a.get('result_length', 0) for a in analyzer.analysis_history if a['success']) / max(1, len([a for a in analyzer.analysis_history if a['success']]))
            st.metric("Avg Report Length", f"{avg_length:.0f} chars")
        
        st.markdown("""
        **Search Speed:**
        - Quick: 2-10 seconds
        - Deep: 30+ seconds
        - Extension: Variable
        
        **Analysis Time:**
        - Small files: 5-15 seconds
        - Large files: 15-30 seconds
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <h3>🤖 Auto File Analyzer Pro</h3>
        <p><strong>Enhanced File Search + Gemini AI Analysis + Full Computer Access</strong></p>
        <p>Find any file anywhere on your computer and get instant AI-powered insights</p>
        <p><em>Perfect for automation, document processing, and intelligent file management</em></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
