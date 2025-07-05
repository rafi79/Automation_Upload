import streamlit as st
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
        
        # For cloud/server environment, create dummy search locations
        if platform.system() == "Linux":
            # Check if we're in a cloud environment
            if os.path.exists("/tmp/mock_downloads"):
                # This is likely Streamlit Cloud - create safe mock locations
                search_locations = [
                    Path("/tmp/mock_downloads"),
                    Path("/tmp/mock_documents"),
                ]
            else:
                # Full Linux system search
                search_locations = [
                    Path("/home"),
                    Path("/usr"),
                    Path("/opt"),
                    Path("/var"),
                    Path("/tmp"),
                ]
                if deep_search:
                    search_locations.insert(0, Path("/"))  # Root directory for deep search
        
        elif platform.system() == "Windows":
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
        
        else:
            # Fallback for other systems
            search_locations = [
                Path.home(),
                Path("/tmp") if Path("/tmp").exists() else Path(tempfile.gettempdir()),
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
                                
                    except (PermissionError, OSError) as e:
                        st.warning(f"⚠️ Permission denied: {location}")
                        continue
                        
                # Break if we have enough results and not doing deep search
                if not deep_search and len(found_files) >= 20:
                    break
                    
            except (PermissionError, OSError) as e:
                st.warning(f"⚠️ Cannot access: {location}")
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
    
    def copy_file_to_temp(self, source_path):
        """Copy file to temporary directory for processing"""
        try:
            source = Path(source_path)
            temp_filename = f"uploaded_{uuid.uuid4().hex[:8]}_{source.name}"
            temp_path = self.temp_dir / temp_filename
            
            shutil.copy2(source, temp_path)
            return temp_path, None
        except Exception as e:
            return None, f"Error copying file: {str(e)}"
    
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
                "type": "PDF" if path.suffix.lower() == ".pdf" else "Image"
            }
        except Exception as e:
            return {"error": str(e)}
    
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
                {content[:8000]}
                
                Analysis Type: {analysis_type}
                """
            else:
                base_prompt = f"""
                Analyze this file: {file_info['name']}
                Analysis Type: {analysis_type}
                Please provide insights based on the filename and type.
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
    st.title("🤖 Auto File Analyzer with Gemini AI")
    st.markdown("**Smart File Processing** - Enhanced with Full Computer Search")
    
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
        
        st.header("🔍 Search Options")
        st.markdown("""
        **🎯 Search Modes:**
        - **Quick Search**: Common locations
        - **Deep Search**: Entire computer
        - **Extension Search**: Find by file type
        """)
        
        st.header("🤖 RoboTask Ready")
        st.markdown("""
        **Automation Steps:**
        1. Enter filename below
        2. System finds file automatically
        3. Click "Use This" on found file
        4. Select analysis type
        5. Click "AUTO ANALYZE"
        6. Download results
        """)
    
    # Main content
    st.header("📁 Enhanced File Processing")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🔍 Find Your File")
        
        # Method 1: Full path input
        st.markdown("**Method 1: Enter Full File Path**")
        file_path_input = st.text_input(
            "Full file path:",
            placeholder="C:\\Users\\Rafi7\\Downloads\\Telegram Desktop\\IQAC.pdf",
            help="Enter the complete path to your file"
        )
        
        # Method 2: Enhanced filename search
        st.markdown("**Method 2: Enhanced Filename Search**")
        
        search_col1, search_col2 = st.columns([3, 1])
        
        with search_col1:
            filename_only = st.text_input(
                "Just the filename:",
                placeholder="IQAC.pdf",
                help="Enter just the filename - we'll search for it automatically"
            )
        
        with search_col2:
            deep_search = st.checkbox("🔍 Deep Search", help="Search entire computer (slower)")
        
        # Search options
        search_options_col1, search_options_col2 = st.columns(2)
        
        with search_options_col1:
            max_results = st.selectbox("Max Results:", [10, 25, 50, 100], index=1)
        
        with search_options_col2:
            search_extension = st.text_input("Search by extension:", placeholder="pdf", help="Leave empty to search by filename")
        
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
        selected_file_path = None
        
        # Process extension search
        if search_extension and st.button("🔍 Search by Extension", type="secondary"):
            with st.spinner(f"Searching for .{search_extension} files..."):
                found_files = analyzer.search_by_extension(search_extension, max_results)
                
                if found_files:
                    st.success(f"✅ Found {len(found_files)} .{search_extension} files!")
                    
                    # Display found files
                    st.subheader("📁 Found Files")
                    for i, file_path in enumerate(found_files):
                        file_info = analyzer.get_file_info(file_path)
                        
                        with st.expander(f"📄 {file_info['name']} ({file_info['size_mb']:.2f} MB)"):
                            st.write(f"**📁 Path:** {file_path}")
                            st.write(f"**📅 Modified:** {file_info['modified']}")
                            
                            if st.button(f"✅ Use This File", key=f"use_ext_file_{i}"):
                                st.session_state.selected_file = str(file_path)
                                st.session_state.selected_file_info = file_info
                                st.rerun()
                else:
                    st.error(f"❌ No .{search_extension} files found")
        
        # Process filename search
        elif filename_only and not file_path_input:
            search_button_col1, search_button_col2 = st.columns(2)
            
            with search_button_col1:
                if st.button("🔍 Quick Search", type="primary"):
                    with st.spinner(f"Searching for {filename_only}..."):
                        found_files = analyzer.search_for_file(filename_only, max_results, deep_search=False)
                        
                        if found_files:
                            st.success(f"✅ Found {len(found_files)} matching files!")
                            
                            # Display found files
                            st.subheader("📁 Found Files")
                            for i, file_path in enumerate(found_files):
                                file_info = analyzer.get_file_info(file_path)
                                
                                with st.expander(f"📄 {file_info['name']} ({file_info['size_mb']:.2f} MB)"):
                                    st.write(f"**📁 Path:** {file_path}")
                                    st.write(f"**📅 Modified:** {file_info['modified']}")
                                    
                                    if st.button(f"✅ Use This File", key=f"use_file_{i}"):
                                        st.session_state.selected_file = str(file_path)
                                        st.session_state.selected_file_info = file_info
                                        st.rerun()
                        else:
                            st.warning("❌ No files found in quick search. Try Deep Search for comprehensive results.")
            
            with search_button_col2:
                if st.button("🔍 Deep Search", type="secondary"):
                    with st.spinner(f"Deep searching for {filename_only}... This may take a while..."):
                        found_files = analyzer.search_for_file(filename_only, max_results, deep_search=True)
                        
                        if found_files:
                            st.success(f"✅ Deep search found {len(found_files)} matching files!")
                            
                            # Display found files
                            st.subheader("📁 Found Files")
                            for i, file_path in enumerate(found_files):
                                file_info = analyzer.get_file_info(file_path)
                                
                                with st.expander(f"📄 {file_info['name']} ({file_info['size_mb']:.2f} MB)"):
                                    st.write(f"**📁 Path:** {file_path}")
                                    st.write(f"**📅 Modified:** {file_info['modified']}")
                                    
                                    if st.button(f"✅ Use This File", key=f"use_deep_file_{i}"):
                                        st.session_state.selected_file = str(file_path)
                                        st.session_state.selected_file_info = file_info
                                        st.rerun()
                        else:
                            st.error(f"❌ No files found even with deep search")
        
        # Process full path
        elif file_path_input:
            if st.button("✅ Validate File Path", type="primary"):
                is_valid, message, validated_path = analyzer.validate_file_path(file_path_input)
                
                if is_valid:
                    st.success(f"✅ {message}")
                    
                    file_info = analyzer.get_file_info(validated_path)
                    st.session_state.selected_file = validated_path
                    st.session_state.selected_file_info = file_info
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
        
        # Show selected file and analysis section
        if hasattr(st.session_state, 'selected_file') and hasattr(st.session_state, 'selected_file_info'):
            st.markdown("---")
            st.subheader("📁 Selected File")
            
            selected_file_path = st.session_state.selected_file
            file_info = st.session_state.selected_file_info
            
            st.success(f"✅ File ready for analysis: **{file_info['name']}**")
            
            # Show file info in a nice layout
            info_col1, info_col2, info_col3 = st.columns(3)
            with info_col1:
                st.metric("📄 File Name", file_info['name'])
            with info_col2:
                st.metric("📊 Size", f"{file_info['size_mb']:.2f} MB")
            with info_col3:
                st.metric("📋 Type", file_info['type'])
            
            st.write(f"**📅 Last Modified:** {file_info['modified']}")
            st.write(f"**📁 Path:** {selected_file_path}")
            
            # Analysis section
            st.subheader("🤖 AI Analysis")
            
            # Analysis type selector (make it more prominent)
            analysis_type_selected = st.selectbox(
                "🎯 Choose Analysis Type:",
                [
                    "Document Summary",
                    "Key Information Extraction",
                    "Automation Opportunities", 
                    "Content Analysis"
                ],
                key="analysis_type_selector",
                help="Select what type of analysis you want Gemini AI to perform"
            )
            
            # Big prominent analysis button
            if st.button("🚀 **START GEMINI AI ANALYSIS**", type="primary", use_container_width=True, key="main_analysis_button"):
                with st.spinner("🤖 Analyzing with Gemini AI... Please wait..."):
                    
                    # Progress bar for better UX
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Step 1: File preparation
                    status_text.text("📄 Preparing file for analysis...")
                    progress_bar.progress(20)
                    time.sleep(1)
                    
                    # Step 2: Content extraction
                    status_text.text("📖 Extracting content...")
                    progress_bar.progress(40)
                    
                    # Extract content from the actual file
                    try:
                        if file_info['type'] == "PDF":
                            content = analyzer.extract_text_from_pdf(selected_file_path)
                            if not content or len(content.strip()) == 0:
                                content = f"PDF file: {file_info['name']} - Content extraction may require different PDF processing method."
                        else:
                            # For image files or other types
                            content = f"File: {file_info['name']} - Image/document analysis based on filename and properties."
                    except Exception as e:
                        content = f"Error extracting content from {file_info['name']}: {str(e)}"
                        st.warning(f"⚠️ Content extraction issue: {str(e)}")
                    
                    if len(content.strip()) == 0:
                        content = f"File: {file_info['name']} - Ready for analysis based on file properties and metadata."
                    
                    progress_bar.progress(60)
                    status_text.text("🤖 Sending to Gemini AI...")
                    time.sleep(1)
                    
                    # Step 3: AI Analysis
                    analysis_result = analyzer.analyze_with_gemini(content, file_info, analysis_type_selected)
                    
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
                        
                        # Display results in a nice format
                        st.markdown(analysis_result)
                        
                        st.markdown("---")
                        
                        # Download section
                        st.subheader("💾 Download Results")
                        
                        # Create download data
                        timestamp = int(time.time())
                        safe_filename = "".join(c for c in file_info['name'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        download_filename = f"analysis_{safe_filename}_{timestamp}.txt"
                        
                        # Create formatted download content
                        download_content = f"""
GEMINI AI ANALYSIS REPORT
========================

File: {file_info['name']}
Analysis Type: {analysis_type_selected}
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
File Size: {file_info['size_mb']:.2f} MB

ANALYSIS RESULTS:
{analysis_result}

---
Generated by Auto File Analyzer with Gemini AI
                        """
                        
                        # Download button
                        st.download_button(
                            label="💾 **Download Complete Analysis Report**",
                            data=download_content,
                            file_name=download_filename,
                            mime="text/plain",
                            use_container_width=True,
                            key="download_results_button"
                        )
                        
                        # Additional options
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("🔄 Analyze Again", key="analyze_again"):
                                st.rerun()
                        with col_b:
                            if st.button("📄 Select New File", key="select_new_file"):
                                # Clear session state
                                if hasattr(st.session_state, 'selected_file'):
                                    del st.session_state.selected_file
                                    del st.session_state.selected_file_info
                                st.rerun()
                        
                        # Log success
                        analyzer.log_analysis(selected_file_path, analysis_type_selected, True, len(analysis_result))
                        
                        # Celebration
                        st.balloons()
                        
                    else:
                        st.error(f"❌ Analysis failed: {analysis_result}")
                        analyzer.log_analysis(selected_file_path, analysis_type_selected, False)
                        
                        # Retry option
                        if st.button("🔄 Try Again", key="retry_analysis"):
                            st.rerun()
        
        # Manual file upload fallback
        st.markdown("---")
        st.subheader("📤 Manual Upload (Alternative)")
        uploaded_file = st.file_uploader("Upload file directly", type=['pdf', 'png', 'jpg', 'jpeg', 'txt', 'docx'])
        
        if uploaded_file:
            st.success(f"📁 Uploaded: {uploaded_file.name}")
            
            if st.button("🔍 Analyze Uploaded File"):
                with st.spinner("🤖 Analyzing uploaded file..."):
                    # Create file info
                    file_info = {
                        "name": uploaded_file.name,
                        "size_mb": len(uploaded_file.getvalue()) / 1024 / 1024,
                        "modified": time.strftime('%Y-%m-%d %H:%M:%S'),
                        "extension": Path(uploaded_file.name).suffix.lower(),
                        "type": "PDF" if uploaded_file.type == "application/pdf" else "Document"
                    }
                    
                    # Save and process file
                    temp_path = analyzer.temp_dir / f"uploaded_{uuid.uuid4().hex[:8]}_{uploaded_file.name}"
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getvalue())
                    
                    # Extract content
                    try:
                        if file_info['type'] == "PDF":
                            content = analyzer.extract_text_from_pdf(temp_path)
                        else:
                            content = f"Uploaded file: {uploaded_file.name} - Document analysis based on filename and properties."
                    except Exception as e:
                        content = f"Error processing uploaded file: {str(e)}"
                    
                    # Analyze
                    analysis_result = analyzer.analyze_with_gemini(content, file_info, analysis_type)
                    
                    # Show results
                    if analysis_result and not analysis_result.startswith("Error"):
                        st.success("🎉 **Upload Analysis Completed!**")
                        st.markdown("### 📊 Analysis Results")
                        st.markdown("---")
                        st.markdown(analysis_result)
                        
                        # Download option
                        timestamp = int(time.time())
                        safe_filename = "".join(c for c in uploaded_file.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        download_filename = f"analysis_{safe_filename}_{timestamp}.txt"
                        
                        download_content = f"""
GEMINI AI ANALYSIS REPORT
========================

File: {uploaded_file.name}
Analysis Type: {analysis_type}
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
File Size: {file_info['size_mb']:.2f} MB

ANALYSIS RESULTS:
{analysis_result}

---
Generated by Auto File Analyzer with Gemini AI
                        """
                        
                        st.download_button(
                            label="💾 Download Analysis Report",
                            data=download_content,
                            file_name=download_filename,
                            mime="text/plain",
                            key="download_upload_results"
                        )
                        
                        # Log success
                        analyzer.log_analysis(str(temp_path), analysis_type, True, len(analysis_result))
                    else:
                        st.error(f"❌ Upload analysis failed: {analysis_result}")
                        analyzer.log_analysis(str(temp_path), analysis_type, False)
                    
                    # Cleanup
                    temp_path.unlink(missing_ok=True)
    
    with col2:
        st.subheader("ℹ️ How It Works")
        st.markdown("""
        **🎯 Three Methods:**
        
        **Method 1: Full Path**
        - Enter complete file path
        - System validates file exists
        - Processes immediately
        
        **Method 2: Filename Search**
        - Enter just the filename
        - Quick search: Common folders
        - Deep search: Entire computer
        - Shows all matches found
        
        **Method 3: Extension Search**
        - Search by file type (.pdf, .docx, etc.)
        - Finds all files of that type
        - System-wide search capability
        
        **🔍 Enhanced Search Locations:**
        - User Downloads folder
        - Telegram Desktop folder
        - Documents & Desktop
        - All system drives (Windows)
        - Root directory (Linux/Mac)
        - Program Files & System folders
        - Recursive subdirectory search
        
        **🤖 RoboTask Compatible:**
        - Clear input fields
        - Large buttons for automation
        - Predictable UI layout
        - Progress indicators
        - Multiple search options
        """)
        
        st.subheader("⚡ Analysis Types")
        st.markdown("""
        - **Document Summary**: Overview and key points
        - **Key Information**: Extract names, dates, numbers
        - **Automation Opportunities**: Process improvements
        - **Content Analysis**: Quality and structure review
        """)
        
        st.subheader("🔧 Technical Features")
        st.markdown("""
        **File Support:**
        - PDF documents (with text extraction)
        - Images (JPG, PNG)
        - Text files
        - Word documents (DOCX)
        
        **Search Capabilities:**
        - Full computer search
        - Multiple drive support
        - Permission handling
        - Duplicate removal
        - Result sorting by date
        
        **AI Analysis:**
        - Gemini 2.0 Flash model
        - Multiple analysis types
        - Progress tracking
        - Error handling
        - Download reports
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <h4>🤖 Auto File Analyzer Pro</h4>
        <p>Enhanced file processing + Full computer search + Gemini AI analysis + RoboTask automation ready</p>
        <p><strong>Perfect for automated document processing workflows across your entire system!</strong></p>
        <p><em>Search any file, anywhere on your computer, and get instant AI-powered analysis.</em></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
