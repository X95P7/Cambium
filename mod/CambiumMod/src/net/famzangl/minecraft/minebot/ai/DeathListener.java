package net.famzangl.minecraft.minebot.ai;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGameOver;
import net.minecraft.entity.player.EntityPlayer;
import net.minecraftforge.client.event.GuiOpenEvent;
import net.minecraftforge.event.entity.living.LivingDeathEvent;
import net.minecraftforge.fml.common.Mod.EventHandler;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;


public class DeathListener {

    
    private boolean shouldRespawn = false;
    private boolean deathReported = false;

    @SubscribeEvent
    public void onPlayerDeath(LivingDeathEvent event) {
        // Ensure this runs only on the client
        if (event.entity.worldObj.isRemote) {
            if (event.entity instanceof EntityPlayer) {
                EntityPlayer player = (EntityPlayer) event.entity;
                String name = player.getName();
                
                AIChatController.addChatLine("Bot " + name + " has died!");
                
                // Report death to API
                reportDeath(name);
                
                // Mark the player for respawn
                shouldRespawn = true;
                deathReported = true;
            }
        }
    }

    @SubscribeEvent
    public void onDeathScreen(GuiOpenEvent event) {
        if (event.gui instanceof GuiGameOver) {
            event.setCanceled(true); // Cancel death screen
            shouldRespawn = true; // Flag for respawning in the next tick
            
            // Report death if not already reported
            if (!deathReported) {
                Minecraft mc = Minecraft.getMinecraft();
                if (mc.thePlayer != null) {
                    String name = mc.thePlayer.getName();
                    reportDeath(name);
                    deathReported = true;
                }
            }
        }
    }

    @SubscribeEvent
    public void onClientTick(TickEvent.ClientTickEvent event) {
        if (shouldRespawn) {
            Minecraft mc = Minecraft.getMinecraft();
            if (mc.thePlayer != null) {
                mc.thePlayer.respawnPlayer();
                shouldRespawn = false;
                deathReported = false;
            }
        }
    }
    
    private void reportDeath(String name) {
        try {
            String urlString = "http://backend:8000/death/";
            URL url = new URL(urlString);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);
            
            String jsonInputString = "{\"name\":\"" + name + "\"}";
            OutputStream os = conn.getOutputStream();
            os.write(jsonInputString.getBytes("UTF-8"));
            os.close();
            
            int responseCode = conn.getResponseCode();
            InputStream is = responseCode == HttpURLConnection.HTTP_OK
                    ? conn.getInputStream()
                    : conn.getErrorStream();
            
            if (is != null) {
                is.close();
            }
        } catch (Exception e) {
            AIChatController.addChatLine("Error reporting death: " + e.getMessage());
            e.printStackTrace();
        }
    }
}
