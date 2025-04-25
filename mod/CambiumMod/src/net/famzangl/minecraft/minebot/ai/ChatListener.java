package net.famzangl.minecraft.minebot.ai;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

import net.famzangl.minecraft.minebot.PhysicsController;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.famzangl.minecraft.minebot.ai.strategy.cambium.LeftClickStrategy;
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
					// URL of the Python API
					URL url = new URL("http://127.0.0.1:8000/bot-setup");
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
                } catch (Exception e) {
					AIChatController.addChatLine("Error: " + e.toString());
					e.printStackTrace();
				}
            
        
            //controller.addStrategy(new LeftClickStrategy(15, 20, controller.getAiHelper()));

            // Optional: Cancel the message from appearing in chat
            // event.setCanceled(true);
        }
    }
}
