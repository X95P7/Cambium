package com.example.tickfreeze;

import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.common.event.FMLServerStartingEvent;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;
import net.minecraft.client.Minecraft;

import java.net.URI;
import java.net.URISyntaxException;

import main.java.com.example.tickfreeze.BotCommunicationClient;
import net.minecraft.server.MinecraftServer;

import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;
import java.net.URI;

@Mod(modid = TickFreezeMod.MODID, version = TickFreezeMod.VERSION, acceptableRemoteVersions = "*")
public class TickFreezeMod {
    public static final String MODID = "tickfreeze";
    public static final String VERSION = "1.0";

    public static boolean freezeTicks = false;

    @Mod.EventHandler
    public void onServerStart(FMLServerStartingEvent event) throws URISyntaxException {
        event.registerServerCommand(new FreezeCommand());
        //WebSocketClient client = new BotCommunicationClient(new URI("ws://localhost:8080"));
        //client.connect();
    }

    private static int tickDelay = 50; // Default 50ms per tick

    @SubscribeEvent
    public void onServerTick(TickEvent.ServerTickEvent event) {
        Minecraft mc = Minecraft.getMinecraft();
            if(mc == null) return; // Wut
    }

    public static void toggleFreeze() {
        Minecraft mc = Minecraft.getMinecraft();
            if(mc == null) return; // Wut

        if(freezeTicks){
            //put overkill tick rate here
            mc.timer.tickLength = 2000F;
        } else {
            mc.timer.tickLength = 1000F / 20;
        }
        freezeTicks = !freezeTicks;
    }


}