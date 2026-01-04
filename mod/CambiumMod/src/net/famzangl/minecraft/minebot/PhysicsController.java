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
    public boolean forward = true;
    public boolean back = false;
    public boolean left = false;
    public boolean right = false;
    public boolean jump = false;
    public boolean sneak = true;
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

    private final GameSettings settings = Minecraft.getMinecraft().gameSettings;

    public void step() {
        allowNextTick = true;
        EntityPlayerSP player = Minecraft.getMinecraft().thePlayer;
        if (player != null) {
            player.noClip = false;
        }
    }

    public void tick() {
        long currentTime = System.currentTimeMillis();
        if (lastTickTime != -1) {
            //AIChatController.addChatLine("Time since last tick: " + (currentTime - lastTickTime) + " ms");
        }
        lastTickTime = currentTime;

        EntityPlayerSP player = Minecraft.getMinecraft().thePlayer;
        if (player == null) return;

        // Apply mouse movement
        player.rotationYaw += deltaYaw;
        player.rotationPitch += deltaPitch;

        // Clamp pitch
        if (player.rotationPitch > 90) player.rotationPitch = 90;
        if (player.rotationPitch < -90) player.rotationPitch = -90;

        // Handle movement & action keys
        setKey(settings.keyBindForward, forward);
        setKey(settings.keyBindBack, back);
        setKey(settings.keyBindLeft, left);
        setKey(settings.keyBindRight, right);
        setKey(settings.keyBindJump, jump);
        setKey(settings.keyBindSneak, sneak);
        setKey(settings.keyBindSprint, sprint);
        setKey(settings.keyBindAttack, attack);
        setKey(settings.keyBindUseItem, useItem);

        // Handle hotbar keys (0-9)
        KeyBinding[] hotbar = settings.keyBindsHotbar;
        boolean[] hotbarStates = {
            hotbar0, hotbar1, hotbar2, hotbar3, hotbar4,
            hotbar5, hotbar6, hotbar7, hotbar8, hotbar9
        };
        for (int i = 0; i < hotbar.length && i < hotbarStates.length; i++) {
            setKey(hotbar[i], hotbarStates[i]);
        }
    }

    private void setKey(KeyBinding keyBind, boolean pressed) {
        int code = keyBind.getKeyCode();
        KeyBinding.setKeyBindState(code, pressed);
        if (pressed) {
            KeyBinding.onTick(code);
        }
    }
}



