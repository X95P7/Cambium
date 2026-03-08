package net.famzangl.minecraft.minebot;

import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent.ClientTickEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent.PlayerTickEvent;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.minecraft.client.Minecraft;
import net.minecraft.client.entity.EntityPlayerSP;
import net.minecraft.entity.player.EntityPlayerMP;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.FMLCommonHandler;

import net.minecraft.client.Minecraft;
import net.minecraft.client.entity.EntityPlayerSP;
import net.minecraft.client.settings.GameSettings;
import net.minecraft.client.settings.KeyBinding;

import net.minecraft.client.Minecraft;
import net.minecraft.client.entity.EntityPlayerSP;
import net.minecraft.client.settings.GameSettings;
import net.minecraft.client.settings.KeyBinding;

public class PhysicsController {

    private boolean allowNextTick = false;
    private int count = 0;
    private long lastTickTime = -1;

    // Movement & action keys
    public boolean forward = false;
    public boolean back = false;
    public boolean left = false;
    public boolean right = false;
    public boolean jump = false;
    public boolean sneak = false;
    public boolean sprint = false;
    public boolean attack = false;
    public boolean useItem = false;

    // Hotbar keys 0-9
    public boolean hotbar0 = false;
    public boolean hotbar1 = false;
    public boolean hotbar2 = false;
    public boolean hotbar3 = false;
    public boolean hotbar4 = false;
    public boolean hotbar5 = false;
    public boolean hotbar6 = false;
    public boolean hotbar7 = false;
    public boolean hotbar8 = false;
    public boolean hotbar9 = false;

    // Mouse movement
    public float deltaYaw = 0f;
    public float deltaPitch = 0f;

    private final GameSettings settings = Minecraft.func_71410_x().field_71474_y;

    public void step() {
        allowNextTick = true;
        EntityPlayerSP player = Minecraft.func_71410_x().field_71439_g;
        if (player != null) {
            player.field_70145_X = false;
        }
    }

    public void tick() {
        long currentTime = System.currentTimeMillis();
        if (lastTickTime != -1) {
            //AIChatController.addChatLine("Time since last tick: " + (currentTime - lastTickTime) + " ms");
        }
        lastTickTime = currentTime;

        EntityPlayerSP player = Minecraft.func_71410_x().field_71439_g;
        if (player == null) return;

        // Apply mouse movement
        player.field_70177_z += deltaYaw;
        player.field_70125_A += deltaPitch;

        // Clamp pitch
        if (player.field_70125_A > 90) player.field_70125_A = 90;
        if (player.field_70125_A < -90) player.field_70125_A = -90;

        // Handle movement & action keys
        setKey(settings.field_74351_w, forward);
        setKey(settings.field_74368_y, back);
        setKey(settings.field_74370_x, left);
        setKey(settings.field_74366_z, right);
        setKey(settings.field_74314_A, jump);
        setKey(settings.field_74311_E, sneak);
        setKey(settings.field_151444_V, sprint);
        setKey(settings.field_74312_F, attack);
        setKey(settings.field_74313_G, useItem);

        // Handle hotbar keys (0-9)
        KeyBinding[] hotbar = settings.field_151456_ac;
        boolean[] hotbarStates = {
            hotbar0, hotbar1, hotbar2, hotbar3, hotbar4,
            hotbar5, hotbar6, hotbar7, hotbar8, hotbar9
        };
        for (int i = 0; i < hotbar.length && i < hotbarStates.length; i++) {
            setKey(hotbar[i], hotbarStates[i]);
        }
    }

    private void setKey(KeyBinding keyBind, boolean pressed) {
        int code = keyBind.func_151463_i();
        KeyBinding.func_74510_a(code, pressed);
        if (pressed) {
            KeyBinding.func_74507_a(code);
        }
    }
}



