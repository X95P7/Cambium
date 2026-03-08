package net.famzangl.minecraft.minebot.ai;

import net.famzangl.minecraft.minebot.ai.cambiumInputs.APIClient;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGameOver;
import net.minecraft.entity.player.EntityPlayer;
import net.minecraftforge.client.event.GuiOpenEvent;
import net.minecraftforge.event.entity.living.LivingDeathEvent;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;


public class DeathListener {

    
    private boolean shouldRespawn = false;
    private boolean deathReported = false;
    private long lastDeathReportTime = 0;
    private static final long DEATH_REPORT_COOLDOWN = 5000; // 5 seconds cooldown between death reports

    @SubscribeEvent
    public void onPlayerDeath(LivingDeathEvent event) {
        // Ensure this runs only on the client
        if (event.entity.worldObj.isRemote) {
            if (event.entity instanceof EntityPlayer) {
                EntityPlayer player = (EntityPlayer) event.entity;
                String name = player.getName();
                
                AIChatController.addChatLine("Bot " + name + " has died!");
                
                // Report death to API (only once per death event)
                if (!deathReported) {
                    reportDeath(name);
                    deathReported = true;
                }
                
                // Mark the player for respawn
                shouldRespawn = true;
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
        // Prevent multiple death reports within cooldown period
        long currentTime = System.currentTimeMillis();
        if (currentTime - lastDeathReportTime < DEATH_REPORT_COOLDOWN) {
            return; // Skip if called too soon after last report
        }
        lastDeathReportTime = currentTime;
        
        try {
            String jsonInputString = "{\"name\":\"" + name + "\"}";
            APIClient.postRequest("/death/", jsonInputString);
        } catch (Exception e) {
            AIChatController.addChatLine("Error reporting death: " + e.getMessage());
            e.printStackTrace();
        }
    }
}
