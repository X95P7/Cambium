package net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses.PlayerData;
import net.minecraft.client.Minecraft;

public class GetPlayer {
    private Minecraft mc;

    public GetPlayer(AIHelper helper){
        mc = helper.getMinecraft();
    }

    public PlayerData getPlayerData(){
        return new PlayerData(mc.thePlayer.getHealth(), mc.thePlayer.rotationYaw, mc.thePlayer.rotationPitch, mc.thePlayer.posX, mc.thePlayer.posY, mc.thePlayer.posZ, mc.thePlayer.getTotalArmorValue());
    }
}
