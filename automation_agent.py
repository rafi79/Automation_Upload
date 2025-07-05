import streamlit as st
import base64
import os
import json
import subprocess
import tempfile
import time
from pathlib import Path
from PIL import Image
import speech_recognition as sr
import pyautogui
import psutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google import genai
from google.genai import types
import requests
import io
import numpy as np
import cv2
import threading
import queue
import sounddevice as sd
from scipy.io.wavfile import write
import uuid

# Configure Streamlit page
st.set_page_config(
    page_title="PC Automation Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

class PCAutomationAgent:
    def __init__(self):
        self.gemini_api_key = "AIzaSyDFgcA8F1RD0t0UmMbomQ54dHoGPZRT0ok"
        self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        self.model = "gemini-2.0-flash"
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.automation_history = []
        self.setup_directories()
        
    def setup_directories(self):
        """Create necessary directories for file operations"""
        self.temp_dir = Path(tempfile.gettempdir()) / "pc_automation_agent"
        self.temp_dir.mkdir(exist_ok=True)
        self.images_dir = self.temp_dir / "images"
        self.images_dir.mkdir(exist_ok=True)
        self.audio_dir = self.temp_dir / "audio"
        self.audio_dir.mkdir(exist_ok=True)
        
    def capture_screen(self):
        """Capture current screen"""
        screenshot = pyautogui.screenshot()
        filename = f"screenshot_{uuid.uuid4().hex[:8]}.png"
        filepath = self.images_dir / filename
        screenshot.save(filepath)
        return filepath
        
    def record_audio(self, duration=5, sample_rate=44100):
        """Record audio from microphone"""
        try:
            st.info(f"Recording audio for {duration} seconds...")
            audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1)
            sd.wait()
            
            filename = f"audio_{uuid.uuid4().hex[:8]}.wav"
            filepath = self.audio_dir / filename
            write(str(filepath), sample_rate, audio_data)
            
            st.success("Audio recorded successfully!")
            return filepath
        except Exception as e:
            st.error(f"Error recording audio: {str(e)}")
            return None
            
    def transcribe_audio(self, audio_file):
        """Transcribe audio to text using speech recognition"""
        try:
            with sr.AudioFile(str(audio_file)) as source:
                audio = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio)
                return text
        except Exception as e:
            st.error(f"Error transcribing audio: {str(e)}")
            return None
            
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
            
    def create_robotask_script(self, task_description):
        """Create RoboTask automation script"""
        script_template = f"""
// RoboTask Automation Script
// Generated for: {task_description}
// Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}

begin
    // Initialize task
    SetVar("TaskDescription", "{task_description}")
    SetVar("StartTime", Now())
    
    // Log task start
    WriteLog("Starting automation task: " + TaskDescription)
    
    // Main automation logic (customize based on task)
    {self.generate_automation_steps(task_description)}
    
    // Log task completion
    WriteLog("Completed automation task: " + TaskDescription)
    WriteLog("Execution time: " + FormatDateTime(Now() - StartTime))
end
"""
        
        filename = f"robotask_script_{uuid.uuid4().hex[:8]}.rtf"
        filepath = self.temp_dir / filename
        
        with open(filepath, 'w') as f:
            f.write(script_template)
            
        return filepath
        
    def generate_automation_steps(self, task_description):
        """Generate automation steps using Gemini AI"""
        prompt = f"""
        Generate RoboTask automation steps for the following task: {task_description}
        
        Please provide the steps in RoboTask script format. Include:
        1. Window management (finding and activating windows)
        2. Mouse clicks and movements
        3. Keyboard input
        4. File operations if needed
        5. Error handling
        6. Wait conditions
        
        Use RoboTask syntax and commands.
        """
        
        response = self.generate_gemini_response(prompt)
        return response if response else "// No automation steps generated"
        
    def execute_browser_automation(self, task_description):
        """Execute browser automation using Selenium"""
        try:
            # Setup Chrome options
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            # Create driver
            driver = webdriver.Chrome(options=chrome_options)
            
            # Generate automation steps using Gemini
            prompt = f"""
            Generate Python Selenium automation code for: {task_description}
            
            The code should:
            1. Navigate to appropriate websites
            2. Fill forms or click buttons as needed
            3. Handle file uploads if required
            4. Extract data if needed
            5. Include proper error handling
            
            Return only the Python code without explanations.
            """
            
            automation_code = self.generate_gemini_response(prompt)
            
            if automation_code:
                # Execute the generated code (be careful with eval in production)
                st.code(automation_code, language="python")
                
                # For safety, we'll display the code instead of executing it
                st.warning("Generated automation code displayed above. Review before execution.")
                
            driver.quit()
            
        except Exception as e:
            st.error(f"Error in browser automation: {str(e)}")
            
    def get_system_info(self):
        """Get current system information"""
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "active_windows": self.get_active_windows(),
            "running_processes": len(psutil.pids()),
        }
        
    def get_active_windows(self):
        """Get list of active windows (Windows-specific)"""
        try:
            import win32gui
            
            def enum_windows_proc(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    if window_title:
                        windows.append(window_title)
                return True
                
            windows = []
            win32gui.EnumWindows(enum_windows_proc, windows)
            return windows[:10]  # Return top 10 windows
            
        except ImportError:
            return ["Window enumeration not available (requires pywin32)"]
            
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
    return PCAutomationAgent()

# Main Streamlit App
def main():
    st.title("🤖 PC Automation Agent with Gemini AI")
    st.markdown("Automate your PC tasks using voice commands, image analysis, and AI-powered automation")
    
    # Get automation agent
    agent = get_automation_agent()
    
    # Sidebar for system information
    with st.sidebar:
        st.header("System Information")
        if st.button("Refresh System Info"):
            system_info = agent.get_system_info()
            st.json(system_info)
            
        st.header("Automation History")
        if agent.automation_history:
            for task in agent.automation_history[-5:]:  # Show last 5 tasks
                st.write(f"**{task['timestamp']}**")
                st.write(f"Type: {task['task_type']}")
                st.write(f"Status: {task['status']}")
                st.write("---")
        else:
            st.write("No automation tasks yet")
    
    # Main content area
    tab1, tab2, tab3, tab4 = st.tabs(["Voice Control", "Image Analysis", "Script Generation", "Browser Automation"])
    
    with tab1:
        st.header("🎤 Voice-Controlled Automation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Record Voice Command")
            duration = st.slider("Recording duration (seconds)", 1, 10, 5)
            
            if st.button("🎙️ Start Recording"):
                audio_file = agent.record_audio(duration)
                if audio_file:
                    st.audio(str(audio_file))
                    
                    # Transcribe audio
                    transcript = agent.transcribe_audio(audio_file)
                    if transcript:
                        st.success(f"Transcribed: {transcript}")
                        
                        # Generate automation response
                        prompt = f"""
                        User voice command: "{transcript}"
                        
                        Generate a detailed automation plan that includes:
                        1. What the user wants to automate
                        2. Step-by-step automation sequence
                        3. Required tools or applications
                        4. Expected outcomes
                        5. RoboTask script suggestions
                        """
                        
                        response = agent.generate_gemini_response(prompt)
                        if response:
                            st.markdown("### 🤖 AI Automation Plan")
                            st.markdown(response)
                            
                            # Log the task
                            agent.log_automation_task("voice_command", transcript, response)
        
        with col2:
            st.subheader("Direct Text Input")
            text_command = st.text_area("Enter automation command:", height=100)
            
            if st.button("Process Text Command"):
                if text_command:
                    prompt = f"""
                    User automation request: "{text_command}"
                    
                    Create a comprehensive automation solution including:
                    1. Analysis of the request
                    2. Required automation steps
                    3. RoboTask script code
                    4. Alternative approaches
                    5. Potential issues and solutions
                    """
                    
                    response = agent.generate_gemini_response(prompt)
                    if response:
                        st.markdown("### 🤖 Automation Solution")
                        st.markdown(response)
                        
                        # Log the task
                        agent.log_automation_task("text_command", text_command, response)
    
    with tab2:
        st.header("📸 Image Analysis & Automation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Upload Image")
            uploaded_file = st.file_uploader("Choose an image", type=['png', 'jpg', 'jpeg'])
            
            if uploaded_file:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded Image", use_column_width=True)
                
                # Save uploaded image
                image_path = agent.images_dir / f"uploaded_{uuid.uuid4().hex[:8]}.png"
                image.save(image_path)
                
                analysis_prompt = st.text_input("Custom analysis prompt:", 
                                               "Analyze this image and suggest automation tasks")
                
                if st.button("Analyze Image with Gemini"):
                    response = agent.process_image_with_gemini(image_path, analysis_prompt)
                    if response:
                        st.markdown("### 🤖 Image Analysis")
                        st.markdown(response)
                        
                        # Log the task
                        agent.log_automation_task("image_analysis", f"Analysis of {uploaded_file.name}", response)
        
        with col2:
            st.subheader("Screen Capture")
            
            if st.button("📱 Capture Current Screen"):
                screen_path = agent.capture_screen()
                if screen_path:
                    st.success("Screen captured successfully!")
                    
                    # Display captured screen
                    screen_image = Image.open(screen_path)
                    st.image(screen_image, caption="Screen Capture", use_column_width=True)
                    
                    # Analyze screen with Gemini
                    screen_prompt = st.text_input("Screen analysis prompt:", 
                                                "Analyze this screen and suggest automation opportunities")
                    
                    if st.button("Analyze Screen"):
                        response = agent.process_image_with_gemini(screen_path, screen_prompt)
                        if response:
                            st.markdown("### 🤖 Screen Analysis")
                            st.markdown(response)
                            
                            # Log the task
                            agent.log_automation_task("screen_analysis", "Screen capture analysis", response)
    
    with tab3:
        st.header("📝 RoboTask Script Generation")
        
        task_description = st.text_area("Describe the automation task:", height=100)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Generate RoboTask Script"):
                if task_description:
                    script_path = agent.create_robotask_script(task_description)
                    
                    with open(script_path, 'r') as f:
                        script_content = f.read()
                    
                    st.code(script_content, language="text")
                    
                    # Provide download button
                    st.download_button(
                        label="Download RoboTask Script",
                        data=script_content,
                        file_name=f"automation_script_{int(time.time())}.rtf",
                        mime="text/plain"
                    )
                    
                    # Log the task
                    agent.log_automation_task("script_generation", task_description, script_content)
        
        with col2:
            st.subheader("Advanced Script Options")
            
            script_type = st.selectbox("Script Type", [
                "Desktop Automation",
                "File Management",
                "Web Automation",
                "System Monitoring",
                "Data Processing"
            ])
            
            complexity = st.selectbox("Complexity Level", [
                "Simple",
                "Intermediate", 
                "Advanced"
            ])
            
            if st.button("Generate Advanced Script"):
                if task_description:
                    advanced_prompt = f"""
                    Generate a {complexity.lower()} level {script_type.lower()} RoboTask script for:
                    {task_description}
                    
                    Include:
                    1. Error handling
                    2. Logging
                    3. Variable management
                    4. Conditional logic
                    5. Loop structures if needed
                    6. Comments explaining each step
                    """
                    
                    response = agent.generate_gemini_response(advanced_prompt)
                    if response:
                        st.code(response, language="text")
                        
                        # Log the task
                        agent.log_automation_task("advanced_script", task_description, response)
    
    with tab4:
        st.header("🌐 Browser Automation")
        
        automation_task = st.text_area("Describe browser automation task:", height=100)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Generate Browser Automation"):
                if automation_task:
                    agent.execute_browser_automation(automation_task)
                    
                    # Log the task
                    agent.log_automation_task("browser_automation", automation_task, "Generated")
        
        with col2:
            st.subheader("Quick Actions")
            
            if st.button("Open Google"):
                st.code("""
from selenium import webdriver
driver = webdriver.Chrome()
driver.get("https://www.google.com")
""", language="python")
            
            if st.button("Fill Form Template"):
                st.code("""
from selenium import webdriver
from selenium.webdriver.common.by import By

driver = webdriver.Chrome()
driver.get("your_form_url")

# Fill form fields
driver.find_element(By.NAME, "username").send_keys("your_username")
driver.find_element(By.NAME, "password").send_keys("your_password")
driver.find_element(By.ID, "submit").click()
""", language="python")
    
    # Footer
    st.markdown("---")
    st.markdown("**Note:** This automation agent integrates with RoboTask, Gemini AI, and various automation libraries. "
                "Always test automation scripts in a safe environment before deploying them.")

if __name__ == "__main__":
    main()
