package net.famzangl.minecraft.minebot.ai;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

import net.famzangl.minecraft.minebot.PhysicsController;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.famzangl.minecraft.minebot.ai.strategy.cambium.RLControllerStrategy;
import net.minecraft.client.entity.EntityPlayerSP;
import net.minecraftforge.client.event.ClientChatReceivedEvent;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;

public class ChatListener {

	private PhysicsController controller = new PhysicsController();

    @SubscribeEvent
    public void onChatReceived(ClientChatReceivedEvent event) {
        // Get the message as a string
        String message = event.message.getUnformattedText();

		if(message.contains(".step")){
			try{
				AIChatController.addChatLine("Stepping");
				controller.step();
			} catch(Exception e){
				AIChatController.addChatLine("Error: " + e.toString());
			}
		}

        // Check if the message contains the target phrase
        if (message.contains("&setup")) {
            System.out.println("Detected 'setup' in chat!");
            AIController controller = AIController.getInstance();
            EntityPlayerSP player = controller.getMinecraft().thePlayer;
            String name = (player != null) ? player.getName() : "Unknown";

            try {
					// URL of the Python API - use service name for Docker Compose networking
					String string_url = "http://backend:8000/bot-setup";
					URL url = new URL(string_url);
					System.out.println("attempting to connect to: " + string_url );
					HttpURLConnection conn = (HttpURLConnection) url.openConnection();
		
					// Set up the HTTP connection
					conn.setRequestMethod("POST");
					conn.setRequestProperty("Content-Type", "application/json");
					conn.setDoOutput(true);
		
					// Send JSON payload
                    String jsonInputString = "{\"name\":\"" + name + "\"}";
					OutputStream os = conn.getOutputStream();
					os.write(jsonInputString.getBytes("UTF-8"));
					os.close();
		
					// Get response
					InputStream is = conn.getResponseCode() == HttpURLConnection.HTTP_OK
									 ? conn.getInputStream()
									 : conn.getErrorStream();
		
					byte[] buffer = new byte[1024];
					int bytesRead;
					StringBuilder response = new StringBuilder();
					while ((bytesRead = is.read(buffer)) != -1) {
						response.append(new String(buffer, 0, bytesRead, "UTF-8"));
					}
					is.close();
					
					AIChatController.addChatLine("Bot " + name + " added to game!");
                } catch (Exception e) {
					AIChatController.addChatLine("Error: " + e.toString());
					e.printStackTrace();
				}
        }
        
        // &bot-setup: Load all configuration data (action space, observation space, model endpoint)
        if (message.contains("&bot-setup")) {
            System.out.println("Detected 'bot-setup' in chat!");
            AIController controller = AIController.getInstance();
            EntityPlayerSP player = controller.getMinecraft().thePlayer;
            String name = (player != null) ? player.getName() : "Unknown";
            
            try {
                // Create RL Controller Strategy instance (but don't add it yet)
                RLControllerStrategy rlStrategy = new RLControllerStrategy();
                
                // Load configurations from API
                AIChatController.addChatLine("Loading action space config...");
                rlStrategy.loadActionSpaceConfig();
                
                AIChatController.addChatLine("Loading observation space config...");
                rlStrategy.loadObservationSpaceConfig();
                
                AIChatController.addChatLine("Loading model endpoint for " + name + "...");
                // AIController extends AIHelper, so we can use it directly
                rlStrategy.loadModelEndpoint(controller);
                
                // Store the strategy instance for later use with &run
                // We'll store it in a static map or similar - for now, just notify
                AIChatController.addChatLine("Bot setup complete! Use &run to start the bot.");
                
                // Store strategy in controller for later retrieval
                controller.setStoredRLStrategy(rlStrategy);
            } catch (Exception e) {
                AIChatController.addChatLine("Error in bot-setup: " + e.toString());
                e.printStackTrace();
            }
        }
        
        // &run: Start the RL Controller Strategy
        if (message.contains("&run")) {
            System.out.println("Detected 'run' in chat!");
            AIController controller = AIController.getInstance();
            
            try {
                // Get stored RL strategy from controller
                RLControllerStrategy rlStrategy = controller.getStoredRLStrategy();
                
                if (rlStrategy == null) {
                    // If no stored strategy, create a new one and load configs
                    AIChatController.addChatLine("No stored strategy found. Creating new one...");
                    rlStrategy = new RLControllerStrategy();
                    
                    // Load configurations
                    rlStrategy.loadActionSpaceConfig();
                    rlStrategy.loadObservationSpaceConfig();
                    
                    // AIController extends AIHelper, so we can use it directly
                    rlStrategy.loadModelEndpoint(controller);
                }
                
                // Add strategy to controller
                controller.addStrategy(rlStrategy);
                AIChatController.addChatLine("RL Controller started!");
            } catch (Exception e) {
                AIChatController.addChatLine("Error starting RL Controller: " + e.toString());
                e.printStackTrace();
            }
        }
        
        // &reset: Clear all strategies and reset bot state
        if (message.contains("&reset")) {
            System.out.println("Detected 'reset' in chat!");
            AIController controller = AIController.getInstance();
            
            try {
                // Clear all active strategies
                controller.clearStrategies();
                
                // Clear stored RL strategy
                controller.setStoredRLStrategy(null);
                
                // Reset physics controller
                PhysicsController physicsController = new PhysicsController();
                
                AIChatController.addChatLine("Bot reset complete! All strategies cleared.");
            } catch (Exception e) {
                AIChatController.addChatLine("Error resetting bot: " + e.toString());
                e.printStackTrace();
            }
        }
    }
}
