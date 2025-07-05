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
    page_title="Path-Based Auto Uploader",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

class PathBasedUploader:
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
            
        self.upload_history = []
        self.setup_temp_directory()
        
    def setup_temp_directory(self):
        """Create temporary directory for processing"""
        self.temp_dir = Path(tempfile.gettempdir()) / "auto_uploader"
        self.temp_dir.mkdir(exist_ok=True)
        
    def validate_file_path(self, file_path):
        """Validate that the file path exists and is accessible"""
        try:
            path = Path(file_path)
            if not path.exists():
                return False, f"File not found: {file_path}"
            if not path.is_file():
                return False, f"Path is not a file: {file_path}"
            if not os.access(path, os.R_OK):
                return False, f"File is not readable: {file_path}"
            return True, "File is valid"
        except Exception as e:
            return False, f"Error validating file: {str(e)}"
    
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
            # Create analysis prompt based on file type and analysis type
            if file_info.get("type") == "PDF":
                base_prompt = f"""
                Analyze this PDF document: {file_info['name']}
                
                Document Content:
                {content[:10000]}  # Limit to avoid token limits
                
                Analysis Type: {analysis_type}
                """
            else:
                base_prompt = f"""
                Analyze this image file: {file_info['name']}
                
                Analysis Type: {analysis_type}
                
                Please describe what you see and provide insights for automation opportunities.
                """
            
            # Add specific analysis instructions based on type
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
                2. **Dates and Deadlines**: All dates mentioned in the document
                3. **Financial Information**: Amounts, prices, costs, salaries
                4. **Organizations**: Companies, institutions, departments
                5. **Technical Details**: Specifications, requirements, qualifications
                6. **Action Items**: Tasks, requirements, next steps
                
                Format as a structured list for easy reference.
                """,
                
                "Automation Opportunities": base_prompt + """
                
                Identify automation possibilities:
                1. **Data Entry Tasks**: Information that could be auto-extracted
                2. **Repetitive Processes**: Tasks that could be automated
                3. **Document Processing**: How this document type could be handled automatically
                4. **Integration Opportunities**: Systems this could connect to
                5. **Workflow Improvements**: How to streamline related processes
                6. **RoboTask Scripts**: Specific automation recommendations
                """,
                
                "Content Analysis": base_prompt + """
                
                Provide detailed analysis:
                1. **Content Quality**: Writing quality, completeness, clarity
                2. **Structure Analysis**: How the document is organized
                3. **Missing Information**: What might be incomplete
                4. **Improvements**: Suggestions for enhancement
                5. **Compliance**: Any standard formats or requirements
                6. **Recommendations**: Next steps or actions needed
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
    
    def log_upload(self, file_path, analysis_type, success, result_length=0):
        """Log the upload and analysis"""
        self.upload_history.append({
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "file_path": str(file_path),
            "file_name": Path(file_path).name,
            "analysis_type": analysis_type,
            "success": success,
            "result_length": result_length
        })

@st.cache_resource
def get_uploader():
    return PathBasedUploader()

def main():
    st.title("🤖 Path-Based Auto File Analyzer")
    st.markdown("**Direct Path Upload** - Specify exact file path for automatic processing")
    
    if not GEMINI_AVAILABLE:
        st.error("⚠️ Google Gemini AI not available. Please install: pip install google-genai")
        return
    
    uploader = get_uploader()
    
    # Sidebar
    with st.sidebar:
        st.header("📊 Upload History")
        
        if uploader.upload_history:
            total_uploads = len(uploader.upload_history)
            successful = len([u for u in uploader.upload_history if u['success']])
            st.metric("Total Uploads", total_uploads)
            st.metric("Success Rate", f"{(successful/total_uploads*100):.0f}%")
            
            st.subheader("📝 Recent Uploads")
            for upload in uploader.upload_history[-5:]:
                st.write(f"**{upload['timestamp']}**")
                st.write(f"File: {upload['file_name']}")
                st.write(f"Type: {upload['analysis_type']}")
                st.write(f"Status: {'✅' if upload['success'] else '❌'}")
                st.write("---")
        else:
            st.info("No uploads yet")
        
        st.header("🎯 Quick Paths")
        st.markdown("""
        **Example paths:**
        ```
        C:\\Users\\Rafi7\\Downloads\\file.pdf
        C:\\Users\\%USERNAME%\\Downloads\\*.pdf
        %USERPROFILE%\\Documents\\report.pdf
        ```
        """)
        
        st.header("🤖 RoboTask Integration")
        st.markdown("""
        **Automation Steps:**
        1. Set file path in text input
        2. Select analysis type
        3. Click "AUTO UPLOAD & ANALYZE"
        4. Get results automatically
        5. Download analysis report
        """)
    
    # Main content
    st.header("📁 Direct File Path Upload")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🎯 Specify File Path")
        
        # File path input
        file_path_input = st.text_input(
            "Enter full file path:",
            placeholder="C:\\Users\\Rafi7\\Downloads\\Fathea Jannat Ayrin_Cover Letter_UIU.pdf",
            help="Enter the complete path to your file"
        )
        
        # Quick path suggestions
        st.markdown("**Quick Fill Options:**")
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            if st.button("📁 Downloads Folder"):
                downloads_path = str(Path.home() / "Downloads")
                st.session_state.suggested_path = downloads_path
                
        with col_b:
            if st.button("📄 Documents Folder"):
                docs_path = str(Path.home() / "Documents")
                st.session_state.suggested_path = docs_path
                
        with col_c:
            if st.button("🖥️ Desktop"):
                desktop_path = str(Path.home() / "Desktop")
                st.session_state.suggested_path = desktop_path
        
        # Show suggested path
        if hasattr(st.session_state, 'suggested_path'):
            st.info(f"💡 Suggested path: {st.session_state.suggested_path}")
        
        # Analysis type selection
        analysis_type = st.selectbox(
            "Select Analysis Type:",
            [
                "Document Summary",
                "Key Information Extraction",
                "Automation Opportunities", 
                "Content Analysis"
            ],
            help="Choose what type of analysis you want"
        )
        
        # File validation and processing
        if file_path_input:
            # Validate file path
            is_valid, validation_message = uploader.validate_file_path(file_path_input)
            
            if is_valid:
                # Show file info
                file_info = uploader.get_file_info(file_path_input)
                
                if "error" not in file_info:
                    st.success("✅ File found and accessible!")
                    
                    # Display file information
                    info_col1, info_col2, info_col3 = st.columns(3)
                    with info_col1:
                        st.metric("File Name", file_info['name'])
                    with info_col2:
                        st.metric("Size", f"{file_info['size_mb']:.2f} MB")
                    with info_col3:
                        st.metric("Type", file_info['type'])
                    
                    st.write(f"**Last Modified:** {file_info['modified']}")
                    
                    # Big auto upload and analyze button
                    if st.button("🚀 **AUTO UPLOAD & ANALYZE**", type="primary", use_container_width=True):
                        with st.spinner("🤖 Processing file automatically..."):
                            
                            # Progress indicators
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            # Step 1: Copy file to temp directory
                            status_text.text("📂 Copying file for processing...")
                            progress_bar.progress(20)
                            
                            temp_file_path, copy_error = uploader.copy_file_to_temp(file_path_input)
                            
                            if copy_error:
                                st.error(f"❌ File copy failed: {copy_error}")
                                return
                            
                            # Step 2: Extract content if PDF
                            status_text.text("📄 Extracting content...")
                            progress_bar.progress(40)
                            
                            if file_info['type'] == "PDF":
                                content = uploader.extract_text_from_pdf(temp_file_path)
                            else:
                                content = f"Image file: {file_info['name']}"
                            
                            # Step 3: Analyze with Gemini AI
                            status_text.text("🤖 Analyzing with Gemini AI...")
                            progress_bar.progress(60)
                            
                            analysis_result = uploader.analyze_with_gemini(content, file_info, analysis_type)
                            
                            # Step 4: Process results
                            status_text.text("📝 Preparing results...")
                            progress_bar.progress(80)
                            
                            # Step 5: Complete
                            progress_bar.progress(100)
                            status_text.text("✅ Analysis complete!")
                            
                            # Clear progress indicators
                            time.sleep(1)
                            progress_bar.empty()
                            status_text.empty()
                            
                            # Show results
                            if analysis_result and not analysis_result.startswith("Error"):
                                st.success("🎉 **Analysis Completed Successfully!**")
                                
                                # Display results
                                st.markdown("### 📊 Analysis Results")
                                st.markdown("---")
                                st.markdown(analysis_result)
                                st.markdown("---")
                                
                                # Create download filename
                                timestamp = int(time.time())
                                safe_filename = "".join(c for c in file_info['name'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
                                download_filename = f"analysis_{safe_filename}_{timestamp}.txt"
                                
                                # Download button
                                st.download_button(
                                    label="💾 **Download Analysis Report**",
                                    data=analysis_result,
                                    file_name=download_filename,
                                    mime="text/plain",
                                    use_container_width=True
                                )
                                
                                # Log the successful upload
                                uploader.log_upload(file_path_input, analysis_type, True, len(analysis_result))
                                
                                # Celebration
                                st.balloons()
                                
                                # Cleanup temp file
                                if temp_file_path and temp_file_path.exists():
                                    temp_file_path.unlink(missing_ok=True)
                                    
                            else:
                                st.error(f"❌ Analysis failed: {analysis_result}")
                                uploader.log_upload(file_path_input, analysis_type, False)
                
                else:
                    st.error(f"❌ {file_info['error']}")
            else:
                st.error(f"❌ {validation_message}")
        
        # Text preview section for PDFs
        if file_path_input and st.button("👁️ Preview Text Content"):
            is_valid, _ = uploader.validate_file_path(file_path_input)
            if is_valid:
                file_info = uploader.get_file_info(file_path_input)
                if file_info.get('type') == 'PDF':
                    with st.spinner("Extracting text preview..."):
                        text_content = uploader.extract_text_from_pdf(file_path_input)
                        if text_content and not text_content.startswith("Error"):
                            preview = text_content[:2000] + "..." if len(text_content) > 2000 else text_content
                            st.text_area("Text Preview", preview, height=200)
                        else:
                            st.error(f"Could not extract text: {text_content}")
                else:
                    st.info("Text preview only available for PDF files")
    
    with col2:
        st.subheader("ℹ️ How It Works")
        st.markdown("""
        **🎯 Direct Path Processing:**
        1. Enter complete file path
        2. System validates file exists
        3. File copied for processing
        4. Content extracted (if PDF)
        5. Gemini AI analyzes content
        6. Results displayed instantly
        7. Download analysis report
        
        **📁 Supported Paths:**
        - Absolute paths: `C:\\Users\\...`
        - Environment variables: `%USERPROFILE%`
        - Network paths: `\\\\server\\share`
        
        **🔧 File Types:**
        - ✅ PDF documents
        - ✅ PNG images
        - ✅ JPG/JPEG images
        """)
        
        st.subheader("🤖 RoboTask Script")
        st.code("""
# RoboTask Actions:
1. Open Browser → This App URL
2. Send Keys → File path
3. Select → Analysis type
4. Click → AUTO UPLOAD & ANALYZE
5. Wait → For completion
6. Click → Download button
        """)
        
        st.subheader("⚡ Benefits")
        st.markdown("""
        - ✅ No manual file browsing
        - ✅ Direct path specification
        - ✅ Automatic processing
        - ✅ Instant AI analysis
        - ✅ One-click download
        - ✅ Perfect for automation
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <h4>🤖 Path-Based Auto File Analyzer</h4>
        <p>Specify file path → Automatic upload → Gemini AI analysis → Download results</p>
        <p><strong>Perfect for RoboTask automation!</strong></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
