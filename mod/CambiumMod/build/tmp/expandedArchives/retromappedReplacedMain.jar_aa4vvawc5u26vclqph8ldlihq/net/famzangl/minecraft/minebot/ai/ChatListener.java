package net.famzangl.minecraft.minebot.ai;

import net.famzangl.minecraft.minebot.PhysicsController;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.APIClient;
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
        String message = event.message.func_150260_c();

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
            EntityPlayerSP player = controller.getMinecraft().field_71439_g;
            String name = (player != null) ? player.func_70005_c_() : "Unknown";

            try {
                    String jsonInputString = "{\"name\":\"" + name + "\"}";
                    String response = APIClient.postRequest("/bot-setup", jsonInputString);
                    if (response != null) {
                        AIChatController.addChatLine("Bot " + name + " added to game!");
                    } else {
                        AIChatController.addChatLine("Error: No response from backend");
                    }
                } catch (Exception e) {
					AIChatController.addChatLine("Error: " + e.toString());
					e.printStackTrace();
				}
        }
        
        // &bot-setup: Load all configuration data (action space, observation space, model endpoint)
        if (message.contains("&bot-setup")) {
            System.out.println("Detected 'bot-setup' in chat!");
            AIController controller = AIController.getInstance();
            EntityPlayerSP player = controller.getMinecraft().field_71439_g;
            String name = (player != null) ? player.func_70005_c_() : "Unknown";
            
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
