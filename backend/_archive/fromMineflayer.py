from flask import Flask, request, jsonify
import numpy as np
import cv2
import os
import json
import time
from datetime import datetime
import threading
import requests
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("rl_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("RL_Server")

# Create Flask app
app = Flask(__name__)

# Directory to save received images
SAVE_DIR = "received_images"
os.makedirs(SAVE_DIR, exist_ok=True)
logger.info(f"Images will be saved to: {os.path.abspath(SAVE_DIR)}")

# Current state
current_state = {
    "image": None,
    "metadata": None,
    "timestamp": None
}

# Lock for thread safety
state_lock = threading.Lock()

@app.route('/receive_image', methods=['POST'])
def receive_image():
    """Endpoint to receive images from Mineflayer/Prismarine Viewer"""
    logger.info("Received image request")
    
    try:
        # Print request information for debugging
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Request files: {list(request.files.keys())}")
        logger.info(f"Request form: {list(request.form.keys())}")
        
        # Get the image from the request
        if 'image' not in request.files:
            logger.error("No image part in the request")
            return jsonify({"error": "No image part"}), 400
        
        file = request.files['image']
        logger.info(f"Received file: {file.filename}, size: {file.content_length} bytes")
        
        # Get the metadata
        if 'metadata' not in request.form:
            logger.warning("No metadata in the request, using empty object")
            metadata = {}
        else:
            metadata_str = request.form['metadata']
            logger.info(f"Received metadata: {metadata_str[:100]}...")
            metadata = json.loads(metadata_str)
        
        # Save the image to disk
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"minecraft_{timestamp}.png"
        filepath = os.path.join(SAVE_DIR, filename)
        file.save(filepath)
        logger.info(f"Saved image to: {filepath}")
        
        # Convert image to numpy array for processing
        image_np = cv2.imread(filepath)
        if image_np is None:
            logger.error(f"Failed to read image from {filepath}")
            return jsonify({"error": "Failed to read image"}), 500
            
        logger.info(f"Image shape: {image_np.shape}")
        
        # Process the image for RL
        processed_image = preprocess_image(image_np)
        logger.info(f"Processed image shape: {processed_image.shape}")
        
        # Update current state
        with state_lock:
            current_state["image"] = processed_image
            current_state["metadata"] = metadata
            current_state["timestamp"] = time.time()
        
        # Log receipt and bot position
        if 'position' in metadata:
            pos = metadata['position']
            logger.info(f"Bot position: x={pos.get('x', 0):.1f}, y={pos.get('y', 0):.1f}, z={pos.get('z', 0):.1f}")
        else:
            logger.info("No position data in metadata")
        
        return jsonify({
            "status": "success", 
            "filename": filename,
            "timestamp": timestamp,
            "message": "Image received and processed successfully"
        })
    
    except Exception as e:
        logger.exception("Error processing received image")
        return jsonify({"error": str(e)}), 500

def preprocess_image(image):
    """Preprocess the image for the RL algorithm"""
    # Resize image
    resized = cv2.resize(image, (84, 84))  # Common size for RL
    logger.info(f"Resized image to 84x84")
    
    # Convert to grayscale
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    
    # Normalize pixel values
    normalized = gray.astype(np.float32) / 255.0
    
    # Save processed image for debugging
    debug_path = os.path.join(SAVE_DIR, "processed_debug.png")
    cv2.imwrite(debug_path, gray)
    logger.info(f"Saved processed debug image to: {debug_path}")
    
    return normalized

class RLAgent:
    """Simple RL agent class"""
    
    def __init__(self, command_url="http://localhost:3001/command"):
        self.command_url = command_url
        self.running = False
        self.thread = None
        logger.info(f"RLAgent initialized, command URL: {command_url}")
    
    def start(self):
        """Start the RL agent in a separate thread"""
        if self.running:
            logger.info("Agent is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self.run_loop)
        self.thread.daemon = True
        self.thread.start()
        logger.info("Agent started")
    
    def stop(self):
        """Stop the RL agent"""
        if not self.running:
            logger.info("Agent is not running")
            return
            
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        logger.info("Agent stopped")
    
    def run_loop(self):
        """Main RL loop"""
        logger.info("RL loop started")
        loop_count = 0
        
        while self.running:
            # Get current state
            with state_lock:
                image = current_state["image"]
                metadata = current_state["metadata"]
                timestamp = current_state["timestamp"]
            
            if image is not None and metadata is not None:
                # Log every 10 iterations to avoid spamming the log
                if loop_count % 10 == 0:
                    time_ago = time.time() - (timestamp or 0)
                    logger.info(f"Processing state, image shape: {image.shape}, metadata age: {time_ago:.2f}s")
                
                # Make a decision based on the current state
                action = self.decide_action(image, metadata)
                
                # Send the action to the Minecraft bot
                self.send_action(action)
                
                loop_count += 1
            else:
                logger.warning("No state available yet")
                time.sleep(1.0)
                continue
            
            # Sleep to control loop rate
            time.sleep(0.1)
    
    def decide_action(self, image, metadata):
        """Decide what action to take based on the current state"""
        import random
        
        actions = [
            {"action": "move", "params": {"forward": True, "back": False, "left": False, "right": False, "jump": False}},
            {"action": "move", "params": {"forward": False, "back": True, "left": False, "right": False, "jump": False}},
            {"action": "move", "params": {"forward": False, "back": False, "left": True, "right": False, "jump": False}},
            {"action": "move", "params": {"forward": False, "back": False, "left": False, "right": True, "jump": False}},
            {"action": "move", "params": {"forward": True, "back": False, "left": False, "right": False, "jump": True}},
            {"action": "look", "params": {"yaw": random.uniform(-3.14, 3.14), "pitch": random.uniform(-1.5, 1.5)}}
        ]
        
        return random.choice(actions)
    
    def send_action(self, action):
        """Send an action to the Minecraft bot"""
        try:
            response = requests.post(self.command_url, json=action, timeout=2.0)
            if response.status_code == 200:
                logger.info(f"Sent action: {action['action']}")
            else:
                logger.error(f"Failed to send action: {response.status_code}, {response.text}")
        except Exception as e:
            logger.exception(f"Error sending action: {e}")

# Create the RL agent
agent = RLAgent()

@app.route('/start_agent', methods=['POST'])
def start_agent():
    """Start the RL agent"""
    logger.info("Received request to start agent")
    agent.start()
    return jsonify({"status": "Agent started"})

@app.route('/stop_agent', methods=['POST'])
def stop_agent():
    """Stop the RL agent"""
    logger.info("Received request to stop agent")
    agent.stop()
    return jsonify({"status": "Agent stopped"})

@app.route('/status', methods=['GET'])
def status():
    """Check if the server is running"""
    logger.info("Status check received")
    return jsonify({
        "status": "running",
        "images_received": len(os.listdir(SAVE_DIR)),
        "agent_running": agent.running,
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    logger.info("Starting Python RL server...")
    # Start Flask server
    # Use debug=False in production
    app.run(host='0.0.0.0', port=5000, debug=True)