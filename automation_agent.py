import streamlit as st
import base64
import os
import json
import tempfile
import time
from pathlib import Path
from PIL import Image
import requests
import io
import numpy as np
import uuid
from google import genai
from google.genai import types

# Configure Streamlit page
st.set_page_config(
    page_title="PC Automation Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

class CloudAutomationAgent:
    def __init__(self):
        # Use environment variable or fallback to provided key
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "AIzaSyDFgcA8F1RD0t0UmMbomQ54dHoGPZRT0ok")
        self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        self.model = "gemini-2.0-flash"
        self.automation_history = []
        self.setup_directories()
        
    def setup_directories(self):
        """Create necessary directories for file operations"""
        self.temp_dir = Path(tempfile.gettempdir()) / "pc_automation_agent"
        self.temp_dir.mkdir(exist_ok=True)
        self.images_dir = self.temp_dir / "images"
        self.images_dir.mkdir(exist_ok=True)
        
    def process_image_with_gemini(self, image_path, prompt="Describe this image and suggest automation tasks"):
        """Process image with Gemini AI"""
        try:
            # Read and encode image
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode()
            
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(
                            data=base64.b64decode(image_data),
                            mime_type="image/png"
                        ),
                    ],
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
            st.error(f"Error processing image with Gemini: {str(e)}")
            return None
            
    def generate_gemini_response(self, prompt):
        """Generate response using Gemini AI"""
        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                    ],
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
            st.error(f"Error generating Gemini response: {str(e)}")
            return None
            
    def create_robotask_script(self, task_description, automation_steps):
        """Create RoboTask automation script"""
        script_template = f"""
RoboTask Automation Script
Generated for: {task_description}
Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}

Task Description:
{task_description}

Automation Steps:
{automation_steps}

Implementation Instructions:
1. Copy this script content
2. Open RoboTask on your local machine
3. Create a new task
4. Implement the steps described above
5. Test the automation carefully
6. Schedule or trigger as needed

Note: This is a template. Adjust coordinates, window titles, 
and specific actions according to your system configuration.
"""
        return script_template
        
    def generate_automation_steps(self, task_description):
        """Generate automation steps using Gemini AI"""
        prompt = f"""
        Generate detailed RoboTask automation steps for the following task: {task_description}
        
        Please provide specific, actionable steps including:
        1. Window management (finding and activating specific windows)
        2. Mouse clicks with approximate coordinates
        3. Keyboard input and shortcuts
        4. File operations if needed
        5. Error handling suggestions
        6. Wait conditions and timing
        
        Format the response as a numbered list with clear, implementable steps.
        Include RoboTask-specific commands and syntax where appropriate.
        """
        
        response = self.generate_gemini_response(prompt)
        return response if response else "No automation steps generated"
        
    def generate_browser_automation_code(self, task_description):
        """Generate browser automation code"""
        prompt = f"""
        Generate Python Selenium automation code for: {task_description}
        
        The code should:
        1. Set up Chrome WebDriver with appropriate options
        2. Navigate to relevant websites
        3. Locate elements using appropriate selectors
        4. Perform actions (click, type, submit)
        5. Handle potential errors and timeouts
        6. Include proper cleanup
        
        Provide complete, runnable Python code with comments.
        Use webdriver-manager for ChromeDriver setup.
        Include error handling and best practices.
        """
        
        response = self.generate_gemini_response(prompt)
        return response if response else "# No automation code generated"
        
    def log_automation_task(self, task_type, description, result):
        """Log automation task to history"""
        self.automation_history.append({
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "task_type": task_type,
            "description": description,
            "result": result,
            "status": "success" if result else "error"
        })

# Initialize the automation agent
@st.cache_resource
def get_automation_agent():
    return CloudAutomationAgent()

# Main Streamlit App
def main():
    st.title("🤖 PC Automation Agent with Gemini AI")
    st.markdown("**Cloud Edition** - Generate automation scripts and browser automation code")
    
    # API Key configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # API Key input
        api_key_input = st.text_input(
            "Gemini API Key (optional)", 
            type="password",
            help="Enter your Gemini API key or use the default one"
        )
        
        if api_key_input:
            os.environ["GEMINI_API_KEY"] = api_key_input
            st.success("✅ Custom API key set!")
        
        st.markdown("---")
        
        # Features info
        st.header("🌟 Features")
        st.markdown("""
        - 🎯 **Task Analysis**: Describe any automation task
        - 📝 **Script Generation**: Get RoboTask automation scripts
        - 🌐 **Browser Automation**: Generate Selenium code
        - 📸 **Image Analysis**: Upload screenshots for automation insights
        - 🤖 **AI-Powered**: Uses Google Gemini AI
        """)
        
        st.markdown("---")
        
        # Usage tips
        st.header("💡 Usage Tips")
        st.markdown("""
        1. **Be Specific**: Describe your automation task in detail
        2. **Include Context**: Mention applications, websites, or file types
        3. **Test Safely**: Always test generated scripts in a safe environment
        4. **Customize**: Adapt generated code to your specific needs
        """)
    
    # Get automation agent
    agent = get_automation_agent()
    
    # Main content area
    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Task Analysis", "📝 Script Generation", "🌐 Browser Automation", "📸 Image Analysis"])
    
    with tab1:
        st.header("🎯 Automation Task Analysis")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Describe Your Automation Task")
            task_description = st.text_area(
                "What do you want to automate?",
                height=150,
                placeholder="Example: I want to automatically organize my desktop files by moving all PDFs to a Documents folder, all images to a Pictures folder, and delete files older than 30 days..."
            )
            
            complexity = st.selectbox(
                "Task Complexity",
                ["Simple", "Intermediate", "Advanced"],
                help="Choose the level of detail you need in the automation plan"
            )
            
            if st.button("🔍 Analyze Task", type="primary"):
                if task_description:
                    with st.spinner("Analyzing your automation task..."):
                        analysis_prompt = f"""
                        Analyze this automation task and provide a comprehensive plan:
                        
                        Task: {task_description}
                        Complexity Level: {complexity}
                        
                        Please provide:
                        1. **Task Analysis**: Break down what needs to be automated
                        2. **Approach Options**: Different ways to implement this automation
                        3. **Required Tools**: What software/tools are needed
                        4. **Step-by-Step Plan**: Detailed implementation steps
                        5. **Potential Challenges**: Issues to watch out for
                        6. **Testing Strategy**: How to safely test the automation
                        7. **Maintenance Tips**: How to keep it working over time
                        
                        Format the response with clear headings and bullet points.
                        """
                        
                        analysis = agent.generate_gemini_response(analysis_prompt)
                        
                        if analysis:
                            st.markdown("### 🤖 AI Analysis Results")
                            st.markdown(analysis)
                            
                            # Log the task
                            agent.log_automation_task("task_analysis", task_description, analysis)
                        else:
                            st.error("Failed to analyze the task. Please try again.")
                else:
                    st.warning("Please describe your automation task first.")
        
        with col2:
            st.subheader("📊 Quick Stats")
            if agent.automation_history:
                total_tasks = len(agent.automation_history)
                successful_tasks = len([t for t in agent.automation_history if t['status'] == 'success'])
                st.metric("Total Tasks Analyzed", total_tasks)
                st.metric("Success Rate", f"{(successful_tasks/total_tasks*100):.1f}%")
                
                st.subheader("📝 Recent Tasks")
                for task in agent.automation_history[-3:]:
                    st.write(f"**{task['timestamp']}**")
                    st.write(f"Type: {task['task_type']}")
                    st.write(f"Status: {task['status']}")
                    st.write("---")
            else:
                st.info("No tasks analyzed yet. Start by describing an automation task!")
    
    with tab2:
        st.header("📝 RoboTask Script Generation")
        
        script_task = st.text_area(
            "Describe the automation task for RoboTask:",
            height=100,
            placeholder="Example: Monitor CPU usage every 5 minutes and send an email alert if it exceeds 80%"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            script_type = st.selectbox("Script Type", [
                "Desktop Automation",
                "File Management", 
                "System Monitoring",
                "Application Control",
                "Data Processing"
            ])
            
        with col2:
            include_error_handling = st.checkbox("Include Error Handling", value=True)
            include_logging = st.checkbox("Include Detailed Logging", value=True)
        
        if st.button("🛠️ Generate RoboTask Script", type="primary"):
            if script_task:
                with st.spinner("Generating RoboTask automation script..."):
                    # Generate automation steps
                    automation_steps = agent.generate_automation_steps(script_task)
                    
                    # Create full script
                    script_content = agent.create_robotask_script(script_task, automation_steps)
                    
                    st.markdown("### 📄 Generated RoboTask Script")
                    st.code(script_content, language="text")
                    
                    # Download button
                    st.download_button(
                        label="💾 Download Script",
                        data=script_content,
                        file_name=f"robotask_automation_{int(time.time())}.txt",
                        mime="text/plain"
                    )
                    
                    # Implementation instructions
                    st.markdown("### 🔧 Implementation Instructions")
                    st.markdown("""
                    1. **Copy the script content** using the download button
                    2. **Open RoboTask** on your local machine
                    3. **Create a new task** and configure the steps manually
                    4. **Test thoroughly** in a safe environment
                    5. **Adjust coordinates and timing** as needed for your system
                    6. **Set up triggers** (schedule, hotkey, file watch, etc.)
                    """)
                    
                    # Log the task
                    agent.log_automation_task("script_generation", script_task, script_content)
            else:
                st.warning("Please describe the automation task first.")
    
    with tab3:
        st.header("🌐 Browser Automation")
        
        browser_task = st.text_area(
            "Describe the web automation task:",
            height=100,
            placeholder="Example: Login to Gmail, search for emails from last week, download all PDF attachments"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            browser_type = st.selectbox("Browser", ["Chrome", "Firefox", "Edge"])
            headless_mode = st.checkbox("Headless Mode", help="Run browser in background")
            
        with col2:
            wait_timeout = st.slider("Element Wait Timeout (seconds)", 5, 30, 10)
            include_screenshots = st.checkbox("Include Screenshot Debugging", value=True)
        
        if st.button("🚀 Generate Browser Automation", type="primary"):
            if browser_task:
                with st.spinner("Generating browser automation code..."):
                    automation_code = agent.generate_browser_automation_code(browser_task)
                    
                    st.markdown("### 💻 Generated Selenium Code")
                    st.code(automation_code, language="python")
                    
                    # Download button
                    st.download_button(
                        label="💾 Download Python Script",
                        data=automation_code,
                        file_name=f"browser_automation_{int(time.time())}.py",
                        mime="text/python"
                    )
                    
                    # Setup instructions
                    st.markdown("### 🛠️ Setup Instructions")
                    st.markdown("""
                    1. **Install dependencies:**
                       ```bash
                       pip install selenium webdriver-manager
                       ```
                    
                    2. **Save the code** to a `.py` file
                    
                    3. **Run the script:**
                       ```bash
                       python your_automation_script.py
                       ```
                    
                    4. **Customize as needed** for your specific requirements
                    """)
                    
                    # Log the task
                    agent.log_automation_task("browser_automation", browser_task, automation_code)
            else:
                st.warning("Please describe the browser automation task first.")
    
    with tab4:
        st.header("📸 Image Analysis for Automation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Upload Screenshot or Image")
            uploaded_file = st.file_uploader("Choose an image", type=['png', 'jpg', 'jpeg'])
            
            if uploaded_file:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded Image", use_column_width=True)
                
                # Save uploaded image
                image_path = agent.images_dir / f"uploaded_{uuid.uuid4().hex[:8]}.png"
                image.save(image_path)
                
                analysis_type = st.selectbox("Analysis Type", [
                    "General Automation Opportunities",
                    "UI Element Detection",
                    "Workflow Analysis",
                    "Process Documentation",
                    "Error Detection"
                ])
                
                custom_prompt = st.text_input(
                    "Custom analysis prompt (optional):",
                    placeholder="Focus on specific aspects you want analyzed"
                )
                
                if st.button("🔍 Analyze Image"):
                    base_prompts = {
                        "General Automation Opportunities": "Analyze this image and identify automation opportunities. Look for repetitive tasks, manual processes, or workflows that could be automated.",
                        "UI Element Detection": "Identify clickable elements, buttons, forms, and interactive components in this interface that could be automated.",
                        "Workflow Analysis": "Analyze the workflow shown in this image and suggest how it could be streamlined or automated.",
                        "Process Documentation": "Document the process shown in this image and suggest automation improvements.",
                        "Error Detection": "Look for potential errors, inefficiencies, or issues in this interface that automation could help resolve."
                    }
                    
                    analysis_prompt = custom_prompt if custom_prompt else base_prompts[analysis_type]
                    
                    with st.spinner("Analyzing image with AI..."):
                        response = agent.process_image_with_gemini(image_path, analysis_prompt)
                        
                        if response:
                            st.markdown("### 🤖 Image Analysis Results")
                            st.markdown(response)
                            
                            # Log the task
                            agent.log_automation_task("image_analysis", f"Analysis of {uploaded_file.name}", response)
                        else:
                            st.error("Failed to analyze the image. Please try again.")
        
        with col2:
            st.subheader("📋 Analysis Tips")
            st.markdown("""
            **Best images for automation analysis:**
            - Screenshots of applications or workflows
            - User interfaces with visible buttons and menus
            - Process diagrams or flowcharts
            - Error messages or system alerts
            - Repetitive manual tasks
            
            **What the AI can identify:**
            - Clickable elements and buttons
            - Form fields and input areas
            - Navigation patterns
            - Workflow inefficiencies
            - Automation opportunities
            - UI/UX improvements
            """)
            
            st.subheader("🎯 Example Use Cases")
            st.markdown("""
            - **Desktop Apps**: Analyze software interfaces for automation
            - **Web Forms**: Identify fields for auto-filling
            - **Workflows**: Document and optimize business processes
            - **Error Handling**: Automate error resolution
            - **Data Entry**: Find repetitive input patterns
            """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <h4>🤖 PC Automation Agent - Cloud Edition</h4>
        <p>Powered by Google Gemini AI | Generate automation scripts for RoboTask and Selenium</p>
        <p><strong>⚠️ Important:</strong> Always test generated scripts in a safe environment before production use!</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
