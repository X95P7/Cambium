package com.example.tickfreeze;

import net.minecraft.command.CommandBase;
import net.minecraft.command.ICommandSender;
import net.minecraft.server.MinecraftServer;
import net.minecraft.util.ChatComponentText;

public class FreezeCommand extends CommandBase {
    @Override
    public String getCommandName() {
        return "freeze";
    }

    @Override
    public String getCommandUsage(ICommandSender sender) {
        return "/freeze - Toggles tick freezing";
    }

    @Override
    public void processCommand(ICommandSender sender, String[] args) {
        TickFreezeMod.toggleFreeze();
        sender.addChatMessage(new ChatComponentText("Tick Freezing: " + (TickFreezeMod.freezeTicks ? "ON" : "OFF")));
    }

    @Override
    public int getRequiredPermissionLevel() {
        return 2; // Only operators can run this command
    }
}
