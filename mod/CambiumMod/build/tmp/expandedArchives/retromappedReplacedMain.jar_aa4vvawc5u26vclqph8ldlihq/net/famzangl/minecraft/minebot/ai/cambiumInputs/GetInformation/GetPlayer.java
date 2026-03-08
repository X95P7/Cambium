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
        return new PlayerData(mc.field_71439_g.func_110143_aJ(), mc.field_71439_g.field_70177_z, mc.field_71439_g.field_70125_A, mc.field_71439_g.field_70165_t, mc.field_71439_g.field_70163_u, mc.field_71439_g.field_70161_v, mc.field_71439_g.func_70658_aO());
    }
}
