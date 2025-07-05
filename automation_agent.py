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
import glob

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
    page_title="Auto PDF Analyzer",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

class AutoFileSelector:
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
        
    def get_downloads_folder(self):
        """Get the user's Downloads folder path"""
        home = Path.home()
        downloads_paths = [
            home / "Downloads",
            home / "Download", 
            Path("C:/Users") / os.getenv("USERNAME", "") / "Downloads",
            Path("/Users") / os.getenv("USER", "") / "Downloads"
        ]
        
        for path in downloads_paths:
            if path.exists():
                return path
        return home
        
    def scan_files(self, folder_path, file_types=["pdf", "png", "jpg", "jpeg"]):
        """Scan folder for files of specified types"""
        files = []
        folder = Path(folder_path)
        
        if not folder.exists():
            return files
            
        for file_type in file_types:
            pattern = f"*.{file_type}"
            found_files = list(folder.glob(pattern))
            files.extend(found_files)
            
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return files
        
    def filter_files(self, files, keyword="", date_filter="all", file_type="all"):
        """Filter files based on criteria"""
        filtered_files = []
        
        for file_path in files:
            # File type filter
            if file_type != "all":
                if not file_path.suffix.lower().endswith(file_type.lower()):
                    continue
                    
            # Keyword filter
            if keyword and keyword.lower() not in file_path.name.lower():
                continue
                
            # Date filter
            if date_filter != "all":
                file_time = file_path.stat().st_mtime
                current_time = time.time()
                
                if date_filter == "today":
                    if current_time - file_time > 86400:  # 24 hours
                        continue
                elif date_filter == "week":
                    if current_time - file_time > 604800:  # 7 days
                        continue
                elif date_filter == "month":
                    if current_time - file_time > 2592000:  # 30 days
                        continue
                        
            filtered_files.append(file_path)
            
        return filtered_files
        
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
                
            return "PDF processing not available."
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def analyze_with_gemini(self, content, file_type, analysis_type):
        """Analyze content with Gemini AI"""
        if not self.gemini_client:
            return "Gemini AI not available."
            
        try:
            if file_type == "pdf":
                prompt = f"""
                Analyze this PDF document content:
                
                {content[:8000]}
                
                Analysis Type: {analysis_type}
                
                Please provide:
                1. Document summary
                2. Key information extracted
                3. Important insights
                4. Recommendations for automation
                """
            else:  # image
                prompt = f"Analyze this image for automation opportunities and describe what you see. Analysis type: {analysis_type}"
            
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

@st.cache_resource
def get_auto_selector():
    return AutoFileSelector()

def main():
    st.title("🤖 Auto PDF/Image Analyzer")
    st.markdown("**Smart File Selection** - Automatically find and analyze your files")
    
    if not GEMINI_AVAILABLE:
        st.error("⚠️ Google Gemini AI not available.")
        return
    
    selector = get_auto_selector()
    
    # Sidebar for file selection criteria
    with st.sidebar:
        st.header("🔍 Smart File Finder")
        
        # Folder selection
        default_folder = selector.get_downloads_folder()
        st.write(f"**Scanning Folder:** {default_folder}")
        
        # File type filter
        file_type_filter = st.selectbox(
            "File Type:",
            ["all", "pdf", "png", "jpg", "jpeg"],
            help="Filter by file type"
        )
        
        # Keyword filter
        keyword_filter = st.text_input(
            "Keyword Filter:",
            placeholder="e.g., invoice, report, letter",
            help="Find files containing this word in filename"
        )
        
        # Date filter
        date_filter = st.selectbox(
            "Date Filter:",
            ["all", "today", "week", "month"],
            help="Filter by file modification date"
        )
        
        # Analysis type
        analysis_type = st.selectbox(
            "Analysis Type:",
            [
                "Document Summary",
                "Key Information Extraction",
                "Automation Opportunities", 
                "Data Processing"
            ]
        )
        
        st.markdown("---")
        st.subheader("🎯 Quick Filters")
        if st.button("📄 Latest PDFs"):
            st.session_state.quick_filter = "latest_pdfs"
        if st.button("📊 Invoice Files"):
            st.session_state.quick_filter = "invoices"
        if st.button("📝 Cover Letters"):
            st.session_state.quick_filter = "cover_letters"
        if st.button("🖼️ Recent Images"):
            st.session_state.quick_filter = "recent_images"
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📁 Smart File Selection")
        
        # Apply quick filters
        if hasattr(st.session_state, 'quick_filter'):
            if st.session_state.quick_filter == "latest_pdfs":
                file_type_filter = "pdf"
                date_filter = "today"
                keyword_filter = ""
            elif st.session_state.quick_filter == "invoices":
                file_type_filter = "pdf"
                keyword_filter = "invoice"
            elif st.session_state.quick_filter == "cover_letters":
                file_type_filter = "pdf"
                keyword_filter = "cover"
            elif st.session_state.quick_filter == "recent_images":
                file_type_filter = "png"
                date_filter = "week"
        
        # Scan and filter files
        if st.button("🔍 **SCAN & AUTO-SELECT FILES**", type="primary", use_container_width=True):
            with st.spinner("🔍 Scanning Downloads folder..."):
                # Get all files
                all_files = selector.scan_files(default_folder)
                
                # Apply filters
                filtered_files = selector.filter_files(
                    all_files, 
                    keyword_filter, 
                    date_filter, 
                    file_type_filter
                )
                
                if filtered_files:
                    st.success(f"✅ Found {len(filtered_files)} matching files!")
                    
                    # Display found files
                    st.subheader("📋 Found Files")
                    
                    for i, file_path in enumerate(filtered_files[:5]):  # Show top 5
                        file_size = file_path.stat().st_size / 1024 / 1024  # MB
                        file_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(file_path.stat().st_mtime))
                        
                        col_a, col_b, col_c = st.columns([3, 1, 1])
                        with col_a:
                            st.write(f"**{file_path.name}**")
                        with col_b:
                            st.write(f"{file_size:.1f} MB")
                        with col_c:
                            st.write(file_time)
                            
                        # Auto-analyze button for each file
                        if st.button(f"🤖 Analyze", key=f"analyze_{i}", use_container_width=True):
                            with st.spinner(f"🤖 Analyzing {file_path.name}..."):
                                
                                # Process file based on type
                                if file_path.suffix.lower() == '.pdf':
                                    content = selector.extract_text_from_pdf(file_path)
                                    file_type = "pdf"
                                else:
                                    # For images, we'd process differently
                                    content = f"Image file: {file_path.name}"
                                    file_type = "image"
                                
                                # Analyze with Gemini
                                analysis_result = selector.analyze_with_gemini(
                                    content, file_type, analysis_type
                                )
                                
                                # Show results
                                st.markdown("### 📊 Analysis Results")
                                st.markdown("---")
                                st.markdown(analysis_result)
                                st.markdown("---")
                                
                                # Download results
                                timestamp = int(time.time())
                                result_filename = f"analysis_{file_path.stem}_{timestamp}.txt"
                                
                                st.download_button(
                                    label="💾 Download Analysis",
                                    data=analysis_result,
                                    file_name=result_filename,
                                    mime="text/plain",
                                    use_container_width=True
                                )
                                
                                # Log analysis
                                selector.analysis_history.append({
                                    "file": file_path.name,
                                    "analysis_type": analysis_type,
                                    "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                                    "success": True
                                })
                                
                                st.balloons()
                                st.success("🎉 Analysis Complete!")
                else:
                    st.warning("No files found matching your criteria. Try adjusting the filters.")
        
        # Manual file upload fallback
        st.markdown("---")
        st.subheader("📤 Manual Upload (Fallback)")
        uploaded_file = st.file_uploader("Or upload a file manually", type=['pdf', 'png', 'jpg', 'jpeg'])
        
        if uploaded_file:
            st.info(f"📁 Uploaded: {uploaded_file.name}")
            
            if st.button("🔍 Analyze Uploaded File", use_container_width=True):
                with st.spinner("🤖 Analyzing uploaded file..."):
                    
                    # Save uploaded file temporarily
                    temp_path = Path(tempfile.gettempdir()) / f"temp_{uuid.uuid4().hex[:8]}_{uploaded_file.name}"
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.read())
                    
                    # Process based on file type
                    if uploaded_file.type == "application/pdf":
                        content = selector.extract_text_from_pdf(temp_path)
                        file_type = "pdf"
                    else:
                        content = f"Image file: {uploaded_file.name}"
                        file_type = "image"
                    
                    # Analyze
                    analysis_result = selector.analyze_with_gemini(content, file_type, analysis_type)
                    
                    # Show results
                    st.markdown("### 📊 Analysis Results")
                    st.markdown(analysis_result)
                    
                    # Download button
                    st.download_button(
                        label="💾 Download Analysis",
                        data=analysis_result,
                        file_name=f"analysis_{uploaded_file.name}_{int(time.time())}.txt",
                        mime="text/plain"
                    )
                    
                    # Cleanup
                    temp_path.unlink(missing_ok=True)
    
    with col2:
        st.subheader("🎯 Smart Selection")
        st.markdown("""
        **How it works:**
        1. 🔍 Scans your Downloads folder
        2. 🎯 Filters by your criteria
        3. 📋 Shows matching files
        4. 🤖 Analyzes with one click
        5. 💾 Downloads results
        
        **Filter Options:**
        - **File Type**: PDF, images, or all
        - **Keywords**: Find specific files
        - **Date**: Recent files only
        - **Quick Filters**: Common searches
        
        **Example Searches:**
        - "invoice" + PDF = Find all invoice PDFs
        - "today" + all = Today's downloads
        - "cover" + PDF = Cover letters
        """)
        
        st.subheader("📊 Analysis History")
        if selector.analysis_history:
            for analysis in selector.analysis_history[-3:]:
                st.write(f"**{analysis['timestamp']}**")
                st.write(f"File: {analysis['file']}")
                st.write(f"Type: {analysis['analysis_type']}")
                st.write("✅ Success" if analysis['success'] else "❌ Failed")
                st.write("---")
        else:
            st.info("No analyses completed yet")
    
    # RoboTask Instructions
    st.markdown("---")
    st.header("🤖 RoboTask Automation Setup")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("""
        **RoboTask Script:**
        ```
        1. Open Browser → This URL
        2. Set filters in sidebar:
           - File type: pdf
           - Keyword: invoice (or whatever you want)
           - Date: today
        3. Click "SCAN & AUTO-SELECT FILES"
        4. Click "Analyze" on desired file
        5. Wait for results
        6. Download analysis
        ```
        """)
    
    with col_b:
        st.markdown("""
        **Automation Benefits:**
        - ✅ No manual file browsing
        - ✅ Smart file filtering
        - ✅ Batch processing ready
        - ✅ Automatic analysis
        - ✅ Results download
        
        **Use Cases:**
        - Process daily invoices
        - Analyze cover letters
        - Review contracts
        - Extract data from forms
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p><strong>🤖 Auto PDF/Image Analyzer</strong> | Smart file selection + Gemini AI analysis</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
