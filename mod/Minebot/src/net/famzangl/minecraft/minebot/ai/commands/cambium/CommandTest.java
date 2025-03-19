/*******************************************************************************
    _______      ____    ,---.    ,---. _______  .-./`)   ___    _ ,---.    ,---.        
   /   __  \   .'  __ `. |    \  /    |\  ____  \\ .-.').'   |  | ||    \  /    |        
  | ._/  \__) /   '  \  \|  ,  \/  ,  || |    \ |/ `-' \|   .|  | ||  ,  \/  ,  |        
,-./  )       |___|  /  ||  |\_   /|  || |____/ / `-'`"`.'  'L  | ||  |\_   /|  |        
\  '_ '`)        _.-`   ||  _( )_/ |  ||   _ _ '. .---. '   ( \.-.||  _( )_/ |  |        
 > (_)  )  __ .'   _    || (_ o _) |  ||  ( ' )  \|   | ' (`. _` /|| (_ o _) |  |        
(  .  .-'_/  )|  _( )_  ||  (_,_)  |  || (_{;}_) ||   | | (_ (_) _)|  (_,_)  |  |        
 `-'`-'     / \ (_ o _) /|  |      |  ||  (_,_)  /|   |  \ /  . \ /|  |      |  |        
   `\_____.'   '.(_,_).' '--'      '--'/_______.' '---'   ``-'`-'' '--'      '--'        
                                                                                         
 *******************************************************************************/
package net.famzangl.minecraft.minebot.ai.commands.cambium;

import java.io.OutputStream;
import java.lang.reflect.Array;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;

import javax.swing.text.html.parser.Entity;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses.BlockData;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses.EntityData;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses.InventoryData;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation.GetBlocks;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation.GetEntities;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation.GetInventory;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation.GetPlayer;
import net.famzangl.minecraft.minebot.ai.command.AICommand;
import net.famzangl.minecraft.minebot.ai.command.AICommandInvocation;
import net.famzangl.minecraft.minebot.ai.command.AICommandParameter;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.famzangl.minecraft.minebot.ai.command.ParameterType;
import net.famzangl.minecraft.minebot.ai.strategy.AIStrategy;
import net.famzangl.minecraft.minebot.ai.strategy.EatStrategy;

@AICommand(helpText = "Sends out a chat message", name = "cambium")
public class CommandTest {
	@AICommandInvocation()
	public static AIStrategy run(
			AIHelper helper,
			@AICommandParameter(type = ParameterType.FIXED, fixedName = "test", description = "") String nameArg) {

				try {
					long startTime = System.currentTimeMillis();
					// URL of the Python API
					URL url = new URL("http://127.0.0.1:8000/process-data");
					HttpURLConnection conn = (HttpURLConnection) url.openConnection();
		
					// Set up the HTTP connection
					conn.setRequestMethod("POST");
					conn.setRequestProperty("Content-Type", "application/json");
					conn.setDoOutput(true);
		
					// Send JSON payload
					String jsonInputString = "{\"key\":\"example\",\"value\":42}";
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
					
					GetBlocks getBlocks = new GetBlocks(helper);
					GetEntities getEnities = new GetEntities(helper);
					GetInventory getInventory = new GetInventory(helper);
					GetPlayer getPlayer = new GetPlayer(helper);

					ArrayList<BlockData> blocks = getBlocks.doRaytrace();

					int c = 0;
					AIChatController.addChatLine("Blocks");
					for(BlockData block : blocks){
						AIChatController.addChatLine(c + block.toString());
						c++;
					}

					ArrayList<EntityData> entities = getEnities.getEntities();
					
					AIChatController.addChatLine("Entities");
					for(EntityData entity : entities){
						if(entity != null){
							AIChatController.addChatLine(entity.toString());
						}
					}

					ArrayList<InventoryData> inventory = getInventory.getInventoryData();

					for(InventoryData inv : inventory){
						AIChatController.addChatLine(inv.toString());
					}

					AIChatController.addChatLine(getPlayer.getPlayerData().toString());
					
				
					// Print response
					System.out.println("Response Code: " + conn.getResponseCode());
					System.out.println("Response Body: " + response.toString());
					AIChatController.addChatLine("Response Code: " + conn.getResponseCode());
					AIChatController.addChatLine("Response Body: " + response.toString());
					AIChatController.addChatLine("Response Time: " + (System.currentTimeMillis() - startTime));
		
				} catch (Exception e) {
					AIChatController.addChatLine("Error: " + e.toString());
					e.printStackTrace();
				}



        AIChatController.addChatLine("cambium Test message");
		return null;
	}
}
