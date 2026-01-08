package com.example.tickfreeze;

import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.common.event.FMLServerStartingEvent;

@Mod(modid = TickFreezeMod.MODID, version = TickFreezeMod.VERSION, acceptableRemoteVersions = "*")
public class TickFreezeMod {
    public static final String MODID = "tickfreeze";
    public static final String VERSION = "1.0";

    @Mod.EventHandler
    public void onServerStart(FMLServerStartingEvent event) {
        // Register projectile knockback handler
        MinecraftForge.EVENT_BUS.register(new ProjectileKnockbackHandler());
        // FreezeCommand removed - no longer needed
    }
}