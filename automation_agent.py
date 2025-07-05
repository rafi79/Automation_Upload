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
    page_title="PC Automation Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

class AutomationAgent:
    def __init__(self):
        # Use environment variable or fallback to provided key
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
            
        self.automation_history = []
        self.setup_directories()
        
    def setup_directories(self):
        """Create necessary directories for file operations"""
        self.temp_dir = Path(tempfile.gettempdir()) / "automation_agent"
        self.temp_dir.mkdir(exist_ok=True)
        self.pdfs_dir = self.temp_dir / "pdfs"
        self.pdfs_dir.mkdir(exist_ok=True)
        
    def extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF file"""
        try:
            text = ""
            
            # Try PyMuPDF first (more reliable)
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
                
            return "PDF text extraction libraries not available."
            
        except Exception as e:
            return f"Error extracting text from PDF: {str(e)}"
    
    def analyze_pdf_with_gemini(self, pdf_path, analysis_type="Document Summary"):
        """Analyze PDF with Gemini AI"""
        if not self.gemini_client:
            return "Gemini AI not available. Please check your API key configuration."
            
        try:
            # Extract text from PDF
            pdf_text = self.extract_text_from_pdf(pdf_path)
            
            if not pdf_text or pdf_text.startswith("Error") or pdf_text.startswith("PDF text"):
                return f"Could not extract text from PDF: {pdf_text}"
            
            # Create analysis prompt based on type
            prompts = {
                "Document Summary": f"""
                Please provide a comprehensive summary of this document:
                
                {pdf_text[:8000]}
                
                Include:
                1. Main topic and purpose
                2. Key points and findings
                3. Important details
                4. Conclusion or recommendations
                """,
                
                "Key Information Extraction": f"""
                Extract all key information from this document:
                
                {pdf_text[:8000]}
                
                Please identify and list:
                1. Names and people mentioned
                2. Dates and deadlines
                3. Numbers, amounts, and quantities
                4. Addresses and locations
                5. Important facts and data points
                
                Format as a structured list.
                """,
                
                "Automation Opportunities": f"""
                Analyze this document for automation opportunities:
                
                {pdf_text[:8000]}
                
                Identify:
                1. Repetitive processes mentioned
                2. Manual tasks that could be automated
                3. Data entry opportunities
                4. Workflow improvements
                5. Integration possibilities
                6. Specific automation recommendations
                """,
                
                "Action Items": f"""
                Identify all action items and tasks from this document:
                
                {pdf_text[:8000]}
                
                Extract:
                1. Tasks to be completed
                2. Deadlines and due dates
                3. Responsible parties
                4. Follow-up requirements
                5. Next steps
                
                Format as a prioritized list.
                """
            }
            
            prompt = prompts.get(analysis_type, prompts["Document Summary"])
            
            # Generate response using Gemini
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ]
            
            generate_content_config = types.GenerateContentConfig(
                response_mime_type="text/plain",
            )
            
            response = self.gemini_client.models.generate_content(
                model=self.model,
                contents=contents,
                config=generate_content_config,
            )
            
            return response.text
            
        except Exception as e:
            return f"Error analyzing PDF: {str(e)}"
    
    def log_analysis(self, filename, analysis_type, result):
        """Log analysis to history"""
        self.automation_history.append({
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "filename": filename,
            "analysis_type": analysis_type,
            "result_length": len(result) if result else 0,
            "status": "success" if result and not result.startswith("Error") else "error"
        })

# Initialize the automation agent
@st.cache_resource
def get_agent():
    return AutomationAgent()

def main():
    st.title("🤖 PC Automation Agent - PDF Analyzer")
    st.markdown("**RoboTask Integration Ready** - Upload PDFs and get AI-powered analysis")
    
    # Check dependencies
    if not GEMINI_AVAILABLE:
        st.error("⚠️ Google Gemini AI not available. Please install: pip install google-genai")
        return
    
    agent = get_agent()
    
    # Sidebar
    with st.sidebar:
        st.header("📊 Analysis Dashboard")
        
        # API Key status
        if agent.gemini_client:
            st.success("✅ Gemini AI Connected")
        else:
            st.error("❌ Gemini AI Not Available")
        
        # Statistics
        if agent.automation_history:
            total_analyses = len(agent.automation_history)
            successful = len([a for a in agent.automation_history if a['status'] == 'success'])
            st.metric("Total Analyses", total_analyses)
            st.metric("Success Rate", f"{(successful/total_analyses*100):.0f}%")
            
            st.subheader("📈 Recent Activity")
            for analysis in agent.automation_history[-3:]:
                st.write(f"**{analysis['timestamp']}**")
                st.write(f"File: {analysis['filename']}")
                st.write(f"Type: {analysis['analysis_type']}")
                st.write(f"Status: {analysis['status']}")
                st.write("---")
        else:
            st.info("No analyses completed yet")
        
        st.header("🔧 RoboTask Setup")
        st.markdown("""
        **Hotkey**: Ctrl+Alt+U
        
        **What RoboTask does**:
        1. Opens this page
        2. Uploads PDF from Downloads
        3. Selects analysis type
        4. Triggers AI analysis
        5. Shows results
        """)
    
    # Main content
    st.header("📄 PDF Analysis with Gemini AI")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📁 Upload PDF Document")
        
        # File uploader
        uploaded_file = st.file_uploader(
            "Choose a PDF file", 
            type=['pdf'],
            help="Select a PDF file from your computer"
        )
        
        if uploaded_file:
            # Save uploaded file
            pdf_path = agent.pdfs_dir / f"uploaded_{uuid.uuid4().hex[:8]}.pdf"
            with open(pdf_path, "wb") as f:
                f.write(uploaded_file.read())
            
            # File info
            file_size = len(uploaded_file.getvalue()) / 1024 / 1024  # MB
            st.success(f"✅ **{uploaded_file.name}** uploaded successfully!")
            st.info(f"📊 File size: {file_size:.2f} MB")
            
            # Analysis type selection
            st.subheader("🎯 Select Analysis Type")
            analysis_type = st.selectbox(
                "Choose analysis type:",
                [
                    "Document Summary",
                    "Key Information Extraction", 
                    "Automation Opportunities",
                    "Action Items"
                ],
                help="Select what type of analysis you want Gemini AI to perform"
            )
            
            # Big analyze button for RoboTask to click
            if st.button("🔍 **ANALYZE PDF WITH GEMINI AI**", type="primary", use_container_width=True):
                with st.spinner("🤖 Analyzing PDF with Gemini AI... Please wait..."):
                    
                    # Show progress
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    status_text.text("📄 Extracting text from PDF...")
                    progress_bar.progress(25)
                    time.sleep(1)
                    
                    status_text.text("🤖 Sending to Gemini AI...")
                    progress_bar.progress(50)
                    
                    # Perform analysis
                    analysis_result = agent.analyze_pdf_with_gemini(pdf_path, analysis_type)
                    
                    progress_bar.progress(75)
                    status_text.text("📝 Processing results...")
                    time.sleep(1)
                    
                    progress_bar.progress(100)
                    status_text.text("✅ Analysis complete!")
                    
                    # Clear progress indicators
                    progress_bar.empty()
                    status_text.empty()
                    
                    if analysis_result and not analysis_result.startswith("Error"):
                        st.success("🎉 **Analysis Complete!**")
                        
                        # Show results
                        st.markdown("### 📋 Analysis Results")
                        st.markdown("---")
                        st.markdown(analysis_result)
                        st.markdown("---")
                        
                        # Download button
                        timestamp = int(time.time())
                        filename = f"analysis_{uploaded_file.name}_{timestamp}.txt"
                        
                        st.download_button(
                            label="💾 **Download Analysis Results**",
                            data=analysis_result,
                            file_name=filename,
                            mime="text/plain",
                            use_container_width=True
                        )
                        
                        # Log the analysis
                        agent.log_analysis(uploaded_file.name, analysis_type, analysis_result)
                        
                        # Show success message for RoboTask
                        st.balloons()
                        st.success("🚀 **PDF Analysis Completed Successfully!**")
                        
                    else:
                        st.error(f"❌ Analysis failed: {analysis_result}")
            
            # Text preview section
            st.subheader("📖 Text Preview")
            if st.button("👁️ Preview Extracted Text"):
                with st.spinner("Extracting text..."):
                    extracted_text = agent.extract_text_from_pdf(pdf_path)
                    
                    if extracted_text and not extracted_text.startswith("Error"):
                        # Show first 1000 characters
                        preview = extracted_text[:1000] + "..." if len(extracted_text) > 1000 else extracted_text
                        st.text_area("Extracted Text", preview, height=200)
                        
                        st.download_button(
                            label="📄 Download Full Text",
                            data=extracted_text,
                            file_name=f"text_{uploaded_file.name}_{int(time.time())}.txt",
                            mime="text/plain"
                        )
                    else:
                        st.error(f"Could not extract text: {extracted_text}")
    
    with col2:
        st.subheader("ℹ️ How It Works")
        st.markdown("""
        **🔄 Automated Process:**
        1. RoboTask opens this page
        2. Selects PDF from Downloads folder
        3. Uploads file automatically
        4. Chooses analysis type
        5. Triggers Gemini AI analysis
        6. Results appear here
        
        **🎯 Analysis Types:**
        - **Document Summary**: Overview and key points
        - **Key Information**: Names, dates, numbers
        - **Automation Opportunities**: Process improvements
        - **Action Items**: Tasks and deadlines
        
        **📁 Supported Files:**
        - Text-based PDFs
        - Scanned documents
        - Forms and reports
        - Contracts and invoices
        - Research papers
        """)
        
        st.subheader("🚀 RoboTask Commands")
        st.code("""
# RoboTask Actions:
1. Open Browser → This URL
2. Click File Upload
3. Navigate to Downloads
4. Select *.pdf files
5. Click ANALYZE button
6. Wait for results
        """)
        
        if not PDF_AVAILABLE:
            st.warning("⚠️ Install PyMuPDF for better PDF processing: `pip install PyMuPDF`")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <h4>🤖 PC Automation Agent</h4>
        <p>Powered by Google Gemini AI | Automated with RoboTask</p>
        <p><strong>Press Ctrl+Alt+U</strong> to trigger automatic PDF analysis</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
