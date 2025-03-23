package net.famzangl.minecraft.minebot.ai;

import akka.japi.Effect;
import ibxm.Player;
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

    @SubscribeEvent
    public void onPlayerDeath(LivingDeathEvent event) {
        // Ensure this runs only on the client
        if (event.entity.worldObj.isRemote) {
            if (event.entity instanceof EntityPlayer) {
                AIChatController.addChatLine("some1 diead"); // Debugging: Should print when player dies
                
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
        }
    }

    @SubscribeEvent
    public void onClientTick(TickEvent.ClientTickEvent event) {
        if (shouldRespawn) {
            Minecraft mc = Minecraft.getMinecraft();
            if (mc.thePlayer != null) {
                mc.thePlayer.respawnPlayer();
                shouldRespawn = false;
                //send api call here!
            }
        }
    }
}
